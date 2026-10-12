#!/usr/bin/env python3
"""investigate_params_dump.py - parse every `investigate-params` struct out of a dconstruct .asm
listing (default: investigate.bin.asm) and emit JSON {name: {offset_hex: value}} plus a per-offset
variability summary. Usage: python3 -I tools/analysis/investigate_params_dump.py [asm] [out.json]"""
import sys, re, json, collections
asm = sys.argv[1] if len(sys.argv) > 1 else '.private/dconstruct_out/dc1/investigate.bin.asm'
out = sys.argv[2] if len(sys.argv) > 2 else None
head = re.compile(r'^\*?([^\s=]+?)\*? = ([\w-]+) \[0x[0-9A-F]+\] \{')
field = re.compile(r'^  \[0x([0-9A-F]+)\] (\w+): ?(.*)$')
sub = re.compile(r'^    \[0x([0-9A-F]+)\] (\w+): ?(.*)$')
entries = {}; cur = None; curtype = None; vec = None
for line in open(asm, encoding='utf-8', errors='replace'):
    line = line.rstrip('\n')
    m = head.match(line)
    if m:
        cur = m.group(1) if m.group(2) == 'investigate-params' else None
        curtype = m.group(2)
        if cur: entries[cur] = {}
        vec = None; continue
    if cur is None: continue
    m = field.match(line)
    if m:
        off, typ, val = m.groups()
        if typ == 'vector':
            vec = '0x' + off; entries[cur][vec] = []
        else:
            vec = None
            v = val.strip().strip('"')
            if typ == 'float': v = float(v)
            elif typ == 'int': v = int(v)
            entries[cur]['0x' + off] = v
        continue
    m = sub.match(line)
    if m and vec:
        typ, val = m.group(2), m.group(3)
        entries[cur][vec].append(float(val) if typ == 'float' else int(val) if typ == 'int' else val)
        continue
    if line.startswith('}'):
        cur = None
summary = collections.OrderedDict()
offs = sorted({o for e in entries.values() for o in e}, key=lambda x: int(x, 16))
for o in offs:
    vals = collections.Counter(json.dumps(e.get(o)) for e in entries.values())
    summary[o] = {'distinct': len(vals), 'top': vals.most_common(6)}
res = {'source': asm, 'count': len(entries), 'offset_summary': summary, 'entries': entries}
if out:
    json.dump(res, open(out, 'w'), indent=1)
print('entries', len(entries))
for o, s in summary.items():
    print(o, s['distinct'], s['top'][:6])
