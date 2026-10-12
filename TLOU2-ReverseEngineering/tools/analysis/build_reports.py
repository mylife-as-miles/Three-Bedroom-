#!/usr/bin/env python3
"""Build state graphs, cross references, interaction definitions and evidence reports."""
import collections,csv,gzip,hashlib,json,re,struct,sys
from pathlib import Path
from corpus import DC,dump,fnv1a64
from data import load,ROOT
PRIMARY={
'drawers':['dc1/ss-t2/ss-openable-drawer.bin'],
'cabinets':['dc1/ss-t2/ss-openable-cabinet.bin'],
'pickups':['dc1/ss-t2/ss-crafting-recipe-from-pickup.bin','dc1/ss-t2/ss-grounded-pickup-despawn.bin','dc1/ss-t2/ss-item-pickup-optional-weapon.bin'],
'investigate':['dc1/ss/ss-investigate-object.bin'],
'examine':['dc1/ss/ss-examine.bin'],
'notes':['dc1/ss-hud2/ss-menu2-collectibles.bin'],
'safes':['dc1/ss/ss-tumbler-safe.bin','dc1/ss-hud2/ss-hud2-lock-minigame.bin'],
'keypads':['dc1/ss-seattlearrival/ss-sea-arrival-keypad.bin','dc1/ss-seattlearrival/ss-sea-horse-keypad.bin'],
'generators':['dc1/ss-seattlearrival/ss-sea-qz-generator-minigame.bin','dc1/ss-seattlearrival/ss-sea-qz-puz-door-generator.bin','dc1/ss-patrol/ss-pat-generator-start.bin'],
'doors':['dc1/ss-t2/ss-openable-door.bin','dc1/anim-player/player-door.bin','dc1/ss-watchtower/ss-wat-infected-tunnels-rope-puzzle-door.bin'],
'ladders':['dc1/ss-t2/ss-basic-ladder.bin','dc1/anim-player/player-ladder.bin','dc1/anim-player/player-climb.bin','dc1/anim-player/player-edge-climb.bin','dc1/anim-player/player-squeeze-through.bin'],
'ropes':['dc1/rope.bin','dc1/phys-ropes.bin','dc1/anim-player/player-rope.bin','dc1/anim-player/player-wall-rope.bin','dc1/ss-seattlearrival/ss-sea-qz-wall-rope-deflector.bin','dc1/ss-watchtower/ss-wat-infected-tunnels-rope-puzzle-door.bin'],
'pushables':['dc1/push-object.bin','dc1/anim-player/player-push-object.bin','dc1/ss/ss-push-follow-cam.bin','dc1/ss-test/ss-test-bsingh/ss-bsingh-puzzle-pushable.bin'],
'workbench':['dc1/ss-t2/ss-workbench.bin','dc1/ss-hud2/ss-menu2-workbench.bin','dc1/ss-hud2/ss-menu2-workbench-upgrades.bin','dc1/workbench-script-funcs-impl.bin','dc1/workbench-settings.bin','dc1/workbench-settings-ellie.bin','dc1/workbench-settings-abby.bin']}
SYSTEMS={'interactable':'interact|pickup-scan','animation':'anim|attach|locator|joint-ik|scripted-move|holster|root','ui':'hud|gui2|widget|prompt','audio':'sound|audio|sfx|bank','camera':'camera|render-settings','ai':'perception|hearing|vision|cover|knowledge|npc.*aware|search-params|ai/|infected','inventory':'inventory|player-apply-pickup|player-pickup|ammo|resource|weapon-upgrade','persistence':'svar|fact|checkpoint|save|persistent','resources':'package|cache|level-set|stream|bank|load.*resource|ir-pack'}
MEANINGFUL=re.compile('interact|pickup|inventory|treasure|attach|detach|camera|anim|scripted|move-to|ik|holster|svar|fact|checkpoint|sound|audio|event|widget|gui2|hud2|rope|ladder|push|upgrade|mesh|collect|^go$|power|light|locator|joint|root|vector|align|entry|tension|crouch|parent')

def fmt(v):
 if not v:return '?'
 if v[0]=='unknown':return '?'
 if v[0]=='global-ref':return 'lookup('+v[1]+')'
 if v[0]=='string' and not re.fullmatch(r'[A-Za-z0-9_*/?.:!+<>=$%-]+',v[1]):return 'literal-sha256:'+hashlib.sha256(v[1].encode()).hexdigest()[:16]
 if v[0]=='result':return 'result('+v[1].split('@')[-1]+')'
 return str(v[1]) if len(v)>1 else v[0]
def call_label(c):return fmt(c['target'])
def write(path,text):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
def main():
 print('Loading global evidence',flush=True);functions=load('functions.json');calls=load('calls.json');scripts=load('state_scripts.json');entries=load('entries.json');sids=load('sid_database.json');errors=load('parse_errors.json');manifest=load('file_manifest.json')['files'];events=load('events.json')
 cf=collections.defaultdict(list);sf=collections.defaultdict(list);ef=collections.defaultdict(list);syf=collections.defaultdict(list);fnby={f['id']:f for f in functions};callby={c['id']:c for c in calls}
 for c in calls:cf[c['file']].append(c)
 for s in scripts:sf[s['file']].append(s)
 for e in entries:ef[e['file']].append(e)
 for s in sids:
  for f in s['source_files']:syf[f].append(s['string'])
 # Improve misleading #%-prefixed known symbols; the anonymous syntax is exactly # + 16 hex digits.
 anonymous=re.compile(r'^#[0-9A-Fa-f]{16}$')
 for c in calls:
  if c['target'][0]=='sid' and not anonymous.fullmatch(c['target'][1]):c['confidence']='CONFIRMED'
 # Global event graph is grouped, not an invented all-to-all runtime delivery graph.
 eg=collections.defaultdict(lambda:{'producers':[],'listeners':[]})
 for e in events:
  if e['kind']=='listener':eg[e['event']]['listeners'].append(e)
 for c in calls:
  if c['target'][0]=='sid' and c['target'][1] in ('send-event','broadcast-event','send-event-box-result','net-send-event-all') and c['arguments'] and c['arguments'][0][0]=='sid':eg[c['arguments'][0][1]]['producers'].append({'call_id':c['id'],'file':c['file'],'function':c['target'][1],'receiver':c['arguments'][1] if len(c['arguments'])>1 else None,'contexts':c['contexts'],'offset':c['offset']})
 dump(ROOT/'databases/event_graph.json',{'edge_semantics':'matching event SID is candidate linkage; receiver identity, state and dispatch timing must be checked','events':eg})
 # Per-system discovery uses file names, SID uses, called functions and entry types.
 index={}
 for category,pattern in SYSTEMS.items():
  pat=re.compile(pattern,re.I);members={f['path'] for f in manifest if pat.search(f['path'])}
  related_calls=[c for c in calls if pat.search(call_label(c))];members.update(c['file'] for c in related_calls)
  symbol_hits=[s for s in sids if pat.search(s['string'])];members.update(f for s in symbol_hits for f in s['source_files'])
  index[category]={'files':sorted(members),'call_ids':[c['id'] for c in related_calls],'symbol_names':[s['string'] for s in symbol_hits],'search_pattern':pattern,'confidence':'CONFIRMED references; functional relevance requires interpretation'}
  out=ROOT/'systems'/category
  cnt=collections.Counter(call_label(c) for c in related_calls)
  md=f'# {category.title()} corpus index\n\nSearch combines names, actual SID words, exported structures and executed call instructions. Keyword matches are discovery leads, not a claim that every matched module implements this system.\n\n{len(members)} candidate files; {len(related_calls)} matching call sites; {len(symbol_hits)} matching symbols. Full lists: `databases/system_index.json`.\n\n## Common call targets\n\n| Target | Sites | Corpus definition |\n| --- | ---: | --- |\n'
  defs={f['name'] for f in functions}
  for name,n in cnt.most_common(45):md+=f'| `{name}` | {n} | {"script lambda present" if name in defs else "not found; boundary unresolved"} |\n'
  write(out/'evidence.md',md)
 dump(ROOT/'databases/system_index.json',index)
 # Interaction gameplay definitions and HUD name-list records remain separate.
 db={int(h,16):s for h,s in json.load(open(ROOT/'.private/sid_dictionary.json')).items()};d=DC(ROOT/'.private/extracted/dc1/interactable.bin','dc1/interactable.bin',db);gui=DC(ROOT/'.private/extracted/dc1/gui2-game.bin','dc1/gui2-game.bin',db)
 gui_names={};pos=gui.strings
 while pos<gui.text:
  end=gui.b.find(b'\0',pos,gui.text)
  if end<0:break
  name=gui.b[pos:end].decode('utf-8',errors='replace')
  if name.startswith('interact-'):gui_names[name]=pos
  pos=end+1
 interact=[]
 for e in d.entries:
  if e['type']!='game-interactable-def':continue
  p=e['offset'];words=[]
  # Fixed payload length observed across all 273 records. +0x200 is NEXT struct's type tag.
  assert d.name(d.q(p-8))=='game-interactable-def'
  for off in range(0,0x200,8):
   h=d.q(p+off)
   if h in db or d.ptr(p+off):words.append({'member_offset':off,'file_offset':p+off,'value':d.value(p+off),'confidence':'CONFIRMED value; member semantics unmapped'})
  name=e['name'];cross=[{'file':f,'usage_count':next(s['uses_by_file'].get(f,0) for s in sids if s['string']==name)} for f in next((s['source_files'] for s in sids if s['string']==name),[]) if f!='dc1/interactable.bin']
  behavior='mash' if 'mash' in name else 'hold' if 'hold' in name else 'stick-rotation' if re.search('rotate|[lr]s-c[wc]',name) else 'unspecified'
  interact.append({'name':name,'sid':e['sid'],'file':d.path,'offset':p,'payload_size':512,'hud_name_list_present':name in gui_names,'logical_command_candidate':fmt(d.value(p+0x198)),'command_confidence':'HIGH CONFIDENCE: slot repeats logical commands, native field declaration unavailable','widget_path':fmt(d.value(p+0xc8)) if d.ptr(p+0xc8) else None,'behavior_candidate':behavior,'behavior_confidence':'INFERRED from definition name; numeric hold/mash parameters untyped','icon':'UNKNOWN / NEEDS NATIVE RESEARCH; gen:interact and accessibility triangle sounds are references, not proof of active key binding','availability_conditions':'UNKNOWN / NEEDS NATIVE RESEARCH; native evaluator plus scripted enable/disable/override','progress_indicator':'UNKNOWN / NEEDS NATIVE RESEARCH; widget and hybrid parameter references retained','fields':words,'related_files':cross})
 for name,pos in gui_names.items():
  if not any(i['name']==name for i in interact):interact.append({'name':name,'sid':f'{fnv1a64(name):016X}','file':gui.path,'string_offset':pos,'record_type':'hud-name-list-only','confidence':'CONFIRMED readable name; gameplay definition with same name absent','behavior_candidate':'UNKNOWN / NEEDS NATIVE RESEARCH'})
 dump(ROOT/'databases/interaction_definitions.json',{'gameplay_definition_count':273,'hud_interact_name_count':len(gui_names),'records':interact})
 with (ROOT/'databases/interaction_definitions.csv').open('w') as f:
  w=csv.writer(f,lineterminator="\n");w.writerow(['name','file','offset','logical_command_candidate','behavior_candidate','widget_path','confidence'])
  for r in interact:w.writerow([r['name'],r['file'],hex(r.get('offset',r.get('string_offset',0))),r.get('logical_command_candidate',''),r.get('behavior_candidate'),r.get('widget_path',''),r.get('confidence','member interpretation partly inferred')])
 # Module registry supplies exact declared import/export relationships, not runtime residency.
 d=DC(ROOT/'.private/extracted/dc1/modules.bin','dc1/modules.bin',db);p=d.entries[0]['offset'];n=d.q(p);table=d.q(p+8);d.check(table,n*40);modules=[]
 for i in range(n):
  m=table+i*40;row={'name':d.string(d.q(m)),'sid':f'{d.q(m+8):016X}','registered_size':d.q(m+16),'offset':m}
  for off,key in [(24,'imports'),(32,'exports')]:
   a=d.q(m+off)
   if not a:row[key]=[];continue
   count=d.u32(a);base=d.q(a+8);d.check(base,count*8);row[key]=[d.name(d.q(base+j*8)) for j in range(count)]
  modules.append(row)
 dump(ROOT/'databases/modules.json',modules)
 # State graph/evidence files follow requested deep-trace sequence.
 for category,files in PRIMARY.items():
  out=ROOT/'interactions'/category;selected=[c for f in files for c in cf[f]];selected_fns=[f for f in functions if f['file'] in files]
  dump(out/'evidence.json',{'sources':files,'state_scripts':[s for f in files for s in sf[f]],'functions':selected_fns,'calls':selected,'note':'Static may-call evidence; instructions and original scripts remain private.'})
  md=f'# {category.title()}: static evidence\n\nCONFIRMED means a structure or call instruction is present. Branch reachability, native implementation and object configuration remain separate questions. Call offset is a hexadecimal byte offset in the original module; source SHA-256 is in `databases/file_manifest.json`. `result(...)` references another call in the same lambda, not its presumed return value.\n'
  for f in files:
   md+=f'\n## `{f}`\n\n{len(cf[f])} call sites; {len(sf[f])} state scripts; {len(ef[f])} exported entries.\n'
   if not cf[f] and ef[f]:md+='\nThis module exports data structures. Zero script calls does not mean zero engine behavior.\n'
   for ss in sf[f]:
    md+=f'\n### `{ss["name"]}`\n\nInitial state field: `{ss["initial_state"]}`. A zero SID does not prove that the first table state starts automatically.\n\n'
    state_names=[s['name'] for s in ss['states']];edges=[]
    for c in cf[f]:
     if c['target']==['sid','go'] and c['arguments'] and c['arguments'][0][0]=='sid':
      dest=c['arguments'][0][1]
      for context in c['contexts']:
       if context['script']==ss['name'] and dest in state_names:edges.append((context['state'],dest,c['id'],context['event'] or context['block']))
    ids={s:'s'+str(i) for i,s in enumerate(state_names)};mermaid='stateDiagram-v2\n'
    for s in state_names:mermaid+=f'    state "{s}" as {ids[s]}\n'
    if ss['initial_state'] in ids:mermaid+=f'    [*] --> {ids[ss["initial_state"]]}\n'
    for source,dest,call,event in sorted(set(edges)):
     if source in ids:mermaid+=f'    {ids[source]} --> {ids[dest]}: {event}\n'
    write(out/(ss['name']+'.mmd'),mermaid);md+='```mermaid\n'+mermaid+'```\n\nEdges represent explicit `go` call sites, including conditional alternatives. Same-target edges can occur in different tracks; this is not a guaranteed linear execution trace.\n'
    for st in ss['states']:
     sc=[c for c in cf[f] if any(ctx['script']==ss['name'] and ctx['state']==st['name'] for ctx in c['contexts'])];meaning=[c for c in sc if MEANINGFUL.search(call_label(c))];unique={}
     for c in sorted(meaning,key=lambda c:c['offset']):unique.setdefault(call_label(c),c)
     listeners=[b['event'] for b in st['blocks'] if b['kind']=='event'];md+=f'\n#### `{st["name"]}`\n\n{len(sc)} call sites. Event listeners: '+(', '.join('`'+s+'`' for s in listeners) or 'none')+'.\n\n| Call target | Example offset | Argument evidence |\n| --- | --- | --- |\n'
     for name,c in unique.items():
      args=', '.join(fmt(a) for a in c['arguments']);args=args.replace('|','\\|').replace('\n',' ')
      md+=f'| `{name}` | `0x{c["offset"]:X}` | {args[:210]} |\n'
   named=[fn for fn in selected_fns if fn['file']==f and not fn['contexts']]
   if named:md+='\nNamed/global/embedded helpers: '+', '.join('`'+fn['name']+'`' for fn in named[:30])+'.\n'
  write(out/'evidence.md',md)
 # Engine API boundary inventory.
 defs=collections.defaultdict(list)
 for fn in functions:
  if not fn['name'].startswith('lambda@'):defs[fn['name']].append(fn['id'])
 api=collections.defaultdict(lambda:{'calls':0,'opcodes':collections.Counter(),'files':set(),'definitions':[]})
 for c in calls:
  if c['target'][0]!='sid':continue
  name=c['target'][1];r=api[name];r['calls']+=1;r['opcodes'][c['opcode']]+=1;r['files'].add(c['file']);r['definitions']=defs.get(name,[])
 dump(ROOT/'databases/engine_api.json',[dict(name=name,call_count=r['calls'],opcodes=dict(r['opcodes']),source_files=sorted(r['files']),script_definitions=r['definitions'],boundary='script lambda present' if r['definitions'] else 'HIGH CONFIDENCE native/imported boundary when CallFf; implementation unknown') for name,r in sorted(api.items())])
 # Level composition examples.
 for f in ['dc1/ss-patrol/ss-pat-library-jokebook-interaction.bin','dc1/ss-patrol/ss-pat-library-globe-interact.bin','dc1/ss-patrol/ss-pat-library-heater-interaction.bin']:
  title=Path(f).stem;out=ROOT/'level_design/examples';dump(out/(title+'.json'),{'file':f,'scripts':sf[f],'calls':cf[f]})
  md=f'# {title}\n\nCONFIRMED from `{f}`. This is level-specific orchestration; animation/dialogue assets are not included.\n\n| Context | Target | Offset | Argument evidence |\n| --- | --- | --- | --- |\n'
  for c in cf[f]:
   if c['target'][0]=='sid' and c['target'][1] not in ('get-self-id','event-arg-symbol','new-boxed-value'):
    md+='| '+','.join(x['state'] for x in c['contexts'])+' | `'+call_label(c)+'` | `'+hex(c['offset'])+'` | '+', '.join(fmt(x) for x in c['arguments']).replace('|','\\|')[:230]+' |\n'
  write(out/(title+'.md'),md)
 print('Reports complete',flush=True)
if __name__=='__main__':main()
