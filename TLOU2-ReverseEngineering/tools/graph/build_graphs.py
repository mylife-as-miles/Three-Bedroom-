#!/usr/bin/env python3
"""Render dependency graphs as DOT; event matches remain explicitly candidate edges."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'analysis'))
from data import ROOT,load
from corpus import dump
modules=load('modules.json');out=ROOT/'databases/graphs';out.mkdir(parents=True,exist_ok=True)
q=json.dumps
selected={m['name'] for m in modules if any(x in m['name'] for x in ['ss-openable-drawer','ss-openable-cabinet','ss-workbench','ss-investigate-object','ss-examine','ss-tumbler-safe','ss-hud2-lock-minigame'])}
lines=['digraph modules {','rankdir=LR;']
for m in modules:
 if m['name'] in selected:
  for i in m['imports']:lines.append(f'{q(m["name"])} -> {q(i)} [label="declared import"];')
lines.append('}');(out/'core_module_dependencies.dot').write_text('\n'.join(lines)+'\n')
events=load('event_graph.json')['events'];lines=['digraph power {','rankdir=LR;'];power={name:value for name,value in events.items() if any(s in name for s in ['generator','power','keypad-success','opened-safe'])}
for name,data in power.items():
 for prod in data['producers']:lines.append(f'{q(prod["file"])} -> {q("event:"+name)} [label={q(hex(prod["offset"])+" emission")}];')
 for listener in data['listeners']:lines.append(f'{q("event:"+name)} -> {q(listener["file"]+"::"+listener["state"])} [style=dashed,label="candidate listener; receiver not verified"];')
lines.append('}');(out/'power_lock_event_candidates.dot').write_text('\n'.join(lines)+'\n');dump(out/'power_lock_event_candidates.json',{'confidence':'CONFIRMED emission/listener records; cross-file delivery INFERRED unless actor identity verified','events':power});print('Graphviz DOT and event graph artifacts written')
