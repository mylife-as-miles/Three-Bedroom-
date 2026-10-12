#!/usr/bin/env python3
"""Verify corpus integrity, graph referential integrity, hashes and independent evidence."""
import collections,hashlib,json,struct,subprocess,sys
from data import ROOT,load
from corpus import fnv1a64,dump
checks={};m=load('file_manifest.json');files=m['files'];assert len(files)==8004 and all(f['path'].startswith('dc1/') for f in files);checks['manifest_files']=len(files)
if (ROOT/'.private/extracted').exists():
 for f in files:
  p=ROOT/'.private/extracted'/f['path'];assert p.stat().st_size==f['size'];assert hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']
 checks['extracted_hashes_verified']=len(files)
scripts=load('state_scripts.json');functions=load('functions.json');calls=load('calls.json');ids={f['id'] for f in functions};by={f['id']:f for f in functions};assert len(ids)==len(functions)
for c in calls:
 assert c['caller'] in ids
 assert c['offset']==by[c['caller']]['instruction_offset']+8*c['instruction_index']
 assert 0<=c['instruction_index']<by[c['caller']]['instruction_count']
 assert all(d in ids for d in c.get('definitions',[]))
 for arg in c['arguments']:
  if arg[0]=='result':assert arg[1].rsplit(':',1)[0] in ids
checks['call_references_verified']=len(calls)
for ss in scripts:
 names={s['name'] for s in ss['states']};assert len(names)==len(ss['states'])
 for st in ss['states']:
  for b in st['blocks']:
   for track in b['tracks']:
    for p in track['lambdas']:assert ss['file']+f'@{p:X}' in ids
checks['state_scripts_verified']=len(scripts)
sids=load('sid_database.json');assert all(fnv1a64(s['string'])==int(s['sid'],16) for s in sids);checks['sid_hashes_verified']=len(sids)
assert not load('parse_errors.json');checks['parser_errors']=0
r=load('reference_validation.json');assert all(not x['mismatches'] for x in r);checks['independent_comparable_targets']=sum(x['comparable_call_offsets'] for x in r)
prior=load('prior_reconciliation.json');assert not prior['conflicting_files'];checks['prior_scripts_matched']=prior['known_state_sequences_matched']
i=load('interaction_definitions.json');assert i['gameplay_definition_count']==273 and i['hud_interact_name_count']==111;checks['interaction_definitions']=273;checks['hud_names']=111
aux=load('auxiliary_coverage.json');assert aux['resource_groups']==3348 and aux['resource_reference_edges']==52545;assert aux['all_auxiliary_parse_errors']==0;checks['resource_groups_verified']=aux['resource_groups'];checks['resource_edges_verified']=aux['resource_reference_edges']
dedup=load('startup_deduplication.json');assert dedup['additional_unique_files']==0 and dedup['content_duplicates_of_primary']==1714;checks['nested_duplicates_verified']=1714
r=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tools/analysis/tests'),'-v'],capture_output=True,text=True);print(r.stderr);assert r.returncode==0;checks['property_tests']='passed'
dump(ROOT/'databases/validation.json',checks);print(json.dumps(checks,indent=2))
