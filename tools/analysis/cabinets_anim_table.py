"""cabinets: extract per-animation-set tuning table from ss-openable-cabinet dcpl (scavenge-init selection lambda).
Usage: python3 -I tools/analysis/cabinets_anim_table.py <ss-openable-cabinet.bin.dcpl> <out.json>"""
import re, sys, json
src = open(sys.argv[1]).read()
parts = re.split(r'set-symbol\(scav-enter-animation, string-to-symbol\("([a-z0-9-]+)"\)!, self\)!;', src)
rows = []
for name, body in zip(parts[1::2], parts[2::2]):
    body = body.split('} else')[0]
    r = {"enter": name}
    for k in ["scav-exit-animation", "scav-pickup-animation"]:
        m = re.search(r'set-symbol\(%s, string-to-symbol\("([a-z0-9-]+)"\)' % k, body); r[k.replace('scav-', '').replace('-animation', '')] = m and m.group(1)
    for k, v in re.findall(r'set-float\(([a-z-]+), ([0-9.]+), self\)', body): r[k] = float(v)
    for k, v in re.findall(r'set-int32\(([a-z-]+), (\d+), self\)', body): r[k] = int(v)
    for k, v in re.findall(r'set-boolean\(([a-z?-]+), (\d), self\)', body): r[k] = int(v)
    m = re.match(r'ellie-scav-(relaxed|tense|crouch)-cabinet-(low-)?(toward|against)-(\d+)cm-enter', name)
    r.update({"stance": m.group(1), "low_cab": bool(m.group(2)), "side": m.group(3), "nominal_cm": int(m.group(4))})
    r["note"] = "l-ik-on-frame is reduced by 6 after selection (scavenge-init)"
    rows.append(r)
json.dump({"source": "ss-t2/ss-openable-cabinet.bin :: scavenge-init (start block)", "sets": rows}, open(sys.argv[2], 'w'), indent=1)
print(len(rows))
for r in rows: print(r["stance"], "low" if r["low_cab"] else "high", r["side"], r["nominal_cm"], r.get("l-ik-on-frame"), r.get("l-ik-off-frame"), r.get("scav-enter-animation-exit-phase"), r.get("scav-pickup-animation-exit-phase"), r.get("scav-pickup-object-phase"), r.get("scav-pickup-object-stowe-phase"), r.get("handle-height-in-animation"), r.get("prefered-pickup-hand"), r.get("camera-required-low?",0), r.get("custom-abort-frame",0))
