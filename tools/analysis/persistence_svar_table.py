#!/usr/bin/env python3
"""persistence_svar_table — parse *global-player-stats* (player-stat.bin) into name/title/flags rows and
cross-reference which stats DC scripts write (set-svar*/increment-svar) or level-sets read (stat-value?).
Run from repo root: python3 -I tools/analysis/persistence_svar_table.py [--json]"""
import re, os, sys, json, collections
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D = os.path.join(REPO, ".private/dconstruct_out/dc1")
rows = []; cur = None
for line in open(os.path.join(D, "player-stat.bin.asm"), encoding="utf-8", errors="ignore"):
    if re.match(r"\s+\[\d+\] anonymous struct", line):
        cur = {"name": None, "title": None, "flags": None}; rows.append(cur); continue
    if cur is None: continue
    m = re.match(r"\s+\[0x000\] sid: (\S+)", line)
    if m and cur["name"] is None: cur["name"] = m.group(1); continue
    m = re.match(r"\s+\[0x008\] sid: (\S+)", line)
    if m and cur["title"] is None: cur["title"] = m.group(1); continue
    m = re.match(r"\s+\[0x010\] int: (-?\d+)", line)
    if m and cur["flags"] is None: cur["flags"] = int(m.group(1))
    if line.startswith("*pickup-cluster-time*"): break
names = {r["name"] for r in rows}
JUNK = {"*", "arg", "u64?", "ss-svar", "tag-symbol", "var"}  # decompiler tokens, not svar names
written = collections.Counter(); read = collections.Counter()
for dp, _, fs in os.walk(D):
    for f in fs:
        if not f.endswith(".dcpl"): continue
        t = open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r"\b(?:set-svar(?:-as-boolean|-bit)?|increment-svar|increment-stat)\(([a-z0-9?!*-]+)", t): written[m.group(1)] += 1
        for m in re.finditer(r"\b(?:get-svar(?:-as-boolean|-bit)?|stat-value\?)\(([a-z0-9?!*-]+)", t): read[m.group(1)] += 1
flagh = collections.Counter(r["flags"] for r in rows)
out = {"stats": len(rows), "flag_histogram": flagh.most_common(),
       "script_written_names": len(written), "written_not_in_table_count": sum(1 for n in written if n not in names and n not in JUNK), "written_not_in_table": sorted(n for n in written if n not in names and n not in JUNK)[:60],
       "read_not_in_table": sorted(n for n in read if n not in names and n not in JUNK)[:60],
       "titled_stats": sum(1 for r in rows if r["title"] and r["title"].startswith("STAT_")),
       "flags_of_written": collections.Counter(next((r["flags"] for r in rows if r["name"] == n), None) for n in written).most_common()}
if "--json" in sys.argv: print(json.dumps(rows, indent=0))
else: print(json.dumps(out, indent=1))
