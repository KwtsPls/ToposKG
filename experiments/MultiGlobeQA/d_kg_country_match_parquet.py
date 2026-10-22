#!/usr/bin/env python3
"""Parquet-native MultiGlobeQA KG → benchmark entity country matching / human review.

Inputs: Parquet partitions with subject,predicate,object columns (alternative s,p,o),
        benchmark unique_entities.csv (kg_source,entity_id,entity_name).
Outputs: worldkg_country_matches.csv, worldkg_review.csv,
         worldkg_entity_triples.csv, worldkg_question_entities.csv (optional),
         worldkg_stats.csv.

Country evidence priority: exact explicit addrCountry > point-in-polygon with
user-provided country boundaries > no verified country. Existing name-inferred
candidates are retained for review only, not promoted to verified facts.
"""
import argparse
import csv
import json
import re
import sys
import time
import multiprocessing as mp

# pyarrow is imported lazily within workers to avoid unnecessary parent overhead.
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

COUNTRY_PRED = {'addrcountry', 'country', 'countrycode', 'isocountrycode', 'isocode', 'iso31661alpha2', 'iso31661alpha3', 'hascountry', 'locatedincountry', 'isincountry', 'isincountrycode', 'iso31661', 'iso31661alpha2', 'iso31661alpha3', 'eeacddaparentiso'}
NAME_PRED = {'label','name','nameen','officialname','altname','nameenglish','shortname'}
LINK_PRED = {'sameas','wikidata','wikidataid','wikidataurl','osmlink','wikipedialink','wikipedia','wikipediaurl','url'}
TYPE_PRED = {'type','subclassof'}
GEO_LINK = {'spatialobject','hasgeometry','geometry','location'}
GEO_LIT = {'aswkt','wkt','geoaswkt','longitude','latitude','lat','lon','long','coordinate','coordinates'}
OTHER = {'administrativeparent','h3index','h3cell','hasadminunit','hasupperadminunit','sfwithin','sfcontains','parentregion','inregion','containedin','adminunit','county','statecode','countryname','addrstate','addrcity','addrprovince','addrdistrict','addrpostcode','addrstreet',
         'state','province','city','district','region','adminlevel','ispartof','partof',
         'locatedin','within','contains','parent','boundary','place','population','isinstate','isinstatecode','isinprovince','isincity','isincounty','isindistrict','isinmunicipality','isintown','isinsubprovince','isinprefecture','isinstate','isinstatecode','isiniso31662','iso31662','bordertype','leftcountry','rightcountry','objectcountry','admintypemg','admintypeph','addrmunicipality','addrfull'}
PICK = COUNTRY_PRED | NAME_PRED | LINK_PRED | TYPE_PRED | GEO_LINK | GEO_LIT | OTHER
WKT_RE = re.compile(r'(?:<[^>]+>\s*)?POINT\s*(?:Z\s*)?\(\s*([-+\d.eE]+)\s+([-+\d.eE]+)', re.I)


def clean(v):
    if v is None: return ''
    v = str(v).strip()
    if v.startswith('<') and v.endswith('>'): v = v[1:-1]
    if v.startswith('"'):
        match = re.match(r'^"((?:[^"\\]|\\.)*)"(?:@[-\w]+|\^\^<?[^>]+>?)?$', v, flags=re.S)
        if match:
            v = match.group(1).replace('\\"','"').replace('\\n',' ').replace('\\t',' ')
    return v


def local(uri):
    uri = clean(uri).rstrip('/#')
    return unquote(re.split(r'[/#]', uri)[-1])


def norm_pred(p):
    return re.sub(r'[^a-z0-9]', '', local(p).lower())


def as_id(v):
    s=clean(v)
    if not s: return ''
    return local(s) if '/' in s or '#' in s else s


def subject_matches(sub, ids):
    s=clean(sub)
    candidates = [s, as_id(s)]
    # WorldKG wkg:<OSM node ID> is common; only compare the resource-local
    # identifier, never substring matches that could create collisions.
    candidates.append(re.sub(r'^(?:node|way|relation|osm_|osm)', '', as_id(s), flags=re.I))
    return next((c for c in candidates if c in ids), None)


def parquet_stream(path, phase, progress=1000000, batch_size=250000):
    """Yield only matching RDF triples; all-row matching runs inside Arrow native kernels."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(path)
    names = list(pf.schema_arrow.names)
    def locate(options):
        for name in names:
            if re.sub(r'[^a-z0-9]', '', name.lower()) in options:
                return name
        return None
    sc = locate({'subject','s','subj','entity','source','subjecturi'})
    pp = locate({'predicate','p','pred','property','relation'})
    oo = locate({'object','o','obj','value','target'})
    if not all([sc,pp,oo]):
        raise ValueError(f'{path}: cannot find RDF s/p/o columns; found {names}. '
                         'Use --subject-column, --predicate-column, --object-column to override.')
    return pf, (sc,pp,oo)


def _coerce_text(x):
    import pyarrow.compute as pc
    import pyarrow as pa
    if pa.types.is_string(x.type) or pa.types.is_large_string(x.type):
        return x
    return pc.cast(x, pa.string(), safe=False)


def _uri_suffix(x):
    """Get URI local part using a compiled Arrow kernel (not per-row Python regex)."""
    import pyarrow.compute as pc
    # Handles angle-bracket-wrapped URIs and plain URLs.
    x = pc.replace_substring_regex(x, pattern=r'>$', replacement='')
    return pc.extract_regex(x, r'(?P<suffix>[^/#<>]+)$').field('suffix')


def _mask_match_subject(sub, phase):
    import pyarrow.compute as pc
    import pyarrow as pa
    if phase == 1:
        suffix = _uri_suffix(sub)
        ids = pc.is_in(suffix, value_set=pa.array(list(_TARGET_IDS), type=pa.string()))
        # Only interpret 'node123' / 'way123' etc. when a target ID has this numeric value.
        stripped = pc.replace_substring_regex(suffix, r'^(?:node|way|relation|osm_|osm)', '')
        prefixed = pc.is_in(stripped, value_set=pa.array(list(_TARGET_IDS), type=pa.string()))
        mask = pc.or_kleene(ids, prefixed)
        return pc.fill_null(mask, False)
    # Linked geometry resources require exact full URI matching, with optional brackets.
    values = pa.array(list(_GEO_TARGETS), type=pa.string())
    norm_sub = pc.replace_substring_regex(sub, r'^<|>$', '')
    mask = pc.is_in(norm_sub, value_set=values)
    return pc.fill_null(mask, False)


def files_under(path):
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(p)
    return sorted([p] if p.is_file() else p.rglob('*.parquet'))


# Worker-side matching: use URI-local equality and avoid
# regex normalization for the overwhelming majority of nonmatching triples.
_TARGET_IDS = frozenset()
_GEO_TARGETS = {}
_PROGRESS = 0
_KG_SOURCE = 'worldkg'

def _init_workers(ids, geo, progress, kg_source):
    global _TARGET_IDS, _GEO_TARGETS, _PROGRESS, _KG_SOURCE
    _TARGET_IDS = frozenset(ids)
    _GEO_TARGETS = geo
    _PROGRESS = progress
    _KG_SOURCE = kg_source

def _match_fast(subject):
    x = subject.strip().strip('<>')
    suffix = x.rsplit('/', 1)[-1].rsplit('#', 1)[-1]
    if suffix in _TARGET_IDS:
        return suffix
    # Alternative OSM-style resource prefixes; only exact IDs accepted.
    if _KG_SOURCE == 'worldkg':
        for prefix in ('node', 'way', 'relation', 'osm_', 'osm'):
            if suffix.startswith(prefix) and suffix[len(prefix):] in _TARGET_IDS:
                return suffix[len(prefix):]
    return None

def _scan_partition(task):
    phase, path, batch_size, progress = task
    import pyarrow as pa
    import pyarrow.compute as pc
    pf, columns = parquet_stream(Path(path), phase, progress, batch_size)
    rows = hits = 0
    kept, links, subjects = [], [], {}
    start = time.monotonic()
    arrow_ids = pa.array(list(_TARGET_IDS), type=pa.string())
    arrow_geos = pa.array(list(_GEO_TARGETS), type=pa.string())
    for batch in pf.iter_batches(batch_size=batch_size, columns=list(columns), use_threads=False):
        rows += batch.num_rows
        sub = _coerce_text(batch.column(0))
        if phase == 1:
            suffix = _uri_suffix(sub)
            exact = pc.is_in(suffix, value_set=arrow_ids)
            if _KG_SOURCE == 'worldkg':
                stripped = pc.replace_substring_regex(suffix, r'^(?:node|way|relation|osm_|osm)', '')
                prefixed = pc.is_in(stripped, value_set=arrow_ids)
                mask = pc.fill_null(pc.or_kleene(exact,prefixed), False)
            else:
                mask = pc.fill_null(exact, False)
        else:
            normalized = pc.replace_substring_regex(sub, r'^<|>$', '')
            suffix = _uri_suffix(sub)
            mask = pc.fill_null(pc.or_kleene(
                pc.is_in(normalized,value_set=arrow_geos),
                pc.is_in(suffix,value_set=arrow_geos)),False)
        if pc.sum(pc.cast(mask, pa.int64())).as_py() == 0:
            if progress and rows % progress < batch.num_rows:
                print(f'[worker {phase}] {Path(path).name}: scanned {rows:,} rows, {hits:,} matches',flush=True)
            continue
        filtered = batch.filter(mask)
        selected = filtered.to_pydict()
        s_vals, p_vals, o_vals = [selected[c] for c in columns]
        for s,p,o in zip(s_vals,p_vals,o_vals):
            if s is None or p is None:continue
            if phase == 1:
                eid = _match_fast(str(s))
                if eid is None:continue
                hits += 1
                subjects.setdefault(eid,clean(s))
                pred = norm_pred(str(p))
                if pred not in PICK: continue
                value = clean(o)
                kept.append((eid,pred,value[:12000]))
                if pred in GEO_LINK and value:
                    links.append((eid,value.strip('<>')))
            else:
                clean_sub = clean(s)
                refs = _GEO_TARGETS.get(clean_sub)
                if refs is None:
                    refs = _GEO_TARGETS.get(local(clean_sub))
                if refs is None:continue
                pred = norm_pred(str(p))
                if pred in GEO_LIT or pred in TYPE_PRED:
                    value = clean(o)
                    for eid in refs:kept.append((eid,'geometry_'+pred,value[:12000]))
                    hits+=1
        if progress and rows % progress < batch.num_rows:
            print(f'[worker {phase}] {Path(path).name}: scanned {rows:,} rows, {hits:,} matches',flush=True)
    return (str(path),rows,hits,kept,links,subjects,time.monotonic()-start)


def _parallel_scan(paths, phase, ids, geo, workers, progress, batch_size, kg_source):
    tasks = ((phase, str(p), batch_size, progress) for p in paths)
    with mp.Pool(processes=workers, initializer=_init_workers,
                 initargs=(tuple(ids),geo,progress,kg_source)) as pool:
        for result in pool.imap_unordered(_scan_partition,tasks,chunksize=1):
            yield result


def pycountry_resolve(value):
    try: import pycountry
    except ImportError: return ('','','no_pycountry')
    val=clean(value).strip(' "')
    if not val: return ('','','empty')
    # Wikidata/OSM IRIs are not country names; don't misidentify them.
    if '://' in val: return ('','','unresolved_uri')
    alias={'UK':'GBR','Great Britain':'GBR','England':'GBR','Scotland':'GBR',
           'United States of America':'USA','USA':'USA','US':'USA',
           'South Korea':'KOR','North Korea':'PRK','Russia':'RUS',
           'Vietnam':'VNM','Türkiye':'TUR','Turkey':'TUR',
           'Czech Republic':'CZE','Iran':'IRN','Bolivia':'BOL',
           'Taiwan':'TWN','Kosovo':'XKX'}
    key=alias.get(val, val)
    if key=='XKX':return ('Kosovo','XKX','alias')
    try:
        c=pycountry.countries.lookup(key)
        return (c.name,c.alpha_3,'explicit_value')
    except LookupError:return ('','','unknown_country_literal')


def country_polygons(path):
    if not path: return []
    try: from shapely.geometry import shape
    except ImportError: raise SystemExit('Install shapely for --countries-geojson')
    import json
    with open(path, encoding='utf-8') as f: obj=json.load(f)
    polys=[]
    for feat in obj.get('features',[]):
        props=feat.get('properties') or {}
        val=next((str(props[k]) for k in ('ADMIN','NAME','name','NAME_EN','SOVEREIGNT','ISO_A3','ADM0_A3','iso_a3') if props.get(k) and props[k]!='-99'), '')
        if not val or not feat.get('geometry'):continue
        g=shape(feat['geometry'])
        if not g.is_empty:polys.append((g, val))
    return polys


def point_from(values):
    for pred, value in values:
        if pred in GEO_LIT:
            m=WKT_RE.search(value)
            if m:
                try: return float(m[1]),float(m[2]),'WKT_POINT'
                except ValueError:pass
    kv={p:v for p,v in values}
    try:
        lon=float(kv.get('longitude') or kv.get('lon') or kv.get('long') or '')
        lat=float(kv.get('latitude') or kv.get('lat') or '')
        return lon,lat,'lat_lon_fields'
    except ValueError:return None


def polygon_country(lon,lat,polys):
    from shapely.geometry import Point
    if abs(lon)>180 or abs(lat)>90:return ('','','coordinate_out_of_range')
    p=Point(lon,lat)
    matches=[]
    for shape,name in polys:
        if shape.covers(p):
            cname,iso,_=pycountry_resolve(name)
            if cname:matches.append((cname,iso))
    if len(matches)==1:return (*matches[0],'boundary_point_in_polygon')
    if len(matches)>1:return ('','','multiple_boundary_matches')
    return ('','','no_boundary_match')


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--kg-dir',required=True,help='RDF-triple Parquet directory (recursive)')
    ap.add_argument('--kg-source', choices=['worldkg','osmh3kg','kwg'], required=True,
                    help='Benchmark source KG; filters entity input and names output files')
    ap.add_argument('--entities',required=True,help='unique_entities.csv from previous extraction')
    ap.add_argument('--question-entities',help='Optional question_entities.csv to enrich')
    ap.add_argument('--out-dir',default=None)
    ap.add_argument('--countries-geojson',help='Optional country polygon GeoJSON (EPSG:4326) for point location')
    ap.add_argument('--progress',type=int,default=1000000,help='Log progress every N rows')
    ap.add_argument('--max-review-triples',type=int,default=30)
    ap.add_argument('--workers',type=int,default=8,help='Parallel Parquet partition workers (default: 8)')
    ap.add_argument('--batch-size',type=int,default=250000,help='Rows per Arrow batch per worker (default: 250000)')
    ap.add_argument('--skip-geometry',action='store_true',help='Only one scan: skip linked geometry resource lookup')
    args=ap.parse_args()
    out=Path(args.out_dir or f'results/{args.kg_source}_country');out.mkdir(parents=True,exist_ok=True)
    paths=files_under(args.kg_dir)
    print(f'Parquet partitions: {len(paths)}',flush=True)
    if not paths:raise SystemExit('No Parquet files found')
    entities={}; candidates={}
    with open(args.entities,encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r.get('kg_source',r.get('source_kg','')).strip().lower()!=args.kg_source:continue
            eid=clean(r.get('entity_id'))
            if eid:
                entities[eid]=r
                candidates[eid]={k:v for k,v in r.items() if k.startswith('country')}
    if not entities:raise SystemExit(f'No {args.kg_source} entities found in entity CSV')
    print(f'Target {args.kg_source} IDs: {len(entities):,}',flush=True)

    triples=defaultdict(list); geo_links=defaultdict(set); subject_examples={}
    total=0; nmatched=0
    t0=time.monotonic()
    print(f'[PASS 1] {len(paths)} partitions, {args.workers} workers',flush=True)
    for path,n,h,items,links,subjects,seconds in _parallel_scan(
        paths,1,entities,{},args.workers,args.progress,args.batch_size,args.kg_source
    ):
        total+=n; nmatched+=h
        for eid,p,v in items: triples[eid].append((p,v))
        for eid,uri in links:geo_links[eid].add(uri)
        for eid,uri in subjects.items():subject_examples.setdefault(eid,uri)
        print(f'[PASS 1] {Path(path).name}: {n:,} rows, {h:,} target triples, '
              f'{seconds:.1f}s | total {total:,} rows',flush=True)
    print(f'[PASS 1 DONE] {total:,} rows; {len(subject_examples):,} IDs; '
          f'{nmatched:,} triples; {time.monotonic()-t0:.1f}s',flush=True)

    geom_to_eids=defaultdict(set)
    for eid,refs in geo_links.items():
        for v in refs:geom_to_eids[v].add(eid)
    if geom_to_eids and not args.skip_geometry:
        print(f'[PASS 2] {len(geom_to_eids):,} geometry resources, '
              f'{args.workers} workers',flush=True)
        geom_index={k:tuple(v) for k,v in geom_to_eids.items()}
        for path,n,h,items,_,_,seconds in _parallel_scan(
            paths,2,entities,geom_index,args.workers,args.progress,args.batch_size,args.kg_source
        ):
            for eid,p,v in items:triples[eid].append((p,v))
            print(f'[PASS 2] {Path(path).name}: {h:,} geometry triples; '
                  f'{seconds:.1f}s',flush=True)

    polygons=country_polygons(args.countries_geojson)
    stats=Counter(); rows=[]; review=[]; flat=[]
    for eid,r in entities.items():
        values=triples.get(eid,[])
        by=defaultdict(list)
        for p,v in values:
            if v not in by[p]:by[p].append(v)
        raw_countries=[]
        for p in COUNTRY_PRED:
            raw_countries+=by.get(p,[])
        explicit=[]
        for raw in raw_countries:
            cc,iso,_=pycountry_resolve(raw)
            if iso and (cc,iso) not in explicit:explicit.append((cc,iso))
        coord=point_from([(p.removeprefix('geometry_'),v) for p,v in values])
        point_country=('','','')
        if polygons and coord:point_country=polygon_country(coord[0],coord[1],polygons)
        if len(explicit)==1:
            country,iso=explicit[0];status='kg_explicit_country';ev=f'{args.kg_source} country predicate (not independently verified)'
            if point_country[1] and point_country[1]!=iso:
                status='conflict_explicit_vs_geometry';ev='explicit property disagrees with polygon lookup'
        elif len(explicit)>1:
            country=iso='';status='conflicting_explicit_properties';ev='multiple distinct direct country values'
        elif point_country[1]:
            country,iso=point_country[:2];status='derived_point_in_country_polygon';ev='geometry point in user supplied boundary'
        else:
            country=iso='';status=('not_found_in_snapshot' if eid not in subject_examples else 'needs_review');ev='no verified country from KG'
        if not country and raw_countries:ev+='; raw country property could not be normalized'
        row=dict(kg_source=args.kg_source,entity_id=eid,entity_name=r.get('entity_name',r.get('name','')),
                 subject_uri=subject_examples.get(eid,''),kg_found=eid in subject_examples,
                 country=country,country_iso3=iso,status=status,evidence=ev,
                 raw_country_values=' | '.join(raw_countries),
                 longitude=coord[0] if coord else '',latitude=coord[1] if coord else '',
                 geometry_type_hint=coord[2] if coord else '',
                 labels=' | '.join((by['name']+by['label']+by['nameen'])[:8]),
                 types=' | '.join(by['type'][:12]),
                 admin_info=' | '.join(f'{p}:{v}' for p in sorted(OTHER) for v in by.get(p,[])[:3])[:3000],
                 wikidata_links=' | '.join(v for p in LINK_PRED for v in by.get(p,[]) if 'wikidata' in v.lower() or p=='wikidata')[:1500],
                 external_links=' | '.join(v for p in LINK_PRED for v in by.get(p,[])[:5])[:1500],
                 wkt_snippet=' | '.join(v[:200] for p in by for v in by[p][:2] if p in ('aswkt','geometry_aswkt','geometry_wkt'))[:450],
                 triples_found=len(values))
        for j in (1,2,3):
            for fld in ('country','country_iso3'):
                row[f'prior_{fld}_{j}']=r.get(f'{fld}_{j}','')
        row['prior_country_confidence']=r.get('country_confidence','')
        rows.append(row);stats[status]+=1
        if not country or 'conflict' in status:
            rr=dict(row)
            rr['review_evidence_json']=json.dumps([{'predicate':p,'object':v[:1000]} for p,v in values[:args.max_review_triples]],ensure_ascii=False)
            rr['review_decision_country']='';rr['review_decision_iso3']='';rr['review_notes']=''
            review.append(rr)
        for p,v in values:
            flat.append({'entity_id':eid,'subject_uri':subject_examples.get(eid,''),'predicate':p,'object':v})

    def save(path,rows,fields=None):
        if fields is None:fields=list(rows[0]) if rows else []
        with open(path,'w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
        print(f'WROTE {path}: {len(rows):,} rows')
    save(out/f'{args.kg_source}_country_matches.csv',rows)
    save(out/f'{args.kg_source}_review.csv',review,fields=list(review[0]) if review else list(rows[0])+['review_evidence_json','review_decision_country','review_decision_iso3','review_notes'])
    save(out/f'{args.kg_source}_entity_triples.csv',flat,['entity_id','subject_uri','predicate','object'])
    if args.question_entities:
        joined=[]
        idx={r['entity_id']:r for r in rows}
        with open(args.question_entities,encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                if r.get('kg_source',r.get('source_kg','')).lower()!=args.kg_source:continue
                x=idx.get(clean(r.get('entity_id')))
                if not x:continue
                item={**r,'resolved_country':x['country'],'resolved_iso3':x['country_iso3'],
                      'country_status':x['status'],'country_evidence_kg':x['evidence']}
                joined.append(item)
        save(out/f'{args.kg_source}_question_entities.csv',joined)
    save(out/f'{args.kg_source}_stats.csv',[{'status':k,'entities':v} for k,v in sorted(stats.items())],['status','entities'])
    save(out/f'{args.kg_source}_four_columns.csv',
         [{'source_kg':args.kg_source,'entity_id':r['entity_id'],
           'name':r['entity_name'],'country':r['country']} for r in rows],
         ['source_kg','entity_id','name','country'])
    print('SUMMARY',dict(stats),flush=True)
    print('NOTE: missing country means unavailable from scanned triples, not necessarily outside any country.')

if __name__=='__main__':main()

