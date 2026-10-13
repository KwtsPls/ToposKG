#!/usr/bin/env python3
"""Evaluate selected GeoQuestions1089 questions on a modified SPARQL endpoint.

Every question is transpiled by GoST first; rewritten query is executed.
Only successfully executed and confidently parsed answer comparisons can be
classified MATCH / INCONSISTENT. Execution/schema errors are separate.

Python 3.9+, standard library only.
"""
import argparse
import collections
import csv
import decimal
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib import request, parse, error

PREFIXES = '''PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX yago: <http://yago-knowledge.org/resource/>
PREFIX y2geor: <http://kr.di.uoa.gr/yago2geo/resource/>
PREFIX y2geoo: <http://kr.di.uoa.gr/yago2geo/ontology/>
PREFIX strdf: <http://strdf.di.uoa.gr/ontology#>
PREFIX uom: <http://www.opengis.net/def/uom/OGC/1.0/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
'''
XSD = 'http://www.w3.org/2001/XMLSchema#'
BOOLEAN = XSD + 'boolean'
NUMERIC = {XSD + x for x in ('integer','int','long','short','byte','nonNegativeInteger','nonPositiveInteger','positiveInteger','negativeInteger','unsignedInt','unsignedLong','unsignedShort','unsignedByte','decimal','float','double')}
FIELDS = ['id','question','category','query_type','status','expected_count','actual_count','missing_count','extra_count','expected','actual','missing','extra','error','elapsed_seconds','original_query','rewritten_query']

def load_questions(path):
    with open(path, encoding='utf-8-sig') as f: data=json.load(f)
    if isinstance(data,dict):
        if 'questions' in data and isinstance(data['questions'],list): data=data['questions']
        else:
            return [(str(i),v) for i,v in data.items() if isinstance(v,dict) and ('Query' in v or 'query' in v)]
    if isinstance(data,list):
        return [(str(item.get('id',item.get('ID',i))),item) for i,item in enumerate(data) if isinstance(item,dict)]
    raise ValueError('Questions must be a JSON object keyed by question ID or a list of question objects')

def load_answers(path):
    with open(path,encoding='utf-8-sig') as f: return json.load(f)

def lookup_gold(data, qid):
    if isinstance(data,dict):
        if qid in data: return data[qid]
        for k in ('answers','Answers','results','Results'):
            if k in data: return lookup_gold(data[k], qid)
    if isinstance(data,list):
        for row in data:
            if isinstance(row,dict) and str(row.get('id',row.get('ID',row.get('QuestionID',''))))==qid:
                return row
    raise KeyError(f'No gold answer for ID {qid}')

def get_qtype(query):
    without_prefix = re.sub(r'(?im)^\s*PREFIX\s+[^\n]*$', '', query)
    m=re.search(r'\b(ASK|SELECT|CONSTRUCT|DESCRIBE)\b',without_prefix,re.I)
    return m.group(1).upper() if m else 'UNKNOWN'

def add_prefixes(query):
    existing=set(re.findall(r'(?im)^\s*PREFIX\s+([\w-]+):',query))
    wanted=[]
    for line in PREFIXES.splitlines():
        prefix=re.search(r'PREFIX\s+([\w-]+):',line).group(1)
        if prefix not in existing: wanted.append(line)
    return '\n'.join(wanted)+'\n'+query

def gost_rewrite(java, cp, classname, query, timeout):
    command=[java,'-cp',cp,classname,query]
    proc=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f'GoST exited {proc.returncode}: {proc.stderr.strip()[:1500]} {proc.stdout.strip()[:400]}')
    result=proc.stdout.strip()
    if not result: raise RuntimeError('GoST returned empty stdout')
    # Keep the query section if diagnostics were printed before it.
    match=re.search(r'(?im)^\s*(?:PREFIX\s+[^\n]*|(?:SELECT|ASK|CONSTRUCT|DESCRIBE)\b)',result)
    if not match: raise RuntimeError('GoST stdout does not contain an identifiable SPARQL query: '+result[:500])
    result=result[match.start():].strip()
    if get_qtype(result)=='UNKNOWN': raise RuntimeError('GoST output contains no recognizable query form')
    return add_prefixes(result)

def endpoint_query(endpoint, sparql, timeout, method, headers, retries):
    payload=parse.urlencode({'query':sparql}).encode('utf-8')
    base_headers={'Accept':'application/sparql-results+json, application/json;q=0.9'}
    base_headers.update(headers)
    for attempt in range(retries+1):
        try:
            if method=='GET':
                url=endpoint+('&' if '?' in endpoint else '?')+payload.decode()
                req=request.Request(url,headers=base_headers)
            else:
                req=request.Request(endpoint,data=payload,headers={**base_headers,'Content-Type':'application/x-www-form-urlencoded; charset=utf-8'},method='POST')
            with request.urlopen(req,timeout=timeout) as rsp:
                raw=rsp.read()
                try: return json.loads(raw)
                except json.JSONDecodeError as exc: raise ValueError('Endpoint response is not SPARQL JSON: '+raw[:350].decode('utf-8','replace')) from exc
        except (error.HTTPError,error.URLError,TimeoutError) as exc:
            if attempt==retries: raise RuntimeError(str(exc)) from exc
            time.sleep(min(2**attempt,10))

# Canonical RDF terms. Numeric lexical variants compare by numeric value;
# other literal datatypes and language tags retain RDF-term identity.
def canon_term(obj):
    if not isinstance(obj,dict) or 'type' not in obj or 'value' not in obj:
        raise ValueError('Not a SPARQL JSON RDF term: '+repr(obj)[:200])
    typ=obj['type']; value=str(obj['value'])
    if typ in ('uri','iri'): return ('uri',value)
    if typ=='bnode': return ('bnode',value)
    if typ in ('literal','typed-literal'):
        language=(obj.get('xml:lang') or obj.get('lang') or '').lower()
        datatype=obj.get('datatype','')
        if datatype in NUMERIC:
            try:
                d=decimal.Decimal(value)
                if d.is_finite(): return ('numeric',str(d.normalize()))
            except decimal.InvalidOperation: pass
        if datatype==BOOLEAN:
            return ('boolean','true' if value.lower() in ('1','true') else 'false')
        if language: return ('lang',language,value)
        if datatype in ('',XSD+'string'): return ('literal',value)
        return ('typed',datatype,value)
    raise ValueError('Unsupported RDF term type: '+typ)

def canon_result(result, qtype, strict_bag=False):
    if isinstance(result,dict) and 'boolean' in result:
        if qtype!='ASK': raise ValueError('Expected SELECT, got ASK result')
        return bool(result['boolean'])
    if not (isinstance(result,dict) and isinstance(result.get('results'),dict) and isinstance(result['results'].get('bindings'),list)):
        raise ValueError('Expected SPARQL JSON results.bindings or boolean; got '+str(result)[:250])
    if qtype=='ASK': raise ValueError('Expected ASK, got SELECT result')
    rows=[]
    for row in result['results']['bindings']:
        rows.append(tuple(sorted((str(k),canon_term(v)) for k,v in row.items())))
    return collections.Counter(rows) if strict_bag else set(rows)

def parse_gold_text_table(text, qtype, strict_bag):
    """GeoQuestions1089 gold strings: header then CRLF-separated TSV records.

    The header contains variable names; results are serialized lexical values,
    often with CSV-style double quotes around URI values containing commas.
    Compare columns positionally to endpoint head.vars because older gold files
    sometimes rename variables despite identical result semantics.
    """
    lines=text.splitlines()
    lines=[line for line in lines if line.strip()]
    if not lines:
        raise ValueError('Empty gold text table')
    import io
    reader=csv.reader(io.StringIO('\n'.join(lines)),delimiter='\t',quotechar='"')
    rows=list(reader)
    if qtype=='ASK':
        if len(rows)==1 and len(rows[0])==1 and rows[0][0].strip().lower() in ('true','false','1','0'):
            return rows[0][0].strip().lower() in ('true','1')
        if len(rows)!=2 or len(rows[1])!=1 or rows[1][0].strip().lower() not in ('true','false','1','0'):
            raise ValueError('ASK gold does not contain one Boolean row: '+repr(rows[:3])[:250])
        return rows[1][0].strip().lower() in ('true','1')
    if qtype!='SELECT':
        raise ValueError('Unsupported query type for text-table gold: '+qtype)
    header=rows[0]
    if not header or any(not name.strip() for name in header):
        raise ValueError('Invalid gold table header: '+repr(header))
    values=[]
    for i,row in enumerate(rows[1:],2):
        if len(row)!=len(header):
            raise ValueError(f'Gold row {i}: expected {len(header)} columns, got {len(row)}')
        values.append(tuple(canon_gold_cell(v) for v in row))
    return collections.Counter(values) if strict_bag else set(values)

def canon_gold_cell(value):
    value=value.strip()
    # Many exported records quote the entire URI to protect commas.
    if len(value)>=2 and value[0]=='"' and value[-1]=='"':
        value=value[1:-1].replace('""','"')
    if not value: return ('unbound',)
    if value.startswith('<') and value.endswith('>'): value=value[1:-1]
    if re.match(r'^https?://\S+$',value): return ('uri',value)
    if value.lower() in ('true','false'): return ('boolean',value.lower())
    try:
        num=decimal.Decimal(value)
        if num.is_finite(): return ('numeric',str(num.normalize()))
    except decimal.InvalidOperation: pass
    return ('literal',value)

def canon_result_positional(result, strict_bag):
    if 'boolean' in result: return bool(result['boolean'])
    vars_=result.get('head',{}).get('vars')
    bindings=result.get('results',{}).get('bindings')
    if not isinstance(vars_,list) or not isinstance(bindings,list):
        raise ValueError('SPARQL JSON SELECT result requires head.vars and results.bindings')
    rows=[]
    for row in bindings:
        rows.append(tuple(canon_term(row[v]) if v in row else ('unbound',) for v in vars_))
    return collections.Counter(rows) if strict_bag else set(rows)

def parse_gold(gold,qtype,strict_bag):
    # Gold answers are only interpreted when their representation is unambiguous.
    if isinstance(gold,dict):
        if 'boolean' in gold or ('results' in gold and isinstance(gold['results'],dict)):
            return canon_result(gold,qtype,strict_bag)
        for key in ('Answer','answer','Answers','answers','Result','result','Results'):
            if key in gold: return parse_gold(gold[key],qtype,strict_bag)
        if qtype!='ASK' and 'bindings' in gold and isinstance(gold['bindings'],list):
            return canon_result({'results':{'bindings':gold['bindings']}},qtype,strict_bag)
        raise ValueError('Unrecognized gold object keys: '+','.join(gold.keys())[:200])
    if isinstance(gold,str):
        trimmed=gold.strip()
        if trimmed.startswith(('{','[')):
            try: return parse_gold(json.loads(trimmed),qtype,strict_bag)
            except json.JSONDecodeError: pass
        if qtype=='ASK' and trimmed.lower() in ('true','false','1','0'):
            return trimmed.lower() in ('true','1')
        return parse_gold_text_table(gold,qtype,strict_bag)
    if qtype=='ASK' and isinstance(gold,(bool,int)) and gold in (False,True,0,1): return bool(gold)
    if qtype!='ASK' and isinstance(gold,list):
        # Full SPARQL JSON bindings list; rows use var -> RDF-term dict.
        if all(isinstance(row,dict) and all(isinstance(term,dict) and 'type' in term and 'value' in term for term in row.values()) for row in gold):
            return canon_result({'results':{'bindings':gold}},qtype,strict_bag)
        raise ValueError('Gold list is not a SPARQL JSON bindings list')
    raise ValueError('Unrecognized gold answer representation: '+repr(gold)[:180])

def fmt(x):
    if isinstance(x,bool): return str(x).lower()
    if isinstance(x,collections.Counter):
        return json.dumps([{'row':v,'frequency':n} for v,n in sorted(x.items(),key=lambda i:repr(i[0]))],ensure_ascii=False,default=str)
    if isinstance(x,set): return json.dumps(sorted(x,key=repr),ensure_ascii=False,default=str)
    return json.dumps(x,ensure_ascii=False,default=str)

def compare(a,b,qtype,bag):
    if qtype=='ASK': return a==b,[],[]
    if bag:
        missing=a-b; extra=b-a
    else:
        missing=a-b; extra=b-a
    return a==b,missing,extra

def count(x):
    if isinstance(x,bool): return 1
    if isinstance(x,collections.Counter): return sum(x.values())
    return len(x)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--questions',required=True,help='Subset GeoQuestions1089.json')
    ap.add_argument('--answers',required=True,help='Official GeoQuestions1089_answers.json')
    ap.add_argument('--endpoint',required=True,help='SPARQL HTTP query endpoint URL')
    ap.add_argument('--gost',required=True,help='Path to GoST jar or directory of .class files')
    ap.add_argument('--out-dir',default='geoquestions_eval')
    ap.add_argument('--java',default='java')
    ap.add_argument('--gost-class',default='gr.uoa.di.ai.Transpiler')
    ap.add_argument('--method',choices=['POST','GET'],default='POST')
    ap.add_argument('--header',action='append',default=[],help='Custom HTTP header, e.g. "Authorization: Bearer ..."')
    ap.add_argument('--endpoint-timeout',type=float,default=180)
    ap.add_argument('--gost-timeout',type=float,default=60)
    ap.add_argument('--retries',type=int,default=1)
    ap.add_argument('--delay',type=float,default=0,help='Delay between questions in seconds')
    ap.add_argument('--bag',action='store_true',help='Compare SELECT rows with multiplicities, not set semantics')
    ap.add_argument('--resume',action='store_true',help='Skip IDs already recorded in results.jsonl')
    ap.add_argument('--limit',type=int,default=0,help='First N questions, useful for smoke testing')
    ap.add_argument('--download-answers',action='store_true',help='Download answers from official GitHub raw file if --answers is missing')
    args=ap.parse_args()
    out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    if args.download_answers and not Path(args.answers).exists():
        url='https://raw.githubusercontent.com/AI-team-UoA/GeoQuestions1089/main/GeoQuestions1089_answers.json'
        logging.warning('Downloading large official gold answers file (~78 MB): %s',url)
        request.urlretrieve(url,args.answers)
    questions=load_questions(args.questions)
    gold=load_answers(args.answers)
    logging.info('Loaded %d selected questions',len(questions))
    hdr={}
    for h in args.header:
        if ':' not in h: ap.error('Header must be Name: Value')
        k,v=h.split(':',1);hdr[k.strip()]=v.strip()
    logs=out/'results.jsonl'
    if not args.resume and logs.exists(): logs.unlink()
    records={}
    if args.resume and logs.exists():
        for line in logs.read_text(encoding='utf-8').splitlines():
            if line.strip():
                obj=json.loads(line);records[str(obj['id'])]=obj
    chosen=questions[:args.limit] if args.limit else questions
    for idx,(qid,item) in enumerate(chosen,1):
        if qid in records: continue
        original=item.get('Query',item.get('query',''))
        question=item.get('Question',item.get('question',''))
        qtype=get_qtype(original)
        row={k:'' for k in FIELDS}
        row.update(id=qid,question=question,category=item.get('Category',item.get('category','')),query_type=qtype,original_query=original)
        start=time.monotonic()
        try:
            if qtype not in ('ASK','SELECT'): raise ValueError('Only ASK and SELECT supported')
            query=add_prefixes(original)
            try: rewritten=gost_rewrite(args.java,args.gost,args.gost_class,query,args.gost_timeout)
            except Exception as exc: row['status']='GOST_ERROR';raise RuntimeError(str(exc)) from exc
            row['rewritten_query']=rewritten
            try: result=endpoint_query(args.endpoint,rewritten,args.endpoint_timeout,args.method,hdr,args.retries)
            except Exception as exc: row['status']='QUERY_ERROR';raise RuntimeError(str(exc)) from exc
            # Write actual endpoint output for provenance, even when gold parsing fails.
            (out/f'actual_{qid}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            try: actual=canon_result(result,qtype,args.bag)
            except Exception as exc: row['status']='RESULT_FORMAT_ERROR';raise RuntimeError(str(exc)) from exc
            try: expected=parse_gold(lookup_gold(gold,qid),qtype,args.bag)
            except KeyError as exc: row['status']='MISSING_GOLD';raise RuntimeError(str(exc)) from exc
            except Exception as exc: row['status']='GOLD_FORMAT_ERROR';raise RuntimeError(str(exc)) from exc
            # String gold records are TSV tables, so compare positional values;
            # JSON gold records retain variable-name-based comparison.
            gold_raw=lookup_gold(gold,qid)
            if qtype=='SELECT' and isinstance(gold_raw,str) and not gold_raw.strip().startswith(('{','[')):
                actual=canon_result_positional(result,args.bag)
            good,missing,extra=compare(expected,actual,qtype,args.bag)
            row.update(status='MATCH' if good else 'INCONSISTENT',expected_count=count(expected),actual_count=count(actual),missing_count=count(missing),extra_count=count(extra),expected=fmt(expected),actual=fmt(actual),missing=fmt(missing),extra=fmt(extra))
        except Exception as exc:
            row['error']=str(exc)[:1800]
            if not row['status']: row['status']='ERROR'
        row['elapsed_seconds']=round(time.monotonic()-start,3)
        records[qid]=row
        with logs.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        logging.info('[%d/%d] ID=%s %s (%.2fs) %s',idx,len(chosen),qid,row['status'],row['elapsed_seconds'],row['error'][:150])
        if args.delay: time.sleep(args.delay)
        # Continuously refresh CSVs so interrupted runs remain useful.
        write_csvs(out,records)
    write_csvs(out,records)
    tally=collections.Counter(row['status'] for row in records.values())
    summary={'selected_questions':len(chosen),'processed':len(records),'status_counts':dict(tally),'note':'INCONSISTENT means gold and modified-KG results differ, not necessarily that the source answer is geographically false.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

def write_csvs(out,records):
    order=sorted(records.values(),key=lambda r:(0,int(r['id'])) if str(r['id']).isdigit() else (1,str(r['id'])))
    for filename,subset in [('evaluation.csv',order),('inconsistencies.csv',[r for r in order if r['status']=='INCONSISTENT']),('errors.csv',[r for r in order if r['status'] not in ('INCONSISTENT','MATCH')])]:
        tmp=out/(filename+'.tmp')
        with tmp.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(subset)
        os.replace(tmp,out/filename)

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    main()

