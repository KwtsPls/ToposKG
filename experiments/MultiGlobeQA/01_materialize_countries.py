#!/usr/bin/env python3
"""Materialize relevant ToposKG country files, using canonical input-directory names.

The third argument passed to materialize_topology.sh is the lowercase ISO3 code
(e.g. 'afg'), without any '_no' prefix.
"""
import argparse
import csv
import logging
import os
import re
import subprocess
import unicodedata
from pathlib import Path

LOG = logging.getLogger('country-materialization')


def norm(value):
    s = unicodedata.normalize('NFKD', str(value or '').casefold())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace('&', ' and ')
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


# Each group represents equivalent spellings, but the actual input directory
# always determines the canonical output country name.
ALIASES = [
    ('Macau', 'Macao', 'Macao SAR China', 'Macau SAR China'),
    ('Macedonia', 'North Macedonia', 'Republic of North Macedonia', 'The Former Yugoslav Republic of Macedonia', 'FYROM'),
    ('Malaysia',),
    ('Cabo Verde', 'Cape Verde'),
    ('Czech Republic', 'Czechia'),
    ('Swaziland', 'Eswatini'),
    ('Ivory Coast', "Cote d'Ivoire", 'Côte d’Ivoire', 'Cote d Ivoire'),
    ('United States', 'United States of America', 'USA', 'US'),
    ('United Kingdom', 'UK', 'Great Britain'),
    ('Russia', 'Russian Federation'),
    ('South Korea', 'Republic of Korea', 'Korea Republic of'),
    ('North Korea', "Democratic People's Republic of Korea", 'Korea Democratic Peoples Republic of'),
    ('Vietnam', 'Viet Nam'),
    ('Laos', "Lao People's Democratic Republic", 'Lao PDR'),
    ('Bolivia', 'Bolivia Plurinational State of'),
    ('Venezuela', 'Venezuela Bolivarian Republic of'),
    ('Syria', 'Syrian Arab Republic'),
    ('Iran', 'Iran Islamic Republic of'),
    ('Tanzania', 'United Republic of Tanzania', 'Tanzania United Republic of'),
    ('Moldova', 'Republic of Moldova', 'Moldova Republic of'),
    ('Brunei', 'Brunei Darussalam'),
    ('East Timor', 'Timor Leste'),
    ('Democratic Republic of the Congo', 'DR Congo', 'Congo Kinshasa', 'Congo Democratic Republic of'),
    ('Republic of the Congo', 'Congo Brazzaville', 'Congo'),
    ('Myanmar', 'Burma'),
    ('Palestine', 'Palestinian Territories', 'State of Palestine'),
    ('Türkiye', 'Turkey', 'Turkiye'),
    ('Kosovo', 'Republic of Kosovo'),
    ('Micronesia', 'Federated States of Micronesia'),
    ('The Gambia', 'Gambia'),
    ('The Bahamas', 'Bahamas'),
    ('Hong Kong', 'Hong Kong SAR China'),
]
ALIAS_KEYS = {}
for group in ALIASES:
    keys = {norm(g) for g in group}
    for key in keys:
        ALIAS_KEYS.setdefault(key, set()).update(keys)


def equivalents(value):
    key = norm(value)
    return ALIAS_KEYS.get(key, {key})


def copy_concat(files, output):
    temp = output.with_name(output.name + '.tmp')
    with temp.open('wb') as dst:
        for path in files:
            with path.open('rb') as src:
                while chunk := src.read(8 * 1024 * 1024):
                    dst.write(chunk)
            if path.stat().st_size:
                with path.open('rb') as chk:
                    chk.seek(-1, os.SEEK_END)
                    if chk.read(1) != b'\n':
                        dst.write(b'\n')
    os.replace(temp, output)


def load_codes(path):
    rows = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            name = (row.get('country') or '').strip()
            code = (row.get('code') or '').strip().lower()
            if name and code:
                rows.append((name, code))
    return rows


def find_dir(root, requested):
    # Exact normalized match first; fuzzy similarity alone risks wrong country.
    dirs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda x: x.name)
    key = norm(requested)
    direct = [d for d in dirs if norm(d.name) == key]
    if len(direct) == 1:
        return direct[0]
    if len(direct) > 1:
        raise ValueError(f'Ambiguous directories for {requested}: {[str(x) for x in direct]}')
    keys = equivalents(requested)
    matches = [d for d in dirs if norm(d.name) in keys]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f'Ambiguous alias directories for {requested}: {[str(x) for x in matches]}')
    return None


def find_nt(directory):
    """Use the canonical ToposKG '<directory name>_all.nt' input."""
    candidate = directory / f'{directory.name}_all.nt'
    if candidate.is_file():
        return candidate
    matches = [p for p in directory.glob('*_all.nt')
               if norm(p.stem[:-4]) == norm(directory.name)]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(
        f'Expected {candidate.name} in {directory}; '
        f'found {[p.name for p in directory.glob("*_all.nt")]}')


# ISO 3166-1 alpha-3 fallbacks for country-directory names which may not
# appear under the exact same label in the user-supplied country-code CSV.
# Names in the ToposKG directory remain canonical in all outputs.
KNOWN_CODE_FALLBACKS = {
    'brunei darussalam': 'brn',
    'brunei': 'brn',
    'macao': 'mac',
    'macau': 'mac',
    'north macedonia': 'mkd',
    'macedonia': 'mkd',
}


def find_code(directory_name, requested_name, country_codes):
    # Exact country-code CSV match using the *canonical directory name* first.
    for name in (directory_name, requested_name):
        direct = {code for label, code in country_codes if norm(label) == norm(name)}
        if len(direct) == 1:
            return direct.pop()
        if len(direct) > 1:
            raise ValueError(f'Ambiguous codes for {name}: {sorted(direct)}')

    # Match equivalent labels, e.g. Brunei -> Brunei Darussalam.
    for name in (directory_name, requested_name):
        equivalent = equivalents(name)
        choices = {code for label, code in country_codes if norm(label) in equivalent}
        if len(choices) == 1:
            return choices.pop()
        if len(choices) > 1:
            raise ValueError(f'Ambiguous alias codes for {name}: {sorted(choices)}')

    # If the country-code CSV lacks a listing, resolve the directory name
    # through ISO-3166 using pycountry when installed.
    try:
        import pycountry
        for name in (directory_name, requested_name):
            try:
                return pycountry.countries.lookup(name).alpha_3.lower()
            except LookupError:
                pass
    except ImportError:
        pass

    # Deterministic fallback for common directory aliases, without
    # replacing the actual ToposKG directory name.
    for name in (directory_name, requested_name):
        key = norm(name)
        for alias in equivalents(name):
            if alias in KNOWN_CODE_FALLBACKS:
                return KNOWN_CODE_FALLBACKS[alias]
        if key in KNOWN_CODE_FALLBACKS:
            return KNOWN_CODE_FALLBACKS[key]
    return None


def write_status(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['requested_country', 'country', 'code', 'input_nt', 'no_pattern', 'status', 'details'])
        w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entities', required=True)
    p.add_argument('--country-codes', required=True)
    p.add_argument('--countries-dir', required=True)
    p.add_argument('--materializer', required=True)
    p.add_argument('--out-dir', required=True)
    p.add_argument('--continue-on-error', dest='continue_on_error', action='store_true', default=True,
                   help='Skip missing files and failed countries (default)')
    p.add_argument('--fail-fast', dest='continue_on_error', action='store_false',
                   help='Stop on the first country-specific error')
    p.add_argument('--force', action='store_true')
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
    root = Path(a.countries_dir).resolve()
    materializer = Path(a.materializer).resolve()
    out = Path(a.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        p.error(f'Country directory missing: {root}')
    if not materializer.is_file():
        p.error(f'Materializer missing: {materializer}')

    wanted = set()
    with open(a.entities, newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if (row.get('source_kg') or '').strip().lower() not in {'osmh3kg', 'worldkg'}:
                continue
            for raw in (row.get('country') or '').split('|'):
                if raw.strip():
                    wanted.add(raw.strip())
    country_codes = load_codes(a.country_codes)
    status, jobs = [], {}
    for requested in sorted(wanted, key=norm):
        try:
            directory = find_dir(root, requested)
            if directory is None:
                LOG.warning('No ToposKG directory for %s', requested)
                status.append([requested, '', '', '', '', 'missing_country_dir', ''])
                continue
            code = find_code(directory.name, requested, country_codes)
            if not code:
                LOG.warning('No country code for %s (ToposKG dir: %s)', requested, directory.name)
                status.append([requested, directory.name, '', '', '', 'missing_country_code', ''])
                continue
            source = find_nt(directory)
            if directory.name in jobs:
                LOG.info('Alias %r resolves to already queued %s', requested, directory.name)
                continue
            jobs[directory.name] = (requested, directory.name, code, source)
        except ValueError as e:
            LOG.error('%s: %s', requested, e)
            status.append([requested, '', '', '', '', 'ambiguous_or_missing_nt', str(e)])
            if not a.continue_on_error:
                write_status(out / 'country_status.csv', status)
                raise SystemExit(1)

    succeeded = []
    for i, (requested, name, code, source) in enumerate(jobs.values(), 1):
        # The code is the exact grep pattern: 'afg', not '_no_AFG'.
        pattern = code
        dest = out / 'by_country' / name / 'mappings.nt'
        dest.parent.mkdir(parents=True, exist_ok=True)
        meta = dest.with_name('selection_pattern.txt')
        cached = (not a.force and dest.is_file() and meta.is_file()
                  and dest.stat().st_mtime >= source.stat().st_mtime
                  and meta.read_text(encoding='utf-8').strip() == pattern)
        if cached:
            LOG.info('[%d/%d] %s: cached (%s)', i, len(jobs), name, pattern)
        else:
            LOG.info('[%d/%d] %s: %s, pattern=%s', i, len(jobs), name, source, pattern)
            try:
                subprocess.run(['bash', str(materializer), str(source), str(dest), pattern], check=True)
                meta.write_text(pattern + '\n', encoding='utf-8')
            except subprocess.CalledProcessError as e:
                dest.unlink(missing_ok=True)
                meta.unlink(missing_ok=True)
                status.append([requested, name, code, str(source), pattern, 'materialization_failed', str(e.returncode)])
                if not a.continue_on_error:
                    write_status(out / 'country_status.csv', status)
                    raise SystemExit(f'Country materialization failed: {name}')
                continue
        succeeded.append((source, dest))
        status.append([requested, name, code, str(source), pattern, 'success', str(dest)])

    copy_concat((source for source, _ in succeeded), out / 'countries.nt')
    output = out / 'country_mappings.nt'
    tmp = output.with_name(output.name + '.tmp')
    seen = set()
    with tmp.open('wb') as dst:
        for _, mappings in succeeded:
            with mappings.open('rb') as f:
                for line in f:
                    canonical = line.rstrip(b'\r\n')
                    if canonical and canonical not in seen:
                        seen.add(canonical)
                        dst.write(canonical + b'\n')
    os.replace(tmp, output)
    write_status(out / 'country_status.csv', status)
    LOG.info('Requested names=%d, matched directories=%d, completed=%d, mapping triples=%d',
             len(wanted), len(jobs), len(succeeded), len(seen))


if __name__ == '__main__':
    main()

