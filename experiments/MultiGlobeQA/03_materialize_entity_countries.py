#!/usr/bin/env python3
"""Materialize WorldKG/OSMH3KG entities AGAINST countries (two disjoint datasets).

Combine only the benchmark entity NT files; keep countries.nt separate. Run
materialize_entity_country_topology.sh(source_entities.nt, countries.nt, output.nt).
Then deduplicate the new mappings with the already generated country mappings.
"""
import argparse
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path


def concatenate(files, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.tmp')
    with temporary.open('wb') as out:
        for filename in files:
            with Path(filename).open('rb') as source:
                shutil.copyfileobj(source, out, length=8 * 1024 * 1024)
                # NT inputs should have newline-terminated triples
                if out.tell() and not _ends_with_newline(filename):
                    out.write(b'\n')
    os.replace(temporary, destination)


def _ends_with_newline(path):
    with Path(path).open('rb') as source:
        source.seek(0, 2)
        if source.tell() == 0:
            return True
        source.seek(-1, 2)
        return source.read(1) in (b'\n', b'\r')


def merge_unique(inputs, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='multiglobeqa_dedup_') as folder:
        db = sqlite3.connect(str(Path(folder) / 'lines.sqlite'))
        db.execute('PRAGMA journal_mode=OFF')
        db.execute('CREATE TABLE triples (line BLOB PRIMARY KEY) WITHOUT ROWID')
        for file in inputs:
            batch = []
            with Path(file).open('rb') as stream:
                for line in stream:
                    line = line.strip()
                    if not line:
                        continue
                    batch.append((line,))
                    if len(batch) >= 10000:
                        db.executemany('INSERT OR IGNORE INTO triples VALUES (?)', batch)
                        batch.clear()
                if batch:
                    db.executemany('INSERT OR IGNORE INTO triples VALUES (?)', batch)
            db.commit()
        with destination.open('wb') as out:
            for (line,) in db.execute('SELECT line FROM triples ORDER BY line'):
                out.write(line + b'\n')
        print(f'[MERGE] {destination}: {db.execute("SELECT COUNT(*) FROM triples").fetchone()[0]:,} unique mappings', flush=True)
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--countries-nt', required=True)
    parser.add_argument('--country-mappings', required=True)
    parser.add_argument('--entity-geometry-nt', required=True, action='append',
                        help='Repeat for OSMH3KG and WorldKG')
    parser.add_argument('--materializer', required=True,
                        help='Path to materialize_entity_country_topology.sh')
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--skip-materialization', action='store_true')
    args = parser.parse_args()

    for path in [args.countries_nt, args.country_mappings, *args.entity_geometry_nt, args.materializer]:
        if not Path(path).is_file():
            parser.error(f'File does not exist: {path}')

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    # No countries inside this input file.
    entity_nt = out_dir / 'combined_entities.nt'
    concatenate(args.entity_geometry_nt, entity_nt)
    print(f'[SOURCE] {entity_nt}', flush=True)
    print(f'[TARGET] {Path(args.countries_nt).resolve()}', flush=True)

    entity_country = out_dir / 'entity_country_mappings.nt'
    if not args.skip_materialization:
        subprocess.run([
            'bash', str(Path(args.materializer).resolve()), str(entity_nt),
            str(Path(args.countries_nt).resolve()), str(entity_country)
        ], check=True)
    elif not entity_country.exists():
        parser.error(f'--skip-materialization set but no {entity_country} exists')

    merge_unique([args.country_mappings, entity_country], out_dir / 'mappings.nt')
    print(f'[DONE] Final mappings: {out_dir / "mappings.nt"}', flush=True)


if __name__ == '__main__':
    main()

