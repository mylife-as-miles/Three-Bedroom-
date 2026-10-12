#!/usr/bin/env python3
"""doors_diff_interact_defs.py - compare game-interactable-def entries in interactable.bin.asm.

Usage (from repo root, always with -I):
  python3 -I tools/analysis/doors_diff_interact_defs.py '<regex on def name>' [--json out.json]

Parses only TOP-LEVEL fields (two-space indent) of each `name = game-interactable-def [...] {` block,
records nested struct types (e.g. gui2-attachable-params) by offset, and prints the offsets whose
values differ between the selected defs. With --json, writes {name: {offset: value}} plus a
`differing_offsets` list. Reads only the private dconstruct output; writes nothing else.
"""
import json
import re
import sys
from pathlib import Path

ASM = Path('.private/dconstruct_out/dc1/interactable.bin.asm')


def parse(txt):
    defs = {}
    cur = None
    for line in txt.splitlines():
        m = re.match(r'^(\S+) = game-interactable-def \[0x[0-9A-F]+\] \{$', line)
        if m:
            cur = m.group(1)
            defs[cur] = {}
            continue
        if cur is None:
            continue
        if line == '}':
            cur = None
            continue
        m = re.match(r'^  \[(0x[0-9A-F]+)\] (.*)$', line)
        if m:
            off, rest = m.group(1), m.group(2)
            mm = re.match(r'(\w+): (.*)', rest)
            if mm and mm.group(1) in ('sid', 'int', 'float', 'string'):
                defs[cur][off] = mm.group(2)
            else:  # nested struct header, e.g. "gui2-attachable-params [0x24800] {"
                defs[cur][off] = '<' + rest.split(' ')[0] + '>'
    return defs


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    pat = re.compile(sys.argv[1])
    out = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
    defs = parse(ASM.read_text())
    names = [n for n in defs if pat.search(n)]
    if not names:
        print('no defs match')
        return 1
    offs = sorted({o for n in names for o in defs[n]}, key=lambda o: int(o, 16))
    diff = [o for o in offs if o != '0x000' and len({defs[n].get(o) for n in names}) > 1]
    print('defs:', ', '.join(names))
    for o in diff:
        print(o, ' | '.join(f'{n}={defs[n].get(o)}' for n in names))
    if not diff:
        print('(all selected defs identical apart from their name)')
    if out:
        Path(out).write_text(json.dumps({'defs': {n: defs[n] for n in names},
                                         'differing_offsets': diff}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
