#!/usr/bin/env python3
"""Extract MultiGlobeQA questions involving spatial/topological relationships.

Core: B (metric containment), C (topological relations), E (containment/hierarchy).
Extended: H (grid containment), I (spatio-temporal; spatial-overlap subset),
          L (uncertain containment subset), D (crossings subset).
This is a *question selection*, not validation of factual correctness.
"""
import argparse
from pathlib import Path
import pandas as pd

FAMILIES = {
    'B': 'Metric containment',
    'C': 'Topological relationships',
    'E': 'Containment and administrative hierarchy',
    'H': 'Grid and spatial indexing',
    'I': 'Spatio-temporal events',
    'L': 'Uncertainty and fuzzy reasoning',
    'D': 'Network and path-based reasoning',
}
# More precise classification by stable family; avoid guessing subfunction via tid.
CORE = {'B', 'C', 'E'}
EXTENDED = {'H', 'I', 'L', 'D'}
PATTERNS = {
    'B': ('containment', 'contains / within'),
    'C': ('topological_relation', 'intersection / overlap / adjacency / disjointness / enclosure'),
    'E': ('administrative_containment', 'administrative membership / full containment'),
    'H': ('grid_containment', 'grid-based spatial containment / indexing'),
    'I': ('spatiotemporal_spatial_relation', 'spatio-temporal spatial relations (review)'),
    'L': ('fuzzy_containment', 'probabilistic / vague spatial relations (review)'),
    'D': ('network_crossing', 'path crossing / connection (review)'),
}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input-dir', default='data/raw/questions/eng/large', help='Folder with 4 Parquet shards')
    ap.add_argument('--out', default='results/multiglobeqa_topology_questions.csv')
    ap.add_argument('--summary', default='results/multiglobeqa_topology_summary.csv')
    ap.add_argument('--scope', choices=('core','extended'), default='core',
                    help='core=B,C,E; extended includes H,I,L,D as potential cases requiring review')
    ap.add_argument('--exclude-false-premises', action='store_true',
                    help='Exclude intentionally false-premise questions')
    args = ap.parse_args()
    src=Path(args.input_dir)
    paths=sorted(src.glob('*.parquet'))
    if not paths:
        ap.error(f'No Parquet files found in {src}. Specify --input-dir.')
    chunks=[]
    for path in paths:
        df=pd.read_parquet(path)
        if 'sfid' not in df.columns:
            raise ValueError(f'{path.name}: missing required sfid column; columns={list(df.columns)}')
        if 'question' not in df.columns:
            raise ValueError(f'{path.name}: missing required question column')
        df['source_file']=path.name
        if 'kg_source' not in df.columns:
            df['kg_source']=path.stem
        chunks.append(df)
        print(f'Read {path.name}: {len(df):,} rows')
    allq=pd.concat(chunks,ignore_index=True)
    allq['sfid']=allq['sfid'].astype('string').str.strip().str.upper()
    families=CORE if args.scope=='core' else CORE|EXTENDED
    selected=allq[allq['sfid'].isin(families)].copy()
    if args.exclude_false_premises and 'is_true_premise' in selected:
        selected=selected[selected['is_true_premise'].eq(True)].copy()
    selected['topology_category']=selected['sfid'].map(lambda x: PATTERNS[x][0])
    selected['topology_relation']=selected['sfid'].map(lambda x: PATTERNS[x][1])
    selected['selection_scope']=selected['sfid'].map(lambda x: 'core' if x in CORE else 'extended_review')
    selected['spatial_family']=selected['sfid'].map(FAMILIES)
    selected['verified_inconsistency']=pd.NA
    # Do not deduplicate by question_id alone: IDs from different shards can conflict.
    key=[c for c in ('kg_source','question_id','is_multimodal') if c in selected]
    if key:
        dup=selected.duplicated(subset=key).sum()
        if dup:
            print(f'Warning: {dup:,} duplicate rows on {key}; dropping duplicates')
            selected=selected.drop_duplicates(subset=key)
    lead=['question_id','kg_source','sfid','spatial_family','topology_category',
          'topology_relation','selection_scope','tid','vid','question','base_template',
          'ground_truth','ground_truth_type','is_true_premise','entity_a_id','entity_a_name',
          'entity_b_id','entity_b_name','entity_c_id','entity_c_name','source_file','verified_inconsistency']
    cols=[c for c in lead if c in selected.columns] + [c for c in selected.columns if c not in lead]
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    selected[cols].to_csv(output,index=False,encoding='utf-8',na_rep='')
    group=['kg_source','sfid','spatial_family','topology_category','selection_scope']
    if 'is_true_premise' in selected.columns:
        group.append('is_true_premise')
    summary=selected.groupby(group,dropna=False).size().reset_index(name='questions')
    sum_path=Path(args.summary);sum_path.parent.mkdir(parents=True,exist_ok=True)
    summary.to_csv(sum_path,index=False)
    print(f'All questions: {len(allq):,}')
    print(f'Selected questions ({args.scope}): {len(selected):,} ({len(selected)/len(allq)*100:.2f}%)')
    print(f'By source / family:\n{selected.groupby(["kg_source","sfid"]).size().to_string()}')
    print(f'CSV: {output}\nSummary: {sum_path}')

if __name__=='__main__':
    main()

