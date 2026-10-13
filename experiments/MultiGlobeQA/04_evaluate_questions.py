#!/usr/bin/env python3
"""Audit factual *topological claims* in MultiGlobeQA questions.

Restricted to (osmh3kg,C), (osmh3kg,E), (worldkg,C).
Uses exact complete geometry for entity pairs when available, plus positive
relation facts in Topos/JEDAI mappings. Never treats a missing mapping as false.
Writes one row per check and a per-question summary, with diagnostics.
"""
import argparse, csv, json, logging, re, sys
from pathlib import Path
from collections import Counter, defaultdict

csv.field_size_limit(sys.maxsize)
L = logging.getLogger('topology-audit')
NT = re.compile(r'^\s*<([^>]*)>\s+<([^>]*)>\s+<([^>]*)>\s*\.\s*$')
SYNTH = re.compile(r'^urn:multiglobeqa:_no:(worldkg|osmh3kg):(.+)$', re.I)
REL = {
    'sfintersects':'intersects', 'intersects':'intersects', 'intersect':'intersects',
    'sfoverlaps':'overlaps','overlaps':'overlaps',
    'sftouches':'touches','touches':'touches', 'adjacentto':'touches',
    'sfdisjoint':'disjoint','disjoint':'disjoint',
    'sfwithin':'within','within':'within', 'ehinside':'within',
    'sfcontains':'contains','contains':'contains','ehcontains':'contains',
    'sfcovers':'covers','covers':'covers','sfcoveredby':'coveredby','coveredby':'coveredby',
    'sfequals':'equals','equals':'equals',
    'hasupperadminunit':'admin_parent'
}
SYMM={'intersects','overlaps','touches','disjoint','equals'}
INV={'contains':'within','within':'contains','covers':'coveredby','coveredby':'covers',
     'admin_parent':'admin_child','admin_child':'admin_parent'}
# Sound entailments between GeoSPARQL simple-features predicates (nonempty geometries).
TRUE_EVIDENCE={
 'intersects': {'intersects','touches','overlaps','contains','within','covers','coveredby','equals'},
 'disjoint':{'disjoint'}, 'overlaps':{'overlaps'}, 'touches':{'touches'},
 'contains':{'contains','equals'},'within':{'within','equals'},
 'covers':{'covers','contains','equals'},'coveredby':{'coveredby','within','equals'},
 'equals':{'equals'}, 'admin_parent':{'admin_parent'}
}
FALSE_EVIDENCE={
 'intersects':{'disjoint'},
 'disjoint':{'intersects','touches','overlaps','contains','within','covers','coveredby','equals'},
 'overlaps':{'disjoint','touches','contains','within','covers','coveredby','equals'},
 'touches':{'disjoint','overlaps','contains','within','equals'},
 'contains':{'disjoint','touches'},'within':{'disjoint','touches'},
 'covers':{'disjoint'},'coveredby':{'disjoint'},'equals':{'disjoint','touches','overlaps'}
}

# Typed template interpretation: A and B in the original dataset are NOT
# always geographic instances (some are category labels). Explicitly handle that.
BOOLEAN_TEMPLATES={
 '13.1':('intersects','a','b'), '14.1':('intersects','a','b'),
 '19.1':('overlaps','a','b'),'20.1':('touches','a','b'),
 '21.1':('touches','a','b'),'22.1':('disjoint','a','b'),
 '23.1':('contains','a','b'),
 '28.1':('admin_parent','a','b'), # A is a subdivision of B
 '31.1':('contains','a','b'),
}

def val(x):
 s=str(x if x is not None else '').strip()
 return '' if s.lower() in ('nan','none','null') else s

def flag(x):
 s=val(x).lower()
 if s in ('true','1','yes'):return True
 if s in ('false','0','no'):return False
 return None

def loc(p):return re.split(r'[/#]',p.rstrip('/'))[-1].lower()

def uri(kg,id):return f'urn:multiglobeqa:_no:{kg}:{id}'

def reverse(r):return r if r in SYMM else INV.get(r)

def load_mappings(path):
 edges=defaultdict(set); stats=Counter(); examples=defaultdict(list)
 with open(path,encoding='utf-8',errors='replace') as f:
  for line in f:
   stats['lines']+=1; m=NT.match(line)
   if not m:
    stats['non_URI_triple']+=1;continue
   s,p,o=m.groups();r=REL.get(loc(p))
   if not r:
    stats['unknown_predicates']+=1
    if len(examples['unknown'])<8:examples['unknown'].append(p)
    continue
   edges[(s,o)].add(r);stats['recognized']+=1;stats['rel_'+r]+=1
   sk,ok=SYNTH.fullmatch(s),SYNTH.fullmatch(o)
   stats['entity_entity' if sk and ok else 'entity_other' if sk or ok else 'other_other']+=1
 return edges,stats,examples

def relations(edges,a,b):
 x=set(edges.get((a,b),set()))
 for r in edges.get((b,a),()):
  t=reverse(r)
  if t:x.add(t)
 return x

def infer(op,rs):
 pos=rs & TRUE_EVIDENCE.get(op,set())
 neg=rs & FALSE_EVIDENCE.get(op,set())
 if pos and neg:return None,'conflicting_mapping_facts',sorted(pos|neg)
 if pos:return True,'topology_mapping',sorted(pos)
 if neg:return False,'topology_mapping',sorted(neg)
 return None,'no_sufficient_direct_mapping',[]

def geometries(paths):
 from shapely import wkt
 out=defaultdict(dict); bad=Counter()
 for path in paths:
  with open(path,encoding='utf-8-sig',newline='') as f:
   for row in csv.DictReader(f):
    k=(val(row.get('source_kg')).lower(),val(row.get('entity_id')))
    s=val(row.get('wkt'))
    if not k[0] or not k[1] or not s:bad['missing_field']+=1;continue
    s=re.sub(r'^<[^>]+>\s*','',s)
    try:
     g=wkt.loads(s)
     if g.is_empty or not g.is_valid:bad['invalid_geometry']+=1;continue
     # Deduplicate exact WKT, but do not quietly select among genuinely distinct geometries.
     out[k][s]=g
    except Exception:bad['WKT_parse_error']+=1
 return out,bad

def geometry_relation(op,a,b,geo):
 ka,kb=a,b
 if ka not in geo or kb not in geo:return None,'missing_geometry_A' if ka not in geo else 'missing_geometry_B',''
 ag=list(geo[ka].values());bg=list(geo[kb].values())
 if len(ag)!=1 or len(bg)!=1:return None,'ambiguous_multiple_geometries',f'geometries_A={len(ag)};geometries_B={len(bg)}'
 g,h=ag[0],bg[0]
 try:
  x={'intersects':g.intersects,'disjoint':g.disjoint,'overlaps':g.overlaps,
     'touches':g.touches,'contains':g.contains,'within':g.within,
     'covers':g.covers,'coveredby':g.covered_by,'equals':g.equals}
  if op not in x:return None,'not_geometry_topology_predicate',''
  return bool(x[op](h)),'exact_complete_wkt',f'A={g.geom_type};B={h.geom_type};DE9IM={g.relate(h)}'
 except Exception as e:return None,'geometry_operation_error',str(e)[:200]

def country_negative(edges,parents,a,b,op):
 """Sound inference only if both entities are WITHIN mapped, disjoint countries."""
 if op not in ('intersects','disjoint','touches','overlaps','contains','within','covers','coveredby','equals'):return None,'',[]
 pa=parents.get(a,());pb=parents.get(b,())
 for ca in pa:
  for cb in pb:
   if ca!=cb and 'disjoint' in relations(edges,ca,cb):
    result=(op=='disjoint')
    return result,'disjoint_containing_countries',[f'{a} within {ca}',f'{b} within {cb}',f'{ca} disjoint {cb}']
 return None,'',[]

def check(row,op,ra,rb,claimed,claim_type,geo,edges,parents,enable_country):
 kg=val(row['kg_source']).lower(); id_a=val(row.get(f'entity_{ra}_id'));id_b=val(row.get(f'entity_{rb}_id'))
 a=uri(kg,id_a) if id_a else '';b=uri(kg,id_b) if id_b else ''
 predicates=sorted(relations(edges,a,b)) if a and b else []
 observed=None; method='';proof=[];diagnostic=''
 if not a or not b:diagnostic='missing_entity_identifier'
 elif op=='admin_parent':
  observed,diagnostic,proof=infer(op,set(predicates));method='explicit_admin_parent_only' if observed is not None else ''
 else:
  observed,diagnostic,detail=geometry_relation(op,(kg,id_a),(kg,id_b),geo)
  if observed is not None:method='complete_geometry';proof=[detail]
  else:
   bymap,why,used=infer(op,set(predicates))
   if bymap is not None:observed=bymap;method='direct_mapping';proof=used;diagnostic=why
   elif enable_country:
    bycountry,why,cproof=country_negative(edges,parents,a,b,op)
    if bycountry is not None:observed=bycountry;method=why;proof=cproof;diagnostic=why
 # Comparison defined only for explicit yes/no gold claims, or affirmative premises.
 if claimed is None:verdict='unverifiable'
 elif observed is None:verdict='unverifiable'
 else:verdict='consistent' if observed==claimed else 'inconsistent'
 return dict(question_id=val(row['question_id']),kg_source=kg,sfid=val(row['sfid']),tid=val(row['tid']),
     question=val(row.get('question')),check_type=claim_type,relation=op,
     entity_a_role=ra,entity_a_id=id_a,entity_a_name=val(row.get(f'entity_{ra}_name')),
     entity_b_role=rb,entity_b_id=id_b,entity_b_name=val(row.get(f'entity_{rb}_name')),
     claimed_value='' if claimed is None else str(claimed).lower(),observed_value='' if observed is None else str(observed).lower(),
     verdict=verdict,evidence_method=method,topos_predicates=';'.join(predicates),
     evidence=json.dumps(proof,ensure_ascii=False),reason=diagnostic,
     gold_truth=val(row.get('ground_truth')),is_true_premise=val(row.get('is_true_premise')))

def build_checks(row,geo,edges,parents,use_country):
 tid=val(row.get('tid')); gt=flag(row.get('ground_truth')) if val(row.get('ground_truth_type')).lower()=='boolean' else None
 checks=[]
 if tid in BOOLEAN_TEMPLATES:
  op,a,b=BOOLEAN_TEMPLATES[tid]
  # For administrative parent: A is subdivision of B => A has parent B.
  checks.append(check(row,op,a,b,gt,'gold_relation',geo,edges,parents,use_country))
 elif tid=='15.1':
  # An intersection-point count > 0 entails intersection; zero is not equivalent
  # to disjointness (lines/polygons can intersect without isolated points).
  try:
   n=float(val(row.get('ground_truth')))
  except ValueError:
   n=0
  if n>0:
   checks.append(check(row,'intersects','a','b',True,'positive_intersection_count_entailment',geo,edges,parents,use_country))
 elif tid.startswith('32.'):
  # The gold-labelled relation is A contains B.
  checks.append(check(row,'contains','a','b',gt,'gold_relation',geo,edges,parents,use_country))
  # 'B of C' in natural-language question is a contextual location/premise;
  # this is NOT independently asserted administrative membership.
  checks.append(check(row,'within','b','c',True,'contextual_containment_premise',geo,edges,parents,use_country))
 elif tid=='18.1':
  # Answer is an enumeration. No entity A ID for the class 'highways'.
  # The question only sets an intersect B and not intersect C filter, not a claim that B,C intersect.
  pass
 # The remaining aggregate/template cases do not entail a specific A-B topological
 # fact merely from a nonzero count or an unprovided candidate set.
 return checks

def write_csv(path,rows,columns):
 with open(path,'w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--questions',required=True);p.add_argument('--entity-geometries',action='append',required=True)
 p.add_argument('--mappings',required=True);p.add_argument('--out-dir',required=True)
 p.add_argument('--log-every',type=int,default=100);p.add_argument('--verbose-questions',action='store_true')
 p.add_argument('--disable-country-inference',action='store_true')
 args=p.parse_args();logging.basicConfig(level=logging.INFO,format='[%(asctime)s] %(levelname)s %(message)s')
 out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
 geo,bad=geometries(args.entity_geometries)
 edges,ms,examples=load_mappings(args.mappings)
 L.info('Loaded geometries: %s entities; invalid rows=%s',len(geo),dict(bad))
 L.info('Mappings: %s; relation examples=%s',dict(ms),dict(examples))
 L.info('Mappings pairs=%d; synthetic pair triples=%d. No mapping is treated as negative evidence.',len(edges),ms['entity_entity'])
 parents=defaultdict(set)
 for (subject,obj),relationset in edges.items():
  if 'within' in relationset:parents[subject].add(obj)
  if 'contains' in relationset:parents[obj].add(subject)
 L.info('Indexed %d mapped entities with parent/containing-area candidates',len(parents))
 questions=[];claims=[];tally=Counter();rationale=Counter()
 with open(args.questions,encoding='utf-8-sig',newline='') as f:
  for row in csv.DictReader(f):
   kg=val(row.get('kg_source')).lower();sf=val(row.get('sfid'))
   if not ((kg=='osmh3kg' and sf in ('C','E')) or (kg=='worldkg' and sf=='C')):continue
   audits=build_checks(row,geo,edges,parents,not args.disable_country_inference)
   claims.extend(audits)
   inconsistent=[x for x in audits if x['verdict']=='inconsistent']
   verified=[x for x in audits if x['verdict']=='consistent']
   # Don't report the whole question as validated unless every check was verifiable;
   # and do not invent a topology error when no explicit binary claim is present.
   result='inconsistent' if inconsistent else 'consistent' if audits and len(verified)==len(audits) else 'unverifiable'
   explanation='; '.join(f"{x['check_type']}:{x['relation']}={x['verdict']}({x['reason']})" for x in audits) or 'no_explicit_checkable_entity_pair_or_aggregate_only'
   rec={'question_id':val(row['question_id']),'kg_source':kg,'sfid':sf,'tid':val(row.get('tid')),
        'question':val(row.get('question')),'ground_truth':val(row.get('ground_truth')),
        'is_true_premise':val(row.get('is_true_premise')),
        'entity_a_id':val(row.get('entity_a_id')),'entity_b_id':val(row.get('entity_b_id')),'entity_c_id':val(row.get('entity_c_id')),
        'checks':len(audits),'consistent_checks':len(verified),'inconsistent_checks':len(inconsistent),
        'unverifiable_checks':sum(x['verdict']=='unverifiable' for x in audits),
        'verdict':result,'details':explanation}
   questions.append(rec);tally[(kg,sf,result)]+=1;rationale[explanation if not audits else result]+=1
   if args.verbose_questions or (args.log_every and len(questions)%args.log_every==0):
    L.info('[%d] KG=%s SF=%s tid=%s Q=%s verdict=%s checks=%d; %s',len(questions),kg,sf,rec['tid'],rec['question_id'],result,len(audits),explanation[:400])
 fields=list(questions[0]) if questions else []
 cfields=list(claims[0]) if claims else []
 write_csv(out/'question_evaluation.csv',questions,fields)
 write_csv(out/'claim_evaluation.csv',claims,cfields)
 write_csv(out/'verified_inconsistencies.csv',[r for r in questions if r['verdict']=='inconsistent'],fields)
 write_csv(out/'unverifiable_questions.csv',[r for r in questions if r['verdict']=='unverifiable'],fields)
 with open(out/'evaluation_summary.csv','w',encoding='utf-8',newline='') as f:
  w=csv.writer(f);w.writerow(['kg_source','sfid','verdict','questions']);w.writerows([*key,count] for key,count in sorted(tally.items()))
 diagnostics={'total_questions':len(questions),'total_checks':len(claims),'outcomes':dict(Counter(q['verdict'] for q in questions)),
              'check_outcomes':dict(Counter(c['verdict'] for c in claims)),'geometries':len(geo),
              'bad_geometry_rows':dict(bad),'mapping_stats':dict(ms),'mapping_samples':dict(examples),
              'no_check_templates':dict(Counter(q['tid'] for q in questions if not q['checks']))}
 (out/'diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding='utf-8')
 L.info('FINISHED: %d questions, %d checks; question verdicts=%s',len(questions),len(claims),diagnostics['outcomes'])
 L.info('Outputs in %s',out)
if __name__=='__main__': main()

