"""safes_extract_code_notes.py - list *treasures* entries whose id/strings mention safe/code/combo/vault/keypad.
Fields per treasure-data struct (offsets observed in treasures.bin.asm): 0x000 id, 0x008 title, 0x010 subtitle?, 0x018 text,
0x028 chapter/activity-ish sid, 0x030 spawner/region string. Usage: python3 -I tools/analysis/safes_extract_code_notes.py"""
import re, sys, json
ASM = '.private/dconstruct_out/dc1/treasures.bin.asm'
L = open(ASM, encoding='utf-8', errors='replace').read().splitlines()
pat = re.compile(r'safe|code|combo|vault|keypad|generator-note', re.I)
out = []; seen = set()
for i, l in enumerate(L):
    m = re.match(r'\s*\[0x000\] sid: (collectible-\S+|siege-treasure\S*)$', l)
    if not m or m.group(1) in seen: continue
    f = {}
    for j in range(i, min(i + 12, len(L))):
        mm = re.match(r'\s*\[(0x0[0-9A-F]{2})\] (sid|string): "?([^"]*)"?$', L[j])
        if mm: f[mm.group(1)] = mm.group(3)
    blob = ' '.join(f.values())
    if pat.search(blob):
        seen.add(m.group(1))
        out.append({'treasure': f.get('0x000'), 'title': f.get('0x008'), 'text': f.get('0x018'),
                    'group': f.get('0x028'), 'spawner_or_region': f.get('0x030')})
json.dump(out, sys.stdout, indent=1)
