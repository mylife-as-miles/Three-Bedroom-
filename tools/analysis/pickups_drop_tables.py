"""pickups: summarize item-drop.bin class tables used by openables (cabinet/drawer) -> JSON.
Usage: python3 -I tools/analysis/pickups_drop_tables.py <item-drop.bin.asm> <out.json> [table ...]
Per-category 7 floats at +0x08..+0x20 are INFERRED to be per resource-difficulty probabilities."""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pickups_asm_struct import parse_file
d = parse_file(sys.argv[1])
names = sys.argv[3:] or ['*cabinet-drop-table*', '*drawer-drop-table*', '*rogue-cabinet-drop-table*', '*rogue-drawer-drop-table*', '*default-drop-table*']
def idx(o): return [o[k] for k in sorted([k for k in o if not k.startswith('_')], key=lambda x: int(x, 0))] if isinstance(o, dict) else []
out = {}
for n in names:
    t = d.get(n)
    if not t: continue
    cats = []
    for c in idx(t.get('0x008')):
        probs = [c.get(k) for k in ['0x008', '0x00C', '0x010', '0x014', '0x018', '0x01C', '0x020']]
        sub = c.get('0x028')
        items = []
        if isinstance(sub, dict):
            for it in idx(sub.get('0x000')):
                if isinstance(it, dict): items.append({"item": it.get('0x000'), "weight?": it.get('0x008')})
            ref = None
        else:
            ref = sub
        cats.append({"category": c.get('0x000'), "prob_per_difficulty?": probs, "type_table_items": items, "type_table_ref": ref})
    out[n] = cats
json.dump({"source": "item-drop.bin (data-only; no DC code references these tables -> consumed natively)", "tables": out}, open(sys.argv[2], 'w'), indent=1)
for n, cats in out.items():
    print(n); [print("  ", c['category'], c['prob_per_difficulty?'], [i['item'] for i in c['type_table_items']][:12], c['type_table_ref']) for c in cats]
