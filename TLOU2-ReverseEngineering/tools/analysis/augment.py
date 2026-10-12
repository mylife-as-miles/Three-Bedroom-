#!/usr/bin/env python3
"""Add module, dependency, declaration and previous-handoff reconciliation indexes."""
import collections,json,re,sys
from pathlib import Path
from data import ROOT,load
from corpus import DC,dump
calls=load('calls.json');functions=load('functions.json');modules=load('modules.json');entries=load('entries.json');scripts=load('state_scripts.json')
exports=collections.defaultdict(list)
for m in modules:
 for name in m['exports']:exports[name].append(m['name'])
api=load('engine_api.json')
for row in api:row['declaring_modules']=exports.get(row['name'],[])
dump(ROOT/'databases/engine_api.json',api)
graph=load('call_graph.json');graph['module_import_edges']=[{'source':m['name'],'target':i,'kind':'declared-import','offset':m['offset']} for m in modules for i in m['imports']];graph['symbol_edges']=[{'source':c['caller'],'target':c['target'],'call_id':c['id'],'declaring_modules':exports.get(c['target'][1],[]) if len(c['target'])>1 else [],'binding':'symbol reference; actual runtime definition binding not verified'} for c in calls];graph['semantics']='State contexts in state_scripts/functions; ScriptLambda calls in calls; explicit go transitions and declared module dependencies. Static may-call graph, not runtime order.';dump(ROOT/'databases/call_graph.json',graph)
# Exact per-file declaration updates are cheap and avoid re-reading bytecode.
db={int(h,16):s for h,s in json.load(open(ROOT/'.private/sid_dictionary.json')).items()};dc_cache={}
for ss in scripts:
 file=ss['file']
 if file not in dc_cache:dc_cache[file]=DC(ROOT/'.private/extracted'/file,file,db)
 dc=dc_cache[file]
 for decl in ss['declarations']:
  p=decl['value_offset'];decl['value']=dc.decl_value(decl['type'],p) if p else None
  decl['is_variable']=dc.short(decl['offset']+26)!=0
 dump_path=None
dump(ROOT/'databases/state_scripts.json',scripts)
for p in (ROOT/'interactions').glob('*/evidence.json'):
 data=json.load(open(p));byid={s['id']:s for s in scripts};data['state_scripts']=[byid[s['id']] for s in data['state_scripts']];dump(p,data)
# Explicit dependency types distinguish calls from symbol-only references.
patterns={'animation':r'anim|attach|joint-ik|root-adjust|scripted-move|holster|ap-ref|locator', 'audio':r'sound|audio-gameplay|sfx', 'inventory':r'inventory|pickup|treasure|weapon-upgrade', 'persistence':r'svar|fact|checkpoint|persistent', 'resources':r'load|stream|package|cache|level-set'}
result={}
for category,pattern in patterns.items():
 pat=re.compile(pattern,re.I);cs=[c for c in calls if c['target'][0]=='sid' and pat.search(c['target'][1])]
 result[category]={'call_ids':[c['id'] for c in cs],'call_targets':sorted({c['target'][1] for c in cs}),'declaring_modules':sorted({m for c in cs for m in exports.get(c['target'][1],[])}),'typed_export_records':[e for e in entries if pat.search(e['type']) and (category!='audio' or re.search('drawer|cabinet|door|safe|keypad|generator|rope|book|paper',e['file'],re.I))],'note':'Typed export presence and call instructions are distinct evidence; declaring module may only expose an interface.'}
dump(ROOT/'databases/dependencies.json',result)
# Per-symbol callable/state relationships use a separate index to avoid duplicating the SID table.
xrefs=collections.defaultdict(lambda:{'callers':set(),'states':set(),'call_ids':[]})
for c in calls:
 if c['target'][0]=='sid':
  name=c['target'][1];x=xrefs[name];x['callers'].add(c['caller']);x['call_ids'].append(c['id'])
  x['states'].update(c['file']+'::'+ctx['script']+'::'+ctx['state'] for ctx in c['contexts'])
dump(ROOT/'databases/cross_references.json',{name:{'related_functions':sorted(x['callers']),'related_states':sorted(x['states']),'call_ids':x['call_ids']} for name,x in xrefs.items()})
# Identify unsupported target labels rather than silently interpreting them as known states.
bystate={(s['file'],s['name']):{t['name'] for t in s['states']} for s in scripts};unknown=[]
for c in calls:
 if c['target']==['sid','go'] and c['arguments'] and c['arguments'][0][0]=='sid':
  target=c['arguments'][0][1]
  for ctx in c['contexts']:
   if target not in bystate.get((c['file'],ctx['script']),set()):unknown.append({'call_id':c['id'],'file':c['file'],'script':ctx['script'],'from_state':ctx['state'],'target':target,'confidence':'UNKNOWN: target not in this StateScript table'})
dump(ROOT/'databases/unresolved_transitions.json',unknown)
prior=ROOT/'.private/prior_handoff/tlou2_reverse_engineering_handoff/core_interaction_call_map.json'
if prior.exists():
 old=json.load(open(prior));checks=[]
 for category,obj in old.items():
  filename=obj.get('source','');filename='dc1/'+filename.split('dc1/',1)[1] if 'dc1/' in filename else filename
  current=[s for s in scripts if s['file']==filename];names={t['name'] for s in current for t in s['states']};known=[t['name'] for t in obj.get('states',[]) if t.get('name') and not t['name'].startswith('#')]
  checks.append({'category':category,'file':filename,'prior_states_matched_by_sid':sum(int(t['sid'],16) in {__import__('corpus').fnv1a64(n) for n in names} for t in obj.get('states',[]) if t.get('sid')),'prior_known_states':len(known),'known_states_present':sum(n in names for n in known),'prior_call_count':sum(len(t.get('calls',[])) for t in obj.get('states',[])),'new_file_call_count':sum(c['file']==filename for c in calls),'note':'Prior linear tracer counts may duplicate shared lambdas and do not prove instruction order.'})
 dump(ROOT/'databases/handoff_reconciliation.json',{'source_version_conflict':'Prior README/architecture say 1.6; SOURCE_NOTES says 1.4. This run is independently tied to the downloaded 1.6-named archive and SHA256.','checks':checks})
print('Augmented module/dependency/declaration/prior indexes')
