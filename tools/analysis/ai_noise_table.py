#!/usr/bin/env python3
"""ai_noise_table — dump the first float (INFERRED: audible radius, m) of every noise-data entry in
audio-gameplay.bin noise-settings maps. Run from repo root: python3 -I tools/analysis/ai_noise_table.py"""
import re, os, json
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
P = os.path.join(REPO, ".private/dconstruct_out/dc1/audio-gameplay.bin.asm")
tables = {}; cur = None; inval = False; name = None
for line in open(P, encoding="utf-8", errors="ignore"):
    m = re.match(r"^\*(noise-settings-[\w-]+)\* = map", line)
    if m: cur = m.group(1); tables[cur] = {}; inval = False; continue
    if cur is None: continue
    if "values array" in line: inval = True; continue
    if inval:
        m = re.match(r"\s+\[0x000\] sid: (\S+)", line)
        if m: name = m.group(1); continue
        m = re.match(r"\s+\[0x008\] float: (\S+)", line)
        if m and name: tables[cur][name] = float(m.group(1)); name = None
    if line.startswith("}"): cur = None
print(json.dumps(tables, indent=1))
