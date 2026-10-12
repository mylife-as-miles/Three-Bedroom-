#!/usr/bin/env python3
"""investigate_anim_states.py - list actor states + transitions (name -> target, fade) + node type/anim
from a dconstruct .asm actor-state-list (e.g. anim-player/player-investigate.bin.asm)."""
import re, sys
lines = open(sys.argv[1], encoding='utf-8', errors='replace').read().split('\n')
state = None
for i, l in enumerate(lines):
    m = re.match(r'^      \[0x000\] string: "(.*)"', l)
    if m:
        state = m.group(1); print(f'\n## {state}')
        # node info
        for j in range(i, i + 12):
            n = re.match(r'^      \[0x018\] (anim-node-[\w-]+)', lines[j])
            if n:
                sids = []
                for k in range(j + 1, j + 30):
                    s = re.search(r'sid: (\S+)', lines[k])
                    if s: sids.append(s.group(1))
                print('   node', n.group(1), sids[:6]); break
        continue
    m = re.match(r'^(\s+)\[0x000\] anim-transition-condition', l)
    if m and state:
        # walk back to find transition name: nearest preceding "[0x000] sid:" with less indent
        ind = len(m.group(1))
        name = None
        for j in range(i - 1, i - 12, -1):
            s = re.match(r'^(\s+)\[0x000\] sid: (\S+)', lines[j])
            if s and len(s.group(1)) < ind - 4: name = s.group(2); nind = len(s.group(1)); break
        if not name: continue
        tgt = fade = None
        for j in range(i, i + 60):
            s = re.match(r'^(\s+)\[0x020\] sid: (\S+)', lines[j])
            if s and len(s.group(1)) == nind: tgt = s.group(2)
            f = re.match(r'^(\s+)\[0x038\] float: (\S+)', lines[j])
            if f and len(f.group(1)) == nind and tgt: fade = f.group(2); break
            if tgt and re.match(r'^(\s+)\[0x04C\]', lines[j]) and len(lines[j]) - len(lines[j].lstrip()) == nind: break
        print(f'   tr {name:10s} -> {tgt}  fade={fade}')
