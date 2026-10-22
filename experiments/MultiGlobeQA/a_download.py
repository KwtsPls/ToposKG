#!/usr/bin/env python3
"""Download MultiGlobeQA Parquet files without datasets/huggingface_hub/httpx2.

Usage:
  python3 01_download_requests.py --list-only
  python3 01_download_requests.py --out data
  python3 01_download_requests.py --out data --no-gold
"""
import argparse
import logging
import os
import pathlib
import sys
import time

import requests

REPO = 'aiana94/MultiGlobeQA'
BASE = 'https://huggingface.co'
LOG = logging.getLogger('multiglobeqa')


def http_session(token=None):
    s = requests.Session()
    s.headers.update({'Accept-Encoding': 'identity', 'User-Agent': 'MultiGlobeQA-topology-audit/1.0'})
    if token:
        s.headers['Authorization'] = f'Bearer {token}'
    return s


def listing(session):
    url = f'{BASE}/api/datasets/{REPO}/tree/main'
    continuation = None
    entries = []
    while True:
        params = {'recursive': 'true', 'limit': 1000, 'expand': 'false'}
        if continuation:
            params['cursor'] = continuation
        r = session.get(url, params=params, timeout=90)
        r.raise_for_status()
        page = r.json()
        if not isinstance(page, list):
            raise RuntimeError(f'Unexpected repository tree response: {str(page)[:300]}')
        entries.extend(x['path'] for x in page if x.get('type') == 'file')
        # Pagination continuation is provided in Link header by the HF API.
        link = r.links.get('next', {}).get('url')
        if not link:
            break
        # Use full next-page URL to preserve the server's pagination convention.
        url = link
        continuation = None
        # Subsequent requests must use URL-provided query params.
        while True:
            rr = session.get(url, timeout=90)
            rr.raise_for_status()
            p = rr.json()
            entries.extend(x['path'] for x in p if x.get('type') == 'file')
            url = rr.links.get('next', {}).get('url')
            if not url:
                return entries
    return entries


def select_files(paths, language, split, include_gold):
    paths = [p for p in paths if p.endswith('.parquet')]
    # Official questions are organized as questions/<language>/<split>/<KG>.parquet.
    questions = [p for p in paths if p.startswith(f'questions/{language}/{split}/')]
    # Gold triples are language-independent, under gold_triples/<split>/.
    gold = [p for p in paths if p.startswith(f'gold_triples/{split}/')] if include_gold else []
    return sorted(questions), sorted(gold)


def download_one(session, remote_path, dest, retries=3):
    url = f'{BASE}/datasets/{REPO}/resolve/main/{remote_path}'
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        LOG.info('Already exists, reusing: %s', dest)
        return
    temp = dest.with_suffix(dest.suffix + '.partial')
    for attempt in range(1, retries + 1):
        try:
            # Explicit identity avoids negotiating Brotli content compression.
            with session.get(url, stream=True, timeout=(30, 180)) as r:
                r.raise_for_status()
                total = 0
                with temp.open('wb') as fh:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            fh.write(chunk)
                            total += len(chunk)
                if total == 0:
                    raise IOError('Zero-byte download')
            temp.replace(dest)
            LOG.info('Downloaded %-65s %9.1f MB', remote_path, total / 1048576)
            return
        except (requests.RequestException, OSError) as exc:
            LOG.warning('Attempt %s/%s for %s: %s', attempt, retries, remote_path, exc)
            if attempt == retries:
                raise
            time.sleep(attempt * 2)


def combine_parquet(files, output):
    import pyarrow as pa
    import pyarrow.parquet as pq
    writer = None
    total_rows = 0
    try:
        for f in files:
            parquet = pq.ParquetFile(f)
            for batch in parquet.iter_batches(batch_size=65536):
                table = pa.Table.from_batches([batch])
                if writer is None:
                    writer = pq.ParquetWriter(output, table.schema, compression='zstd')
                writer.write_table(table)
                total_rows += table.num_rows
        if writer is None:
            raise RuntimeError('No data files to combine')
    except Exception:
        output.unlink(missing_ok=True)
        raise
    finally:
        if writer is not None:
            writer.close()
    LOG.info('Wrote %s (%s rows)', output, f'{total_rows:,}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default='data')
    ap.add_argument('--language', default='eng')
    ap.add_argument('--split', default='large', choices=('large', 'small'))
    ap.add_argument('--no-gold', action='store_true')
    ap.add_argument('--list-only', action='store_true')
    ap.add_argument('--keep-raw', action='store_true', help='Keep downloaded KG partitions in raw/ (default: retained too)')
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    session = http_session(os.environ.get('HF_TOKEN'))
    LOG.info('Listing %s via requests (no Hugging Face Python client)', REPO)
    try:
        paths = listing(session)
        qpaths, gpaths = select_files(paths, args.language, args.split, not args.no_gold)
        LOG.info('Question files (%d):\n%s', len(qpaths), '\n'.join('  ' + p for p in qpaths))
        LOG.info('Gold triple files (%d):\n%s', len(gpaths), '\n'.join('  ' + p for p in gpaths))
        if not qpaths:
            LOG.error('Could not identify question Parquet files. First 40 Parquet paths in repository:\n%s',
                      '\n'.join(p for p in paths if p.endswith('.parquet'))[:4000])
            return 2
        if args.list_only:
            return 0
        out = pathlib.Path(args.out)
        downloaded_q = []
        for p in qpaths:
            dest = out / 'raw' / p
            download_one(session, p, dest)
            downloaded_q.append(dest)
        combine_parquet(downloaded_q, out / f'{args.language}_{args.split}.parquet')
        if not args.no_gold:
            if not gpaths:
                LOG.warning('No gold files found under gold_triples/%s/; inspect repository listing.', args.split)
            else:
                downloaded_g = []
                for p in gpaths:
                    dest = out / 'raw' / p
                    download_one(session, p, dest)
                    downloaded_g.append(dest)
                combine_parquet(downloaded_g, out / f'gold_triples_{args.split}.parquet')
        return 0
    except Exception:
        LOG.exception('Download failed')
        return 1


if __name__ == '__main__':
    sys.exit(main())

