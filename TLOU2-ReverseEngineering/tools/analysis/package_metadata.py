#!/usr/bin/env python3
"""Compact derived JSON, redact descriptive literals, retain full records privately.
Safe to run again: gzip-json descriptors are resolved before rewriting.
"""
import gzip,hashlib,json,re,shutil,math
from pathlib import Path
from data import ROOT
from corpus import dump
IDENTIFIER=re.compile(r'^[A-Za-z0-9_*/?.:!+<>=$%-]+$')
redactions=0
new_redactions=0

def sanitize(value):
 global redactions,new_redactions
 if isinstance(value,float) and not math.isfinite(value):
  return {"type":"ieee754-nonfinite","value":"NaN" if math.isnan(value) else "Infinity" if value>0 else "-Infinity"}
 if isinstance(value,list):
  if len(value)==2 and value[0]=='string-redacted':redactions+=1;return value
  if len(value)==2 and value[0]=='string' and isinstance(value[1],str) and not IDENTIFIER.fullmatch(value[1]):
   redactions+=1;new_redactions+=1;return ['string-redacted',{'sha256':hashlib.sha256(value[1].encode()).hexdigest(),'length':len(value[1])}]
  for i,x in enumerate(value):value[i]=sanitize(x)
 elif isinstance(value,dict):
  for k,x in value.items():value[k]=sanitize(x)
 return value

def main():
 files=list((ROOT/'databases').rglob('*.json'))+list((ROOT/'interactions').glob('*/evidence.json'))+list((ROOT/'level_design/examples').glob('*.json'));backup=ROOT/'.private/derived_full';stats=[]
 for path in files:
  original=json.load(open(path))
  if isinstance(original,dict) and original.get('storage')=='gzip-json':
   value=json.load(gzip.open(path.parent/original['file'],'rt'))
  else:
   value=original;dest=backup/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
  value=sanitize(value)
  encoded=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()+b'\n'
  if len(encoded)>500_000:
   gzpath=Path(str(path)+'.gz')
   with gzpath.open('wb') as f:
    with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0,compresslevel=6) as z:z.write(encoded)
   desc={'storage':'gzip-json','file':gzpath.name,'schema_version':1,'uncompressed_bytes':len(encoded),'sha256':hashlib.sha256(encoded).hexdigest(),'record_count':len(value) if isinstance(value,list) else None,'note':'Derived metadata only; descriptive literals are redacted. Load via tools/analysis/data.py or gzip.'};dump(path,desc);stats.append({'path':path.relative_to(ROOT).as_posix(),'bytes':gzpath.stat().st_size})
  else:path.write_bytes(encoded);stats.append({'path':path.relative_to(ROOT).as_posix(),'bytes':len(encoded)})
 dump(ROOT/'databases/package_stats.json',{'files':stats,'total_derived_json_bytes':sum(s['bytes'] for s in stats),'descriptive_literal_occurrences_redacted':redactions,'newly_redacted_occurrences':new_redactions})
 print('Packaged',len(stats),'JSON files;',round(sum(s['bytes'] for s in stats)/1024**2,2),'MiB;',redactions,'literal occurrences redacted')
if __name__=='__main__':main()
