"""pickups: extract *player-inventory-t2* inv-item-def table (item id, HUD strings, max count, pickup looks/sfx).
Usage: python3 -I tools/analysis/pickups_inventory_table.py <player-inventory.bin.asm> <out.json>
Field meanings are labeled: 0x088 max-count is CONFIRMED (get-inventory-item-max-count reads +136); others INFERRED."""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pickups_asm_struct import parse_file, map_items
d = parse_file(sys.argv[1])
items = []
for key, v in map_items(d['*player-inventory-t2*']):
    row = {"item_id": key, "name_string": v.get('0x008'), "hud_name": v.get('0x010') if isinstance(v.get('0x010'), str) else None,
           "hud_name_single": v.get('0x018') if isinstance(v.get('0x018'), str) else None,
           "icon": v.get('0x038') if isinstance(v.get('0x038'), str) else None,
           "icon_small": v.get('0x048') if isinstance(v.get('0x048'), str) else None,
           "max_count_0x088": v.get('0x088'), "flags_0x068": v.get('0x068'), "flags_0x078": v.get('0x078'), "flags_0x08C": v.get('0x08C')}
    ip = v.get('0x0A0')
    if isinstance(ip, dict):
        looks = []
        lk = ip.get('0x010')
        if isinstance(lk, dict):
            arr = lk.get('0x008')
            if isinstance(arr, dict):
                for k2 in sorted([k for k in arr if not k.startswith('_')], key=lambda x: int(x, 0)):
                    a = arr[k2]
                    looks.append({"art_group": a.get('0x000'), "offset_xyz?": [a.get('0x01C'), a.get('0x020'), a.get('0x024')] if False else [a.get('0x018'), a.get('0x01C'), a.get('0x020')],
                                  "grip_anim": a.get('0x028') if isinstance(a.get('0x028'), str) else None,
                                  "sfx_a": a.get('0x038') if isinstance(a.get('0x038'), str) else None,
                                  "sfx_b": a.get('0x040') if isinstance(a.get('0x040'), str) else None,
                                  "rumble": a.get('0x060') if isinstance(a.get('0x060'), str) else None})
        row["item_pickup"] = {"looks": looks,
                              "shimmer": ip.get('0x020') if isinstance(ip.get('0x020'), str) else None,
                              "int_0x028": ip.get('0x028'), "int_0x02C": ip.get('0x02C'),
                              "sfx_pickup_a": ip.get('0x038'), "sfx_pickup_b": ip.get('0x040'),
                              "sfx_generic": ip.get('0x048'), "sfx_putaway": ip.get('0x050'),
                              "rumble": ip.get('0x058'), "rumble_soft": ip.get('0x060')}
    items.append(row)
json.dump({"source": "player-inventory.bin :: *player-inventory-t2* (map item-id -> inv-item-def)",
           "field_notes": {"0x088": "max carry count (CONFIRMED: script-user-funcs-impl get-inventory-item-max-count reads lookup-inv-item-def()+136)",
                           "0x0A0": "embedded item-pickup struct: looks[] (art-group, grip anim, sfx, rumble), shimmer effect, pickup/putaway sfx (field names INFERRED)"},
           "items": items}, open(sys.argv[2], 'w'), indent=1)
print(len(items), "items;", sum(1 for r in items if r.get('item_pickup')), "with item-pickup")
