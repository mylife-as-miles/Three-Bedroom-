#!/usr/bin/env python3
"""notes_treasures_dump.py - parse the *treasures* treasure-data-array in treasures.bin.asm into a
compact JSON table (top-level scalar fields per record, keyed by hex offset, plus named aliases for
fields whose use is confirmed from ss-investigate-object.dcpl). Usage:
  python3 -I tools/analysis/notes_treasures_dump.py [treasures.bin.asm] [out.json]"""
import re, sys, json, collections
src = sys.argv[1] if len(sys.argv) > 1 else '.private/dconstruct_out/dc1/treasures.bin.asm'
out = sys.argv[2] if len(sys.argv) > 2 else None
L = open(src, encoding='utf-8', errors='replace').read().split('\n')
start = next(i for i, l in enumerate(L) if l.startswith('*treasures* = treasure-data-array'))
recs = []; cur = None
rec_hdr = re.compile(r'^    \[\d+\] anonymous struct')
fld = re.compile(r'^      \[0x([0-9A-F]+)\] (\w[\w-]*)(?: \[0x[0-9A-F]+\])?:? ?(.*)$')
tl = re.compile(r'^            \[0x0(08|10|18|20)\] sid: (\S+)')
for l in L[start:]:
    if rec_hdr.match(l):
        cur = {'_timeline': []}; recs.append(cur); continue
    if cur is None: continue
    m = fld.match(l)
    if m:
        off, typ, val = m.groups(); val = val.strip().strip('"')
        if typ in ('sid', 'string'): cur['0x' + off] = val
        elif typ == 'int': cur['0x' + off] = int(val)
        elif typ == 'float': cur['0x' + off] = float(val)
        else: cur['0x' + off] = '<' + typ + '>'
        continue
    m = tl.match(l)
    if m: cur['_timeline'].append(m.group(2))
    if l.startswith('}'): break
alias = {'0x000': 'treasure-id', '0x008': 'title-cipher (+8)', '0x010': 'location-cipher (+16)',
         '0x018': 'front-text-cipher (+24)', '0x020': 'back-text-cipher (+32)'}
for r in recs:
    tlv = r.pop('_timeline'); r['timeline_chapters'] = tlv[0::4] if tlv else []
summ = collections.OrderedDict()
for o in sorted({k for r in recs for k in r if k.startswith('0x')}, key=lambda x: int(x, 16)):
    c = collections.Counter(json.dumps(r.get(o)) for r in recs)
    summ[o] = {'alias': alias.get(o), 'distinct': len(c), 'top': c.most_common(8)}
prefix = collections.Counter(re.sub(r'^(collectible|coll)-([a-z]+)-.*', r'\1-\2', r['0x000']) for r in recs)
kind = collections.Counter(next((w for w in ('note', 'card', 'coin', 'journal', 'map', 'manual', 'photo', 'safe', 'artifact', 'letter') if w in r['0x000']), 'other') for r in recs)
res = {'source': src, 'count': len(recs), 'field_summary': summ, 'id_kind_counts': kind, 'records': recs}
if out: json.dump(res, open(out, 'w'), indent=1)
print('records', len(recs)); print('kinds', dict(kind))
for o, s in summ.items(): print(o, s['alias'], s['distinct'], s['top'][:5])
