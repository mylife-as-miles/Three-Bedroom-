"""safes_extract_activities.py - list collectible-stat objectives (e.g. safes-found bits) per activity
from dconstruct activities.bin.asm. Usage: python3 -I tools/analysis/safes_extract_activities.py [stat-sid]"""
import re, sys, json
ASM = '.private/dconstruct_out/dc1/activities.bin.asm'
stat = sys.argv[1] if len(sys.argv) > 1 else 'safes-found'
lines = open(ASM, encoding='utf-8', errors='replace').read().splitlines()
act = None; out = []
for i, l in enumerate(lines):
    m = re.match(r'\s*\[\d+\] activity-data \[', l)
    if m:
        s = re.search(r'sid: (\S+)', lines[i+1]); act = s.group(1) if s else None
        t = re.search(r'sid: (\S+)', lines[i+2]); title = t.group(1) if t else None
    if re.search(r'\[0x020\] sid: ' + re.escape(stat) + r'$', l):
        # walk back to struct start
        j = i
        while not re.search(r'anonymous struct', lines[j]): j -= 1
        obj = re.search(r'sid: (\S+)', lines[j+1]).group(1)
        txt = re.search(r'sid: (\S+)', lines[j+2]).group(1)
        k = i
        while '[0x04C]' not in lines[k]: k += 1
        bit = int(re.search(r'int: (-?\d+)', lines[k]).group(1))
        out.append({'activity': act, 'chapter_title': title, 'objective': obj, 'objective_text': txt, 'bit': bit})
json.dump(out, sys.stdout, indent=1)
