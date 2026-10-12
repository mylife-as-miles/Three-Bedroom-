#!/usr/bin/env python3
"""workbench_squash: compress dconstruct .dcpl boilerplate (variant unboxing chains,
animate_ option-array stores) so long state scripts can be read quickly.
Usage: python3 -I workbench_squash.py <file.dcpl> [start] [end]"""
import re, sys
p = sys.argv[1]; s = int(sys.argv[2]) if len(sys.argv) > 2 else 1; e = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
lines = open(p, encoding='utf-8', errors='replace').read().split('\n')
unbox = re.compile(r'^\s*(\}?\s*(else )?if \(var_\d+ && \*\(u16 \*\)\(var_\d+ \+ 12\) == [457]\) \{|var_\d+ = \*\(u64 \*\)var_\d+;|\*\(u64 \*\)var_\d+;|\} else \{|var_\d+ = 0;|\}|u16 var_\d+;)\s*$')
opt_key = re.compile(r'^\s*\*\(i32 \*\)\*\(\*(var_\d+) \+ \((\d+) \* 8\)\) = (\d+);')
opt_val = re.compile(r'^\s*\*\((u64|f32|i32|u8) \*\)\(\*\(\*(var_\d+) \+ \((\d+) \* 8\)\) \+ 8\) = (.*);')
out = []; pend = {}
i = s - 1
while i < min(e, len(lines)):
    l = lines[i]
    m = opt_key.match(l)
    if m:
        pend.setdefault(m.group(1), []).append([m.group(3), None]); i += 1; continue
    m = opt_val.match(l)
    if m:
        v = m.group(4)
        if m.group(2) in pend and (v != "0" or pend[m.group(2)][-1][1] is None):
            pend[m.group(2)][-1][1] = v
        i += 1; continue
    # collapse unbox chains
    if re.match(r'^\s*if \(var_\d+ && \*\(u16 \*\)\(var_\d+ \+ 12\) == 7\) \{', l):
        j = i
        while j < len(lines) and unbox.match(lines[j]) and j - i < 12:
            j += 1
        out.append(f"{i+1:5d}: {l[:len(l)-len(l.lstrip())]}<unbox>")
        i = j; continue
    for var, kv in list(pend.items()):
        if var in l and ('animate' in l or 'stop-animating' in l or '(' in l):
            l = l.replace(var, '{' + ', '.join(f"{k}:{v}" for k, v in kv) + '}')
            del pend[var]
    if re.match(r'^\s*u64\? var_\d+ = #%alloc-array', l):
        i += 1; continue
    out.append(f"{i+1:5d}: {l}")
    i += 1
print('\n'.join(out))
