"""pickups: extract art-group -> (grip anim, scale) table from ss-openable-grips dcpl.
Usage: python3 -I tools/analysis/pickups_extract_grips.py <ss-openable-grips.bin.dcpl> <out.json>"""
import re, sys, json
src = open(sys.argv[1]).read()
body = src[src.index('openable-grip-and-scale(u64? arg_0)'):]
pat = re.compile(r'arg_0 == ([a-z0-9-]+)\) \{\s*set-float\(pickup-obj-scale, ([0-9.]+), self\)!;\s*(?:var_0 = )?set-symbol\(pickup-grip-anim, ([a-z0-9-]+), self\)!;(?:\s*var_0 = set-symbol\(pickup-collect-anim, ([a-z0-9-]+), self\))?')
rows, seen = [], {}
for ag, sc, anim, coll in pat.findall(body):
    dup = ag in seen
    rows.append({"art_group": ag, "scale": float(sc), "grip_anim": anim, "shadowed_duplicate": dup, "collect_anim": coll or "collect (default)"})
    seen[ag] = 1
mir = src[:src.index('openable-grip-and-scale(u64? arg_0)')]
lh = re.findall(r'== (ellie-scav-pickup-grip-r-hand--[a-z0-9-]+)\) \{\s*var_1 = set-boolean\(pickup-grip-l-hand, 1', mir)
m = re.search(r'\} else \{\s*set-float\(pickup-obj-scale, ([0-9.]+), self\)!;\s*var_0 = set-symbol\(pickup-grip-anim, ([a-z0-9-]+)', body)
fallback = {"scale": float(m.group(1)), "grip_anim": m.group(2)} if m else None
json.dump({"fallback": fallback, "source": "ss-t2/ss-openable-grips.bin", "grip_and_scale": rows,
           "left_hand_mirror_supported_grips": lh}, open(sys.argv[2], 'w'), indent=1)
print(len(rows), "rows", len(seen), "unique", len(lh), "lh-mirror")
