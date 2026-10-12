"""pickups: parse drawer-pickup-offset.bin.asm map entries into JSON (field offsets kept raw).
Usage: python3 -I tools/analysis/pickups_parse_offset_maps.py <drawer-pickup-offset.bin.asm> <out.json>"""
import re, sys, json
lines = open(sys.argv[1]).read().splitlines()
out, cur_map, cur = {}, None, None
for ln in lines:
    m = re.match(r'^(\*[a-z0-9-]+\*) = map', ln)
    if m: cur_map = m.group(1); out[cur_map] = []; continue
    m = re.match(r'^\s+\[\d+\] ([a-z0-9-]+) \[0x[0-9A-F]+\] \{', ln)
    if m and cur_map: cur = {"struct": m.group(1), "fields": {}}; out[cur_map].append(cur); continue
    m = re.match(r'^\s+\[(0x[0-9A-F]+)\] (sid|int|float): (\S+)', ln)
    if m and cur is not None:
        k, t, v = m.groups()
        cur["fields"][k] = v if t == 'sid' else (float(v) if t == 'float' else int(v))
res = {}
for name, rows in out.items():
    res[name] = [{"key": r["fields"].get("0x000"), "struct": r["struct"],
                  "values": {k: v for k, v in r["fields"].items() if k != "0x000"}} for r in rows]
json.dump({"source": "drawer-pickup-offset.bin (data-only; no DC code reads these symbols; modules.bin lists them)",
           "maps": res}, open(sys.argv[2], 'w'), indent=1)
for n, r in res.items(): print(n, len(r))
