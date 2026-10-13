#!/usr/bin/env python3
"""Extract complete GeoSPARQL geometries for target entities from RDF-triple Parquet parts.
Creates entity_geometries.nt with synthetic `_no` subjects used by the supplied materializer.
"""
import argparse,csv,json,re,sys
from pathlib import Path
from collections import defaultdict
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

GEO='http://www.opengis.net/ont/geosparql#'
IRI=re.compile(r'^<?(https?://[^<> ]+|urn:[^<> ]+)>?$')
WKT_RE=re.compile(r'(?is)^(?:<[^>]+>\s*)?(POINT|MULTIPOINT|LINESTRING|MULTILINESTRING|POLYGON|MULTIPOLYGON|GEOMETRYCOLLECTION)\s*(?:Z|M|ZM)?\s*\(')

def clean(v):return str(v or '').strip().strip('<>')
def tail(v):
 v=clean(v);return re.split(r'[/#]',v)[-1]
def ident(v):
 s=tail(v);m=re.fullmatch(r'(?:geo|node|way|relation)?([0-9]+)',s,flags=re.I)
 return m.group(1) if m else s

def parse_wkt(v):
 s=str(v or '').strip()
 if s.startswith('"') and '^^' in s:
  s=s[1:s.rfind('"^^')].replace('\\"','"')
 crs=re.match(r'^<([^>]+)>\s*',s)
 if crs:
  if crs.group(1) not in ('http://www.opengis.net/def/crs/EPSG/0/4326','http://www.opengis.net/def/crs/OGC/1.3/CRS84'):
   return None  # Unsupported CRS: never silently treat projected coordinates as lon/lat.
  s=s[crs.end():]
 if WKT_RE.match(s) and s.count('(')==s.count(')'):return s
 return None

def lit(s):return '"'+str(s).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')+'"'

def scan(parquets, ids, targets=None,batch_size=200000):
 """Arrow filtering on normalized URI local part, never converts whole batches to Python."""
 ids_array=pa.array(sorted(ids),type=pa.string())
 targets_array=pa.array(sorted(targets),type=pa.string()) if targets is not None else None
 target_local_array=pa.array(sorted({tail(x) for x in targets}),type=pa.string()) if targets is not None else None
 for fn in parquets:
  pf=pq.ParquetFile(fn);cols=pf.schema_arrow.names
  lower={c.lower():c for c in cols}
  if not all(k in lower for k in ('subject','predicate','object')):print('[SKIP schema]',fn,cols,file=sys.stderr);continue
  names=[lower[k] for k in ('subject','predicate','object')]
  total=0;matched=0
  for batch in pf.iter_batches(batch_size=batch_size,columns=names):
   subj=pc.cast(batch.column(0),pa.string()); local=pc.replace_substring_regex(subj,r'^.*[/#]','')
   numeric=pc.replace_substring_regex(local,r'^(?:geo|node|way|relation)(?=\d)', '') if False else pc.replace_substring_regex(local,r'^(geo|node|way|relation)([0-9]+)$',r'\2')
   mask=pc.is_in(numeric,value_set=ids_array)
   if targets is not None: # candidate full URI/local geometry nodes, not numeric IDs alone
    mask=pc.or_(mask,pc.is_in(subj,value_set=targets_array))
    mask=pc.or_(mask,pc.is_in(local,value_set=target_local_array))
   matched_batch=pc.filter(batch,mask)
   total+=batch.num_rows;matched+=matched_batch.num_rows
   for row in matched_batch.to_pylist():yield row[names[0]],row[names[1]],row[names[2]]
  print(f'[SCAN] {fn.name}: {total:,} rows, {matched:,} selected',flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--kg-source',choices=['worldkg','osmh3kg'],required=True);p.add_argument('--parquet-dir',required=True);p.add_argument('--entities',required=True);p.add_argument('--out-dir',required=True);p.add_argument('--batch-size',type=int,default=250000);p.add_argument('--max-wkt-length',type=int,default=0,help='0 means complete WKT, recommended');a=p.parse_args()
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 target={}
 with open(a.entities,encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   if r['source_kg'].lower()==a.kg_source:target[str(r['entity_id']).strip()]=r
 parquets=sorted(Path(a.parquet_dir).rglob('*.parquet'))
 if not parquets: p.error('No Parquet files found')
 ids=set(target);properties=defaultdict(list);geometry_links=defaultdict(set); geom_nodes=set();subjects=defaultdict(set)
 print('Targets:',len(ids),'Parquet parts:',len(parquets),'first pass...',flush=True)
 for s,pred,obj in scan(parquets,ids,batch_size=a.batch_size):
  k=ident(s)
  if k not in ids:continue
  subjects[k].add(clean(s)); pr=tail(pred).casefold(); value=clean(obj)
  if pr in ('hasgeometry','spatialobject','hasdefaultgeometry','hascentroid','geometry','geom'):
   geometry_links[k].add(value);geom_nodes.add(value)
  elif pr in ('aswkt','wkt','geometrywkt','wktliteral') or 'wkt' in pr:
   w=parse_wkt(obj)
   if w:properties[k].append((s,w,'direct'))
 print('Matched entity IDs:',len(subjects),'linked geometry nodes:',len(geom_nodes),flush=True)
 if geom_nodes:
  print('Second pass: resolving linked geometry nodes...',flush=True)
  # Map geom node aliases to owner entities; guard against collisions by retaining all owners.
  owners=defaultdict(set)
  for entity,refs in geometry_links.items():
   for ref in refs:owners[clean(ref)].add(entity);owners[tail(ref)].add(entity)
  for s,pred,obj in scan(parquets,set(),targets=geom_nodes,batch_size=a.batch_size):
   if 'wkt' not in tail(pred).lower():continue
   w=parse_wkt(obj)
   if not w:continue
   for entity in owners.get(clean(s),set())|owners.get(tail(s),set()):properties[entity].append((s,w,'linked'))
 nt=out/'entity_geometries.nt'; geom_csv=out/'entity_geometries.csv'; aliases=out/'entity_uri_mapping.csv'
 with nt.open('w',encoding='utf-8') as nf,geom_csv.open('w',encoding='utf-8',newline='') as cf,aliases.open('w',encoding='utf-8',newline='') as af:
  cw=csv.writer(cf);cw.writerow(['source_kg','entity_id','entity_name','country','source_subject','geometry_subject','wkt','wkt_source','synthetic_uri'])
  aw=csv.writer(af);aw.writerow(['source_kg','entity_id','source_subject','synthetic_uri'])
  for entity,r in target.items():
   synth=f'urn:multiglobeqa:_no:{a.kg_source}:{entity}'
   for orig in sorted(subjects.get(entity,[])):aw.writerow([a.kg_source,entity,orig,synth])
   for j,(orig,w,how) in enumerate(properties.get(entity,[])):
    if a.max_wkt_length and len(w)>a.max_wkt_length:continue
    geouri=f'urn:multiglobeqa:geometry:{a.kg_source}:{entity}:{j}'
    nf.write(f'<{synth}> <{GEO}hasGeometry> <{geouri}> .\n')
    nf.write(f'<{geouri}> <{GEO}asWKT> {lit(w)}^^<{GEO}wktLiteral> .\n')
    cw.writerow([a.kg_source,entity,r.get('name',''),r.get('country',''),';'.join(sorted(subjects.get(entity,[]))),str(orig),w,how,synth])
 missing=[k for k in target if not properties.get(k)]
 (out/'missing_geometry_ids.txt').write_text('\n'.join(missing)+'\n')
 print('Geometry entities:',len(target)-len(missing),'missing:',len(missing));print('Output:',nt)
if __name__=='__main__':main()
