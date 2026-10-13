#!/usr/bin/env python3
"""Answer-aware SpaRAGraph / ToposKG topological consistency audit.

Directional conjunction A adjacent-to-and-N B is treated as (touches(A,B) AND direction(A,B)).
True gold => touches must be true; False gold => topology alone cannot decide unless
reference proves not touches. NEVER infer nonadjacency from a negative directional answer.
"""
import argparse
import collections
import csv
import json
import logging
import re
from pathlib import Path

from validate_sparagraph_v2 import (connect, build_metadata, build_graph, basename, norm,
    truth_ref, truth_kg, parse_task, csv_writer)

LOG=logging.getLogger('audit_v3')
DIRECTIONAL=re.compile(r'\badjacent\s+to\s+and\s+(?:north|south|east|west|northeast|northwest|southeast|southwest)\b',re.I)


def gold_parts(raw,typ):
    text=(raw or '').strip().lower()
    if typ=='yesno':
        if text in {'yes','true','1'}:return {'answer'},None
        if text in {'no','false','0'}:return set(),None
        return set(),'unknown_yesno_gold'
    letters=set(re.findall(r'(?<![a-z])[a-e](?![a-z])',text))
    if not letters:return set(),'unknown_choice_gold'
    return letters,None


def evidence(con,la,ra,refa,refb,relation):
    """Safely aggregate multiple ToposKG candidates.
    A verdict is true/false only if every candidate-pair produces the same explicit verdict.
    Missing/ambiguous alignment is always unknown, never a fabricated contradiction.
    """
    kval=truth_kg(con,la,ra,relation)
    if not refa or not refb:
        return kval,None,'missing_reference_alignment',None,None
    if len(refa)!=1 or len(refb)!=1:
        return kval,None,'ambiguous_reference_alignment',None,None
    a,b=refa[0],refb[0]
    return kval,truth_ref(con,a,b,relation),'reference_evidence',a,b


def inspect_atomic(typ,selected,directional,kgval,refval,closed_world):
    """Return status for correctness of original gold, not of assertion alone.

    Gold for radio: selected option claims a relation; unselected options are not
    independent negative labels. Gold for directional choices: unselected/No
    does not imply not-touches. For checkbox non-directional unselected is a
    negative, but directional unchecked is not a nonadjacency assertion.
    """
    if refval is None and closed_world:refval=False
    if refval is None:return 'unverifiable','reference_topology_unknown'
    if directional:
        if selected and refval is False:return 'gold_inconsistent','positive_directional_answer_requires_touching'
        if selected and refval is True:return 'topology_supported_direction_unchecked','positive_answer_topology_confirmed_only'
        if not selected and refval is False:return 'gold_supported','non_touching_proves_directional_conjunction_false'
        return 'unverifiable','negative_directional_gold_does_not_imply_nonadjacency'
    if typ=='radio' and not selected:
        return 'not_applicable','unselected_radio_option_not_negative_annotation'
    if selected:
        return ('gold_supported','positive_gold_confirmed') if refval else ('gold_inconsistent','positive_gold_refuted')
    return ('gold_inconsistent','negative_gold_refuted') if refval else ('gold_supported','negative_gold_confirmed')


def run(args):
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    db=out/'audit_index.sqlite'
    if db.exists():db.unlink()
    con=connect(db)
    LOG.info('Indexing reference metadata...');build_metadata(con,args.entities)
    LOG.info('Indexing reference relations...');build_graph(con,args.mappings,'rel')
    LOG.info('Indexing SpaRAGraph KG...');build_graph(con,args.kg,'kg_rel')
    known=collections.defaultdict(list)
    for (uri,) in con.execute('SELECT source FROM kg_rel UNION SELECT target FROM kg_rel'):
        known[norm(basename(uri))].append(uri)
    refs=collections.defaultdict(list)
    for alias,uri in con.execute('SELECT alias,entity FROM aliases'):
        refs[alias].append(uri)
    columns=['source_file','source_type','source_row','query','truth','topological_relation','mixed_directional','gold_relation']
    extras=['status','scope','reason','atomic_checks','gold_supported_checks','gold_inconsistent_checks',
            'topology_supported_direction_unchecked','unverifiable_checks','not_applicable_checks',
            'kg_reference_topology_disagreements','original_gold_checked']
    fh,w=csv_writer(out/'question_results.csv',columns+extras)
    atomcols=['source_file','source_type','source_row','option','gold_selected',
              'directional_conjunction','predicate','spatex_subject','spatex_object',
              'topos_subject','topos_object','kg_topology','reference_topology','status','reason']
    ah,aw=csv_writer(out/'atomic_checks.csv',atomcols)
    qcnt=collections.Counter(); acnt=collections.Counter(); total=0
    with open(args.questions,encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            total+=1
            typ=row.get('source_type','').strip().lower()
            selected,gerr=gold_parts(row.get('truth',''),typ)
            parseerr,tasks=parse_task(row,known)
            direction=bool(DIRECTIONAL.search(row.get('query','')))
            statuses=collections.Counter(); counts=collections.Counter()
            if parseerr or gerr:
                final='skipped';reason=parseerr or gerr; qcnt[final]+=1
            else:
                for key, (alias_a,possible_a),(alias_b,possible_b),rel in tasks:
                    is_selected = key in selected
                    # Distinguish direction-dependent radio options from purely topological ones:
                    # only options themselves containing direction are conjunctions.
                    if typ=='radio':
                        _,opts=split_options_local(row['query'])
                        task_direction=bool(DIRECTIONAL.search(opts.get(key,'')))
                    else:task_direction=direction and rel=='touches'
                    uri_a=list(set(possible_a));uri_b=list(set(possible_b))
                    sa=uri_a[0] if len(uri_a)==1 else None
                    sb=uri_b[0] if len(uri_b)==1 else None
                    ra=refs.get(alias_a,[]);rb=refs.get(alias_b,[])
                    if sa is None or sb is None:
                        verdict='unverifiable';why='ambiguous_spatex_entity';kgval=refval=ta=tb=None
                    else:
                        kgval,refval,align_reason,ta,tb=evidence(con,sa,sb,ra,rb,rel)
                        if align_reason!='reference_evidence':
                            verdict='unverifiable';why=align_reason
                        else:
                            verdict,why=inspect_atomic(typ,is_selected,task_direction,kgval,refval,args.closed_world)
                    if verdict!='not_applicable':statuses[verdict]+=1
                    counts[verdict]+=1;acnt[verdict]+=1
                    if kgval is True and refval is False:counts['kg_reference_topology_disagreements']+=1
                    aw.writerow(dict(source_file=row.get('source_file',''),source_type=typ,source_row=row.get('source_row',''),
                        option=key,gold_selected=int(is_selected),directional_conjunction=int(task_direction),predicate=rel,
                        spatex_subject=sa or '',spatex_object=sb or '',topos_subject=ta or '',topos_object=tb or '',
                        kg_topology='unknown' if kgval is None else str(kgval).lower(),
                        reference_topology='unknown' if refval is None else str(refval).lower(),status=verdict,reason=why))
                # Strongest sound interpretation: any explicit refutation of gold makes entire
                # answer incorrect; all parts must be fully evidenced to mark gold correct.
                if statuses['gold_inconsistent']:
                    final='gold_inconsistent';reason='at_least_one_gold_claim_refuted'
                elif statuses['unverifiable']:
                    final='unverifiable';reason='some_gold_claims_unverifiable'
                elif statuses['topology_supported_direction_unchecked']:
                    final='topology_supported_direction_unchecked';reason='direction_not_checked'
                elif statuses['gold_supported'] and not statuses['unverifiable']:
                    if typ=='radio':
                        final='topology_compatible_radio';reason='selected_option_supported_but_exclusivity_unverified'
                    else:
                        final='gold_consistent';reason='evaluated_gold_claims_supported'
                else:
                    final='unverifiable';reason='no_gold_claims_verified'
                # If radio has a selected purely directional option, topology cannot verify its gold label.
                if typ=='radio' and selected:
                    _,opts=split_options_local(row['query'])
                    if any(k in selected and (not any(x in opts.get(k,'').lower() for x in ['adjacent to','intersect','contain','inside','within'])) for k in opts):
                        if final!='gold_inconsistent': final='unverifiable';reason='selected_radio_answer_pure_direction'
                qcnt[final]+=1
            w.writerow(dict(row,status=final,scope='topology_only_direction_unchecked' if direction else 'non_directional',
                reason=reason,atomic_checks=len(tasks),gold_supported_checks=counts['gold_supported'],
                gold_inconsistent_checks=counts['gold_inconsistent'],
                topology_supported_direction_unchecked=counts['topology_supported_direction_unchecked'],
                unverifiable_checks=counts['unverifiable'],not_applicable_checks=counts['not_applicable'],
                kg_reference_topology_disagreements=counts['kg_reference_topology_disagreements'],
                original_gold_checked=int(not bool(parseerr or gerr))))
    fh.close();ah.close();con.close()
    result={'total_questions':total,'questions':dict(qcnt),'atomic':dict(acnt),
            'closed_world':args.closed_world,
            'interpretation':'gold_inconsistent is a topologically proven answer error; topology_supported_direction_unchecked is NOT a verified correct directional answer; unverified answers are not counted wrong. KG-reference disagreements are separate from answer errors.',
            'warning':'ToposKG is an independent reference with possibly different boundary vintages. Radio options are non-exhaustive without geometric direction verification.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    LOG.info('Done: %s',dict(qcnt))


def split_options_local(text):
    from validate_sparagraph_v2 import split_options
    return split_options(text)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for a in ['questions','kg','mappings','entities']:p.add_argument('--'+a,required=True)
    p.add_argument('--out',default='audit_v3')
    p.add_argument('--closed-world',action='store_true',help='Assume missing reference spatial relation is false (only if complete).')
    p.add_argument('--verbose',action='store_true')
    args=p.parse_args();logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,format='[%(levelname)s] %(message)s')
    run(args)
if __name__=='__main__':main()
