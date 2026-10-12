#!/usr/bin/env python3
"""audio_packages — inventory DC audio modules (audio-sfx/**, aud-sfx1/2, audio*.bin, vox-*):
entry-type counts, sfx-info-light category sids, and for each sfx name in audio-sfx/common-objects the
inferred trigger route (mesh-effect suffix composition / joint-suffixed IGC name / script call / unknown).

Usage: python3 -I tools/analysis/audio_packages.py <mesh_audio_material_table.json> <out.json>
"""
import json, os, re, sys, collections

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DC = os.path.join(os.environ.get("TLOU2_PRIVATE", os.path.join(REPO, ".private")), "dconstruct_out", "dc1")
TYPES = ("sfx-info", "sfx-info-light", "sfx-info-full", "vox-info", "mix-snapshot-info")


def scan(path):
    counts = collections.Counter(); cats = collections.Counter(); names = []
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    for i, ln in enumerate(lines):
        m = re.match(r"^(\S+) = (\S+) \[", ln)
        if not m:
            continue
        name, typ = m.groups()
        if typ in TYPES:
            counts[typ] += 1
            if typ == "sfx-info":
                names.append(name)
            if typ in ("sfx-info-light", "sfx-info-full"):
                for j in range(i + 1, min(i + 6, len(lines))):
                    mm = re.search(r"\[0x008\] sid: (\S+)", lines[j])
                    if mm:
                        cats[mm.group(1)] += 1; break
    return counts, cats, names


def main():
    mesh = json.load(open(sys.argv[1]))
    door_suf = mesh["suffix_tables"].get("suffixes-mesh-effect-door-material", [])
    handle_suf = mesh["suffix_tables"].get("suffixes-mesh-effect-door-handle", [])
    rope_suf = mesh["suffix_tables"].get("suffixes-mesh-effect-rope-material", [])
    gen_suf = mesh["suffix_tables"].get("suffixes-general-effect", [])
    mats = set(mesh["mesh_effect_material_counts"]) | set(mesh["mesh_effect_handle_counts"])
    # script-called sfx names (literal first arg of play-sound* calls)
    script_sfx = collections.Counter()
    for dp, _d, fs in os.walk(DC):
        for f in fs:
            if f.endswith(".dcpl"):
                for m in re.finditer(r"\bplay-sound[a-z-]*\((sfx-[\w\-]+)", open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()):
                    script_sfx[m.group(1)] += 1
    def route(n):
        b = n[4:] if n.startswith("sfx-") else n
        if n in script_sfx:
            return "script-call"
        for s in door_suf:
            if b.endswith("-" + s) and b[: -len(s) - 1] in mats:
                return "mesh-effect:door-material"
        for s in handle_suf:
            if b.endswith("-" + s) and b[: -len(s) - 1] in mats:
                return "mesh-effect:door-handle"
        for s in rope_suf:
            if b.endswith("-" + s):
                return "mesh-effect:rope-material"
        if "--" in b:
            return "anim-effect:joint-suffixed (IGC)"
        return "unknown (anim effect / native)"
    tree = collections.defaultdict(lambda: collections.Counter())
    packages = []
    for dp, _d, fs in os.walk(DC):
        for f in sorted(fs):
            if not f.endswith(".asm"):
                continue
            rel = os.path.relpath(os.path.join(dp, f), DC)[:-4]
            if not (rel.startswith("audio") or rel.startswith("aud-") or "/aud-" in rel or rel.startswith("vox")):
                continue
            c, cats, names = scan(os.path.join(dp, f))
            if not c:
                continue
            top = rel.split("/")[0] if "/" not in rel[len("audio-sfx/"):] or not rel.startswith("audio-sfx") else "audio-sfx/" + rel.split("/")[1]
            for k, v in c.items():
                tree[top][k] += v
            if rel.startswith("audio-sfx/common-objects/"):
                routes = collections.Counter(route(n) for n in names)
                packages.append({"module": rel, "counts": dict(c), "categories": dict(cats.most_common(4)),
                                 "routes": dict(routes), "examples": names[:4]})
    totals = collections.Counter()
    for v in tree.values():
        totals.update(v)
    res = {"source": "dconstruct asm of DC audio modules", "entry_type_totals": dict(totals),
           "by_group": {k: dict(v) for k, v in sorted(tree.items())},
           "script_literal_sfx_calls": len(script_sfx),
           "common_objects_packages": packages}
    json.dump(res, open(sys.argv[2], "w"), indent=1)
    print(dict(totals), len(packages), "common-object packages")
    agg = collections.Counter()
    for p in packages:
        agg.update(p["routes"])
    print(agg)


if __name__ == "__main__":
    main()
