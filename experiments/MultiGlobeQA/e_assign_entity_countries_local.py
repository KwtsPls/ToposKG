#!/usr/bin/env python3
"""Offline country assignment from collected WorldKG / OSMH3KG match CSVs.

No RDF, Parquet, network, or prior final-country CSV is required.
100% ASSIGNMENT is optional (--require-complete); it is not 100% ACCURACY.
"""
import argparse
import csv
import logging
import math
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import wkt
from shapely.geometry import Point
from scipy.spatial import cKDTree

LOG = logging.getLogger('countries')
NUM = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
PAIR = re.compile(r'(?<![\w.])(' + NUM + r')\s+(' + NUM + r')(?![\w.])')
SRID = re.compile(r'^\s*(?:<[^>]+>\s*)?SRID=\d+;', re.I)
EARTH_KM = 6371.0088

ALIASES = {
    'United States of America':'United States',
    'Dem. Rep. Congo':'Democratic Republic of the Congo',
    'Democratic Republic of Congo':'Democratic Republic of the Congo',
    'Republic of the Congo':'Republic of the Congo',
    'Congo':'Republic of the Congo',
    'Czechia':'Czech Republic',
    'Macedonia':'North Macedonia',
    'Myanmar':'Myanmar',
    'eSwatini':'Eswatini',
    'Dominican Rep.':'Dominican Republic',
    'Bosnia and Herz.':'Bosnia and Herzegovina',
    'S. Sudan':'South Sudan',
    'W. Sahara':'Western Sahara',
    'Central African Rep.':'Central African Republic',
    'Eq. Guinea':'Equatorial Guinea',
    'Solomon Is.':'Solomon Islands',
    'Fr. S. Antarctic Lands':'French Southern and Antarctic Lands',
    'N. Cyprus':'Northern Cyprus',
    'Falkland Is.':'Falkland Islands',
    'Timor-Leste':'Timor-Leste',
    'Macao':'Macau',
    'Brunei':'Brunei Darussalam',
}

# Coarse Natural Earth 110m omits many islands. High-specificity coordinate
# overrides reproduce the earlier local Ryukyu/Ogasawara assignment.
# These are candidate geographic regions, NOT an authoritative border polygon.
def island_candidate(lon, lat):
    if (122 <= lon <= 131.5 and 23 <= lat <= 32) or (141 <= lon <= 143.5 and 24 <= lat <= 28):
        return 'Japan', 'japan_ryukyu_or_ogasawara_region'
    return None, None


def canonical(value):
    s = str(value or '').strip()
    return ALIASES.get(s, s)


def country_polygons(path, column):
    boundaries = gpd.read_file(path)
    if boundaries.crs is None:
        raise ValueError('Country boundaries have no CRS; require EPSG:4326 or a declared CRS')
    boundaries = boundaries.to_crs('EPSG:4326')
    if column not in boundaries.columns:
        for alt in ('ADMIN', 'NAME_EN', 'name', 'NAME', 'country', 'SOVEREIGNT'):
            if alt in boundaries.columns:
                LOG.warning('Requested name column missing; using %s', alt)
                column = alt
                break
        else:
            raise ValueError(f'Cannot find country name field; available={list(boundaries.columns)}')
    boundaries = boundaries[boundaries.geometry.notna()].copy()
    boundaries['_country'] = boundaries[column].map(canonical)
    boundaries = boundaries[boundaries['_country'] != '']
    return boundaries


def loc_from_geometry(row):
    lon, lat = row.get('longitude',''), row.get('latitude','')
    text = str(row.get('wkt_snippet','')).strip()
    if text:
        cleaned = SRID.sub('', text)
        if cleaned.startswith('<') and '> ' in cleaned:
            cleaned = cleaned.split('> ',1)[1]
        try:
            geom = wkt.loads(cleaned)
            if not geom.is_empty:
                pt = geom.representative_point()
                if -180 <= pt.x <= 180 and -90 <= pt.y <= 90:
                    return (float(pt.x),float(pt.y),'complete_wkt_representative_point')
        except Exception:
            pass
        m = PAIR.search(cleaned)
        if m:
            x,y = float(m.group(1)),float(m.group(2))
            if -180 <= x <= 180 and -90 <= y <= 90:
                return x,y,'truncated_wkt_first_coordinate'
    try:
        x,y = float(lon),float(lat)
        if -180 <= x <= 180 and -90 <= y <= 90:
            return x,y,'source_coordinate'
    except (TypeError,ValueError): pass
    return float('nan'),float('nan'),'no_coordinates'


def xyz(lon, lat):
    a=np.deg2rad(np.asarray(lat, dtype=float)); b=np.deg2rad(np.asarray(lon,dtype=float))
    return np.column_stack([np.cos(a)*np.cos(b),np.cos(a)*np.sin(b),np.sin(a)])


def resolve(input_frames, boundaries, require_complete=True, overrides=None, max_neighbor_km=math.inf):
    df=pd.concat(input_frames,ignore_index=True)
    df=df.drop_duplicates(['kg_source','entity_id'],keep='first').reset_index(drop=True)
    n=len(df)
    df['source_kg']=df['kg_source']; df['name']=df['entity_name']
    df['assigned_country']=''; df['method']=''; df['confidence']=''; df['alternatives']=''
    df['geometry_location_method']='';df['location_lon']=np.nan;df['location_lat']=np.nan
    df['neighbor_km']=np.nan;df['neighbor_entity_id']=''
    if overrides is None: overrides={}

    for i,row in df.iterrows():
        x,y,m=loc_from_geometry(row)
        df.at[i,'location_lon']=x; df.at[i,'location_lat']=y;df.at[i,'geometry_location_method']=m

    # Explicit KG country (authority: asserted by source, not independently validated).
    for i,row in df.iterrows():
        key=(str(row['kg_source']),str(row['entity_id']))
        value=overrides.get(key) or canonical(row.get('country',''))
        if value:
            df.at[i,'assigned_country']=canonical(value)
            df.at[i,'method']='manual_override' if key in overrides else 'explicit_kg_country'
            df.at[i,'confidence']='user_supplied' if key in overrides else 'high_source_assertion'

    sindex=boundaries.sindex
    for i,row in df.iterrows():
        x,y=row['location_lon'],row['location_lat']
        if not (np.isfinite(x) and np.isfinite(y)): continue
        point=Point(x,y)
        hits=sindex.query(point,predicate='intersects')
        names=sorted({boundaries.iloc[int(j)]['_country'] for j in hits})
        if names:df.at[i,'alternatives']=' | '.join(names)
        if len(names)==1:
            if row['assigned_country']:
                if canonical(row['assigned_country'])!=names[0]:
                    df.at[i,'method']=str(row['method'])+'_spatial_conflict'
                    df.at[i,'confidence']='conflict_review'
            else:
                df.at[i,'assigned_country']=names[0]
                if row['geometry_location_method']=='complete_wkt_representative_point':
                    df.at[i,'method']='complete_wkt_representative_point_in_country'
                    df.at[i,'confidence']='medium_spatial_proxy'
                else:
                    df.at[i,'method']='first_coordinate_or_source_point_in_country'
                    df.at[i,'confidence']='tentative_spatial_proxy'

    # Known omission of coarse boundary: small islands of Japan.
    for i,row in df.iterrows():
        if df.at[i,'assigned_country']:continue
        x,y=row['location_lon'],row['location_lat']
        if np.isfinite(x) and np.isfinite(y):
            country,method=island_candidate(x,y)
            if country:
                df.at[i,'assigned_country']=country;df.at[i,'method']=method
                df.at[i,'confidence']='medium_region_inference'

    # Nearest already-resolved feature using spherical nearest-neighbor index.
    reference=df[(df.assigned_country!='') & np.isfinite(df.location_lon) & np.isfinite(df.location_lat)]
    if not reference.empty:
        tree=cKDTree(xyz(reference.location_lon.to_numpy(),reference.location_lat.to_numpy()))
        ref_index=reference.index.to_numpy()
        missing=df[(df.assigned_country=='') & np.isfinite(df.location_lon) & np.isfinite(df.location_lat)]
        if not missing.empty:
            chord,refpos=tree.query(xyz(missing.location_lon.to_numpy(),missing.location_lat.to_numpy()),k=1)
            distances=EARTH_KM*2*np.arcsin(np.clip(chord/2,0,1))
            for i,rpos,dist in zip(missing.index,refpos,distances):
                j=int(ref_index[int(rpos)])
                df.at[i,'neighbor_km']=float(dist)
                df.at[i,'neighbor_entity_id']=df.at[j,'entity_id']
                if dist<=max_neighbor_km:
                    df.at[i,'assigned_country']=df.at[j,'assigned_country']
                    df.at[i,'method']='nearest_resolved_entity'
                    df.at[i,'confidence']='low_nearest_neighbor'

    # Use prior label-derived candidates, if supplied in source matching CSV.
    for i,row in df.iterrows():
        if df.at[i,'assigned_country']: continue
        for field in ('prior_country_1','prior_country_2','prior_country_3'):
            candidate=canonical(row.get(field,''))
            if candidate:
                df.at[i,'assigned_country']=candidate
                df.at[i,'method']='prior_name_candidate_'+field
                df.at[i,'confidence']='very_low_name_inference'
                break

    # 100% completeness fallback: nearest polygon country, even over long distance.
    # This is intentionally VERY LOW confidence (can be wrong for islands/borders).
    remaining=df[df.assigned_country=='']
    if len(remaining):
        pts=boundaries.geometry.representative_point()
        tree=cKDTree(xyz(pts.x.to_numpy(),pts.y.to_numpy()))
        names=boundaries['_country'].to_numpy()
        for i,row in remaining.iterrows():
            x,y=row['location_lon'],row['location_lat']
            if np.isfinite(x) and np.isfinite(y):
                _,j=tree.query(xyz([x],[y])[0],k=1)
                df.at[i,'assigned_country']=str(names[int(j)])
                df.at[i,'method']='nearest_country_polygon_representative_point'
                df.at[i,'confidence']='very_low_coarse_geographic_guess'

    still=df[df.assigned_country=='']
    if len(still) and require_complete:
        raise RuntimeError(f'{len(still)} entities have no coordinates, country assertion, or candidates. '
                           'Cannot obtain 100% meaningful country assignments without additional evidence. '
                           'Provide --overrides CSV or --allow-unresolved.')
    return df


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--matches',nargs='+',required=True,help='WorldKG and/or OSMH3KG *country_matches.csv files')
    ap.add_argument('--countries',required=True,help='Country polygons (GeoJSON, Shapefile, GPKG), EPSG:4326 preferred')
    ap.add_argument('--country-column',default='ADMIN',help='Country name field (auto-fallback supported)')
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--overrides',help='Optional CSV with source_kg,entity_id,country for manually adjudicated cases')
    ap.add_argument('--allow-unresolved',action='store_true',help='Allow blank countries if no defensible candidate exists')
    ap.add_argument('--max-neighbor-km',type=float,default=float('inf'),help='Maximum distance for nearest-entity fallback')
    args=ap.parse_args()
    logging.basicConfig(level=logging.INFO,format='[%(asctime)s] %(levelname)s %(message)s')
    frames=[]
    for f in args.matches:
        part=pd.read_csv(f,dtype=str,keep_default_na=False)
        required={'kg_source','entity_id','entity_name'}
        if not required.issubset(part.columns): raise ValueError(f'{f}: missing {required-set(part.columns)}')
        LOG.info('Read %d entities from %s',len(part),f)
        frames.append(part)
    country_gdf=country_polygons(args.countries,args.country_column)
    LOG.info('Loaded %d country boundary features',len(country_gdf))
    overrides={}
    if args.overrides:
        with open(args.overrides,newline='',encoding='utf-8-sig') as fh:
            for row in csv.DictReader(fh):
                overrides[(row['source_kg'].strip(),row['entity_id'].strip())]=row['country'].strip()
    df=resolve(frames,country_gdf,not args.allow_unresolved,overrides,args.max_neighbor_km)
    out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    df[['source_kg','entity_id','name','assigned_country']].rename(columns={'assigned_country':'country'}).to_csv(out/'entity_countries.csv',index=False)
    df.rename(columns={'assigned_country':'country'}).to_csv(out/'country_evidence.csv',index=False)
    df.groupby(['source_kg','method','confidence'],dropna=False).size().rename('entities').reset_index().to_csv(out/'resolution_summary.csv',index=False)
    review=df[df.confidence.str.contains('low|conflict',case=False,regex=True) | (df.assigned_country=='')]
    review.to_csv(out/'needs_review.csv',index=False)
    LOG.info('Completed: %d/%d assigned (%.2f%%), %d in review',df.assigned_country.ne('').sum(),len(df),100*df.assigned_country.ne('').mean(),len(review))
    LOG.info('Output: %s',out.resolve())
    LOG.info('Methods:\n%s',df.method.value_counts().to_string())

if __name__=='__main__':main()
