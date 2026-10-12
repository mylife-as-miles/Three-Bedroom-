#!/usr/bin/env python3
"""audio_mesh_config — parse mesh-audio-config.bin.asm (dconstruct) into a JSON table and validate the
sfx name-composition hypothesis  sfx-<mesh-material>-<suffix>  against all sfx-info entry names.

Usage: python3 -I tools/analysis/audio_mesh_config.py <out.json>
"""
import json, os, re, sys, collections

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DC = os.path.join(os.environ.get("TLOU2_PRIVATE", os.path.join(REPO, ".private")), "dconstruct_out", "dc1")


def blocks(path):
    cur, name = [], None
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^(\S+) = (\S+) \[", ln)
        if m:
            if name:
                yield name, cur
            name, cur = (m.group(1), m.group(2)), []
        elif name:
            cur.append(ln.rstrip("\n"))
    if name:
        yield name, cur


def parse_map(lines):
    out, cur, in_eff = [], None, False
    for ln in lines:
        m = re.match(r"^    \[(\d+)\] mesh-audio-config", ln)
        if m:
            cur = {"top": {}, "eff": {}}; out.append(cur); in_eff = False; continue
        if cur is None:
            continue
        if "mesh-effect-audio-config" in ln:
            in_eff = True; continue
        m = re.match(r"^(\s+)\[(0x[0-9A-F]+)\] (string|sid|int|float): (.*)$", ln)
        if m:
            ind, off, _t, v = m.groups()
            v = v.strip().strip('"')
            if in_eff and len(ind) == 8:
                cur["eff"][off] = v
            elif len(ind) == 6:
                in_eff = False
                cur["top"][off] = v
    return out


def main():
    out = sys.argv[1]
    path = os.path.join(DC, "mesh-audio-config.bin.asm")
    tables, suffixes = {}, {}
    for (name, typ), lines in blocks(path):
        if typ == "identifier-array":
            suffixes[name.strip("*")] = re.findall(r'string: "([^"]*)"', "\n".join(lines))
        elif typ == "map":
            tables[name.strip("*")] = parse_map(lines)
    # every sfx-info entry name in the audio corpus
    names = set()
    for dp, _d, fs in os.walk(DC):
        for f in fs:
            if f.endswith(".asm") and ("aud" in f or "audio" in dp):
                for ln in open(os.path.join(dp, f), encoding="utf-8", errors="replace"):
                    m = re.match(r"^(sfx-\S+) = sfx-info(?:-full)? \[", ln)
                    if m:
                        names.add(m.group(1))
    meshes = []
    for e in tables.get("mesh-audio-config", []):
        mat, handle = e["eff"].get("0x000", ""), e["eff"].get("0x008", "")
        if mat or handle:
            meshes.append({"mesh": e["top"].get("0x008"), "material": mat, "handle": handle})
    mats = collections.Counter(m["material"] for m in meshes if m["material"])
    handles = collections.Counter(m["handle"] for m in meshes if m["handle"])
    def coverage(prefixes, sfx_list):
        res = {}
        for p in prefixes:
            hit = [s for s in sfx_list if f"sfx-{p}-{s}" in names]
            res[p] = {"resolved": len(hit), "of": len(sfx_list), "examples": [f"sfx-{p}-{s}" for s in hit[:4]]}
        return res
    rope_mats = sorted({n[4:].split("-rope-")[0] for n in names if "-rope-" in n})
    rope_cov = coverage([m for m in rope_mats if len(m) < 12], suffixes.get("suffixes-mesh-effect-rope-material", []))
    res = {
        "source": "mesh-audio-config.bin (dconstruct asm)",
        "suffix_tables": suffixes,
        "mesh_effect_material_counts": dict(mats),
        "mesh_effect_handle_counts": dict(handles),
        "door_material_coverage": coverage(sorted(mats), suffixes.get("suffixes-mesh-effect-door-material", [])),
        "door_handle_coverage": coverage(sorted(handles), suffixes.get("suffixes-mesh-effect-door-handle", [])),
        "rope_material_coverage": rope_cov,
        "look_audio_config_meshes": [e["top"].get("0x008") for e in tables.get("look-audio-config", [])],
        "mesh_material_table": sorted(meshes, key=lambda m: m["mesh"] or ""),
        "sfx_entry_names_scanned": len(names),
    }
    json.dump(res, open(out, "w"), indent=1)
    print("meshes", len(meshes), "sfx names", len(names))
    for k in ("door_material_coverage", "door_handle_coverage", "rope_material_coverage"):
        print(k, {p: f'{v["resolved"]}/{v["of"]}' for p, v in res[k].items()})


if __name__ == "__main__":
    main()
