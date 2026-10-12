#!/usr/bin/env python3
"""workbench_extract_data: extract workbench-relevant data tables from dconstruct .asm listings.
Outputs JSON to stdout with:
  upgrade_costs: *weapon-upgrade-bundles* (+ grounded override) per weapon -> bundle id, label, cost item/counts, stat refs, craft sfx
  workbench_weapons: per character map (*workbench-weapons-ellie/abby*, t2r variants) -> per-weapon key fields + anim-state sids + upgrade-def keys
Usage: python3 -I tools/analysis/workbench_extract_data.py <dconstruct_out/dc1 dir>
Data stays private: write output under .private/ unless only derived numeric tables are needed."""
import re, sys, json, os
base = sys.argv[1]
def lines(f): return open(os.path.join(base, f), encoding='utf-8', errors='replace').read().split('\n')
ind = lambda l: len(l) - len(l.lstrip(' '))

def block(ls, start):
    """return index range [start, end) of block opened on line start (ends at matching dedent '}')."""
    i0 = ind(ls[start]); j = start + 1
    while j < len(ls) and not (ls[j].strip() == '}' and ind(ls[j]) == i0): j += 1
    return start, j + 1

def bundles(ls, start, stop):
    out = {}
    i = start
    while i < stop:
        m = re.match(r'^    \[\d+\] weapon-upgrade-bundles', ls[i])
        if not m: i += 1; continue
        b0, b1 = block(ls, i)
        weapon = re.search(r'sid: (\S+)', ls[i+1]).group(1)
        ents = []
        j = b0
        while j < b1:
            if re.match(r'^          \[\d+\] anonymous struct', ls[j]):
                e0, e1 = block(ls, j); seg = ls[e0:e1]
                g = lambda off, kind='sid': next((re.search(kind + r': (.*)$', s).group(1).strip('"') for s in seg if re.match(r'^            \[' + off + r'\] ' + kind + ':', s)), None)
                cost = []
                for k, s in enumerate(seg):
                    mm = re.match(r'^                  \[0x000\] sid: (\S+)', s)
                    if mm:
                        cnts = [int(re.search(r'int: (-?\d+)', t).group(1)) for t in seg[k:k+12] if re.match(r'^                        \[0x000\] int:', t)]
                        cost.append({'item': mm.group(1), 'counts': cnts})
                refs = []
                in_ref = False
                for s in seg:
                    if re.match(r'^            \[0x028\] weapon-upgrade-ref-array', s): in_ref = True; continue
                    if in_ref and re.match(r'^            \[0x030\]', s): break
                    if in_ref:
                        a = re.match(r'^                  \[0x000\] int: (-?\d+)', s); b = re.match(r'^                  \[0x004\] int: (-?\d+)', s)
                        if a: refs.append([int(a.group(1))])
                        if b and refs: refs[-1].append(int(b.group(1)))
                ents.append({'id': g('0x000'), 'label': g('0x010', 'string'), 'cost': cost, 'stat_refs_type_idx': refs,
                             'title_loc': g('0x038'), 'craft_sfx': g('0x050'), 'icon': g('0x060', 'string')})
                j = e1
            else: j += 1
        out[weapon] = ents
        i = b1
    return out

wu = lines('weapon-upgrades.bin.asm')
idx = {re.match(r'^(\*\S+\*)', l).group(1): n for n, l in enumerate(wu) if re.match(r'^\*\S+\* =', l)}
names = [l.split('sid: ')[1] for l in wu[idx['*weapon-upgrade-type-names*']:idx['*weapon-upgrade-bundles*']] if 'sid: ' in l]
res = {'weapon_upgrade_type_names': names,
       'upgrade_costs': bundles(wu, idx['*weapon-upgrade-bundles*'], idx['*weapon-upgrade-bundles-grounded-override*']),
       'upgrade_costs_grounded_override': bundles(wu, idx['*weapon-upgrade-bundles-grounded-override*'], len(wu))}

OFF = {'0x008': 'parts_look', '0x010': 'parts_is_weapon_process', '0x018': 'mag_mesh_default', '0x020': 'mag_upgrade_id',
       '0x030': 'bullets_lost_flag', '0x038': 'attach_point', '0x040': 'investigate_params', '0x048': 'pan_cam_key',
       '0x068': 'f104_swap_backpack_phase', '0x078': 'f120_menu_push_phase', '0x090': 'f144_exit_backpack_phase', '0x0A0': 'i160_exit_key61',
       '0x0A4': 'f164_exit_key60', '0x150': 'f336_show_upgrade_screen_phase', '0x168': 'f360_alt_show_upgrade_phase',
       '0x190': 'f400_assemble_interrupt_phase', '0x194': 'f404_hide_upgrade_screen_phase', '0x1A0': 'f416_apply_phase_default',
       '0x1A4': 'f420_menu_fade_in_phase_default', '0x1C8': 'invalid_flag_456'}
STATES = {'0x060': 'enter', '0x080': 'enter_abort', '0x088': 'exit', '0x0A8': 'idle', '0x0B8': 'idle_alt', '0x0C0': 'idle_on_table',
          '0x0D0': 'putback', '0x0F8': 'putback_alt', '0x100': 'pullout', '0x128': 'pullout_alt', '0x130': 'disassemble', '0x160': 'disassemble_alt',
          '0x170': 'assemble', '0x198': 'apply_upgrade_default'}
def weapons(fname):
    ls = lines(fname); out = {}
    for n, l in enumerate(ls):
        m = re.match(r'^(\*\S+-workbench-weapon\*) = workbench-weapon-def', l)
        if not m: continue
        b0, b1 = block(ls, n); seg = ls[b0:b1]; d = {'states': {}, 'upgrades': {}}
        for k, s in enumerate(seg):
            t = re.match(r'^  \[(0x[0-9A-F]{3})\] (\S+?):? (.*)$', s)
            if not t: continue
            off, kind, val = t.groups()
            if off in OFF and kind in ('sid', 'string', 'float', 'int'): d[OFF[off]] = val.strip('"')
            if off in STATES and kind == 'workbench-anim-state-def':
                d['states'][STATES[off]] = re.search(r'sid: (\S+)', seg[k+2]).group(1) if 'sid:' in seg[k+2] else None
            if off == '0x000' and kind == 'map':
                keys = []
                for s2 in seg[k+2:k+40]:
                    if re.match(r'^      \[\d+\] sid:', s2): keys.append(s2.split('sid: ')[1])
                    elif 'values array' in s2: break
                d['upgrade_keys'] = keys
        out[m.group(1)] = d
    return out
for f in ['workbench-settings-ellie.bin.asm', 'workbench-settings-abby.bin.asm', 't2r-workbench-settings-ellie.bin.asm', 't2r-workbench-settings-abby.bin.asm', 'workbench-settings.bin.asm']:
    res.setdefault('workbench_weapons', {})[f] = weapons(f)
print(json.dumps(res, indent=1))
