"""pickups: tabulate pickup/inventory functions from databases/functions.json.
Usage: python3 -I tools/analysis/pickups_fn_table.py <regex> [out.json]"""
import json, re, sys
d = json.load(open('databases/functions.json'))
rx = re.compile(sys.argv[1])
rows = []
for name, v in sorted(d.items()):
    if rx.search(name):
        rows.append({"name": name, "kind": v.get("kind"), "calls": v.get("calls"), "files": v.get("files"),
                     "argc": list((v.get("argc") or {}).keys()), "defined_in": v.get("dc_defined_in"),
                     "native_address": v.get("native_address"),
                     "sample_callers": (v.get("sample_callers") or [])[:4]})
for r in rows:
    print(f"{r['name']:60s} {r['kind']:18s} calls={r['calls']:<5} files={r['files']:<4} argc={','.join(r['argc'])} def={';'.join(r['defined_in'] or [])} {r['native_address'] or ''}")
if len(sys.argv) > 2: json.dump(rows, open(sys.argv[2], 'w'), indent=1)
