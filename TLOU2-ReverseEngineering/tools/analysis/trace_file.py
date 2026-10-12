#!/usr/bin/env python3
"""Generate a small evidence view from one real local DC module."""
import argparse,json,sys
from pathlib import Path
from corpus import DC,dump
p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--output',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[2];db={int(h,16):s for h,s in json.load(open(root/'.private/sid_dictionary.json')).items()};dc=DC(root/'.private/extracted'/a.file,a.file,db);states,ctx=dc.states();fns,errors=dc.lambdas(ctx)
result={'file':a.file,'entries':dc.entries,'scripts':states,'functions':[f for f,c,r in fns],'calls':[c for f,cs,r in fns for c in cs],'errors':errors}
if a.output:dump(a.output,result)
else:
 for ss in states:
  print('SCRIPT',ss['name'],'INITIAL',ss['initial_state']);print('DECLARATIONS',[(d['name'],d['type'],d['value']) for d in ss['declarations']])
  for st in ss['states']:
   print('\nSTATE',st['name'])
   for f,cs,r in fns:
    if any(c['state']==st['name'] for c in f['contexts']):
     print('LAMBDA',hex(f['offset']),[(c['block'],c['event'],c['track'],c['index']) for c in f['contexts']])
     for call in cs:print(hex(call['offset']),call['target'],call['arguments'])
 for f,cs,r in fns:
  if not f['contexts']:
   print('\nFUNCTION',f['name'],hex(f['offset']))
   for call in cs:print(hex(call['offset']),call['target'],call['arguments'])
