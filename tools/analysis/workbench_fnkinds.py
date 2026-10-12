#!/usr/bin/env python3
"""workbench_fnkinds: print kind/defined_in/call-count for each function name given on stdin or argv.
Usage: python3 -I tools/analysis/workbench_fnkinds.py name1 name2 ...  (or pipe names, one per line)"""
import json, sys, os
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
d = json.load(open(os.path.join(root, 'databases', 'functions.json')))
names = sys.argv[1:] or [l.strip() for l in sys.stdin if l.strip()]
for n in names:
    e = d.get(n)
    if not e:
        print(f"{n:55s} MISSING"); continue
    print(f"{n:55s} {e.get('kind'):20s} calls={e.get('calls')} files={e.get('files')} def={','.join(e.get('dc_defined_in') or [])}")
