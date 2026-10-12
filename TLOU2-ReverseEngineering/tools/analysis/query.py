#!/usr/bin/env python3
import argparse,json,re
from data import load
p=argparse.ArgumentParser();p.add_argument('kind',choices=['sid','functions','calls','states','events','entries']);p.add_argument('pattern');p.add_argument('--file');p.add_argument('--limit',type=int,default=30);a=p.parse_args()
name={'sid':'sid_database.json','states':'state_scripts.json'}.get(a.kind,a.kind+'.json');rows=load(name);pat=re.compile(a.pattern,re.I);count=0
for row in rows:
 if a.file and a.file not in row.get('file',''):continue
 fields=[row.get(k) for k in ('name','string','target','event','function','id')];fields+=[' '.join(s['name'] for s in row.get('states',[]))]
 if any(pat.search(str(field[1] if isinstance(field,list) and len(field)>1 else field)) for field in fields if field is not None):
  count+=1
  if count<=a.limit:print(json.dumps(row,ensure_ascii=False))
print(json.dumps({'matches':count,'displayed':min(count,a.limit)}))
