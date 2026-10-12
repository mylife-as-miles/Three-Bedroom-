#!/usr/bin/env python3
"""Hash JSON/TXT corpus strings and index resource manifests; never index derived listings."""
import collections,json,re,struct
from pathlib import Path
from data import ROOT,load
from corpus import DC,dump,fnv1a64,ID_RE,TOKEN_RE
manifest=load('file_manifest.json')['files'];paths=[f['path'] for f in manifest if f['path'].endswith(('.json','.txt'))];records=[];strings=collections.defaultdict(set);empty=[];fields=collections.Counter();documents=0
def collect(value,file):
 if isinstance(value,str):strings[value].add(file)
 elif isinstance(value,dict):
  fields.update(value.keys())
  for k,v in value.items():collect(k,file);collect(v,file)
 elif isinstance(value,list):
  for v in value:collect(v,file)
for file in paths:
 p=ROOT/'.private/extracted'/file;text=p.read_text()
 if not text:empty.append(file);continue
 if file.endswith('.json'):
  decoder=json.JSONDecoder();i=0;row=0
  while i<len(text):
   while i<len(text) and text[i].isspace():i+=1
   if i==len(text):break
   start=i;value,i=decoder.raw_decode(text,i);documents+=1;
   for group_index,obj in enumerate(value if isinstance(value,list) else [value]):
    if not isinstance(obj,dict):raise ValueError('Unexpected resource record')
    records.append({'file':file,'record_index':row,'group_index':group_index,'owner':obj.get('name'),'references':[{'category':key,'target':target} for key,items in obj.items() if key!='name' for target in items],'confidence':'CONFIRMED declared resource reference; runtime residency unknown'})
   collect(value,file);row+=1
 else:
  for line in text.splitlines():collect(line,file)
db={int(h,16):s for h,s in json.load(open(ROOT/'.private/sid_dictionary.json')).items()};original=set(db);hashes={}
for value,files in strings.items():
 h=fnv1a64(value);db.setdefault(h,value);hashes[h]=value
 for token in TOKEN_RE.findall(value):db.setdefault(fnv1a64(token),token)
dump(ROOT/'.private/sid_dictionary.json',{f'{h:016X}':s for h,s in db.items()})
uses=collections.defaultdict(collections.Counter)
new_keys=set(db)-original
if new_keys:
 for file in manifest:
  if not file['path'].endswith('.bin'):continue
  dc=DC(ROOT/'.private/extracted'/file['path'],file['path'],db)
  for offset,(h,) in enumerate(struct.iter_unpack('<Q',dc.b[:dc.strings//8*8])):
   if h in new_keys and not dc.ptr(offset*8):uses[h][file['path']]+=1
sids=load('sid_database.json');byhash={int(s['sid'],16):s for s in sids}
for h,value in hashes.items():
 if not ID_RE.fullmatch(value):continue
 if h in byhash:row=byhash[h];row['readable_source_files']=sorted(strings[value]);row['resolution']='game-readable-fnv'
 else:
  u=uses.get(h,{});row={'sid':f'{h:016X}','string':value,'source_files':sorted(set(u)|strings[value]),'type':'readable-auxiliary-string-with-optional-aligned-word-reference','usage_count':sum(u.values()),'uses_by_file':dict(u),'resolution':'game-readable-fnv','hash_verified':True,'readable_source_files':sorted(strings[value])};sids.append(row)
dump(ROOT/'databases/sid_database.json',sorted(sids,key=lambda x:x['sid']));dump(ROOT/'databases/level_resources.json',records)
coverage={'json_files':sum(p.endswith('.json') for p in paths),'txt_files':sum(p.endswith('.txt') for p in paths),'empty_json_files':empty,'json_documents':documents,'resource_records':len(records),'resource_groups':len(records),'resource_reference_edges':sum(len(r['references']) for r in records),'unique_readable_strings':len(strings),'new_dictionary_hashes_including_tokens':len(new_keys),'new_hashes_matching_dc_words':len(uses),'resource_fields':dict(fields),'all_auxiliary_parse_errors':0};dump(ROOT/'databases/auxiliary_coverage.json',coverage);print(json.dumps(coverage,indent=2))
