#!/usr/bin/env python3
"""Filter selected MultiGlobeQA question families and export entity/country indexes.
No country is guessed from an unqualified place name. Blank means unknown.
"""
import argparse
import csv
import re
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd

ALLOWED = {('kwg','E'), ('osmh3kg','C'), ('osmh3kg','E'), ('worldkg','C')}
ROLES = ('a','b','c','d')
FIELDS = ['question_row_id','question_id','kg_source','sfid','tid','question','entity_role',
          'entity_id','entity_name','country','country_iso3','country_evidence']


def clean(value):
    return str(value).strip() if value is not None else ''


def country_for(kg, entity_id):
    # KG-specific, semantically explicit IDs. KWG admin/ZIP identifiers belong to USA.
    if kg == 'kwg' and (entity_id.startswith('administrativeRegion.USA.') or
                        entity_id.startswith('zipCodeArea.')):
        return 'United States', 'USA', 'explicit_kg_entity_id'
    return '', '', 'not_established_from_input'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default='multiglobeqa_topology_questions.csv')
    ap.add_argument('--out-dir', default='results/multiglobeqa_selected')
    args = ap.parse_args()
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    questions_dir = out/'per_question'; questions_dir.mkdir(exist_ok=True)
    df = pd.read_csv(args.input, dtype=str, keep_default_na=False)
    required = ['question_id','kg_source','sfid','question']
    missing = [k for k in required if k not in df]
    if missing: raise ValueError(f'Missing columns: {missing}')
    selected = df.loc[[ (clean(a).lower(),clean(b).upper()) in ALLOWED for a,b in zip(df.kg_source,df.sfid) ]].copy().reset_index(drop=True)
    selected.insert(0, 'question_row_id', [f'q{i:06d}' for i in range(1, len(selected)+1)])
    selected.to_csv(out/'selected_questions.csv', index=False)
    rows=[]; per_question={}; missing_id_mentions=[]
    for _,q in selected.iterrows():
        qrows=[]
        for role in ROLES:
            eid=clean(q.get(f'entity_{role}_id',''))
            name=clean(q.get(f'entity_{role}_name',''))
            if not eid:
                if name: missing_id_mentions.append({'question_row_id':q.question_row_id,'question_id':q.question_id,'kg_source':q.kg_source,'sfid':q.sfid,'entity_role':role,'entity_name':name,'reason':'no_entity_identifier; often a class/category rather than a specific entity'})
                continue
            country,iso,evidence=country_for(q.kg_source,eid)
            item={'question_row_id':q.question_row_id,'question_id':q.question_id,'kg_source':q.kg_source,'sfid':q.sfid,'tid':q.get('tid',''),
                  'question':q.question,'entity_role':role,'entity_id':eid,'entity_name':name,
                  'country':country,'country_iso3':iso,'country_evidence':evidence}
            rows.append(item); qrows.append(item)
        per_question[q.question_row_id]=qrows
    all_questions_entities=pd.DataFrame(rows,columns=FIELDS)
    all_questions_entities.to_csv(out/'question_entities.csv',index=False)
    if rows:
        unique_entities=(all_questions_entities.drop_duplicates(subset=['kg_source','entity_id'])
                         [['kg_source','entity_id','entity_name','country','country_iso3','country_evidence']]
                         .sort_values(['kg_source','entity_id']))
    else: unique_entities=pd.DataFrame(columns=['kg_source','entity_id','entity_name','country','country_iso3','country_evidence'])
    unique_entities.to_csv(out/'unique_entities.csv', index=False)
    pd.DataFrame(missing_id_mentions,columns=['question_row_id','question_id','kg_source','sfid','entity_role','entity_name','reason']).to_csv(out/'mentions_without_entity_id.csv',index=False)
    # Single ZIP avoids placing thousands of individual CSVs in the main output directory.
    with zipfile.ZipFile(out/'per_question_entities.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zf:
        from io import StringIO
        for rowid, qrows in per_question.items():
            buf=StringIO(); writer=csv.DictWriter(buf,fieldnames=FIELDS);writer.writeheader();writer.writerows(qrows)
            zf.writestr(f'per_question/{rowid}.csv',buf.getvalue())
    summary=selected.groupby(['kg_source','sfid']).size().reset_index(name='questions')
    summary.to_csv(out/'class_counts.csv',index=False)
    print(summary.to_string(index=False));print(f'Questions: {len(selected):,}');print(f'Entity mentions: {len(rows):,}');print(f'Unique entities: {len(unique_entities):,}')
    print(f'Known country entities: {(unique_entities.country != "").sum():,}')
    print(f'Unresolved country entities: {(unique_entities.country == "").sum():,}')
    print(f'Mentions without entity IDs (separate audit): {len(missing_id_mentions):,}')
    print('Output directory:',out)
if __name__=='__main__':main()
