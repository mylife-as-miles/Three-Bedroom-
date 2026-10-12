#!/usr/bin/env python3
"""animation_statelist — summarise anim actor-state-list data modules (anim-player/*.bin.asm)
into a compact JSON schema: states, anim nodes, subsystems, dynamic flags, transitions.

Usage: python3 -I tools/analysis/animation_statelist.py <file.bin.asm> [...]  > out.json
"""
import json, re, sys

re_open = re.compile(r"^(\s*)(?:\[(0x[0-9A-Fa-f]+|\d+)\]\s+)?(.*?)\s*\{\s*(?:\{size: (\d+)\}\s*\{)?\s*$")
re_leaf = re.compile(r"^(\s*)\[(0x[0-9A-Fa-f]+|\d+)\]\s+(\w[\w\- ]*?):\s*(.*)$")


def parse(lines):
    root = {"t": "root", "c": []}
    stack = [root]
    for ln in lines:
        s = ln.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        if stack[-1].get("t") == "script-lambda":
            m = re.search(r"function: ([^\s]+)", s)
            if m:
                stack[-1].setdefault("fns", []).append(m.group(1))
            if s.strip() == "}":
                stack.pop()
            continue
        if s.strip() == "}":
            if len(stack) > 1:
                stack.pop()
            continue
        m = re_leaf.match(s)
        if m and not s.rstrip().endswith("{"):
            stack[-1]["c"].append({"k": m.group(2), "t": m.group(3), "v": m.group(4).strip()})
            continue
        m = re_open.match(s)
        if m:
            head = m.group(3)
            name = None
            if " = " in head:
                name, head = head.split(" = ", 1)
            t = head.split(" [")[0].strip()
            node = {"k": m.group(2), "t": t, "c": []}
            if name:
                node["name"] = name.strip()
            if t.startswith("keys:"):
                continue
            stack[-1]["c"].append(node)
            stack.append(node)
            continue
    return root


def walk(n):
    yield n
    for c in n.get("c", []):
        yield from walk(c)


def first(n, t):
    for c in n.get("c", []):
        if c.get("t") == t:
            return c
    return None


def by_off(n, off):
    for c in n.get("c", []):
        if c.get("k") == off:
            return c
    return None


def sids(n):
    return [c["v"] for c in walk(n) if c.get("t") == "sid"]


def summarize_state(st):
    out = {}
    nm = by_off(st, "0x000")
    out["name"] = nm["v"].strip('"') if nm else None
    tag = by_off(st, "0x028")
    out["tag"] = tag["v"] if tag and tag.get("t") == "sid" else None
    prim = by_off(st, "0x020")
    out["primary_anim"] = prim["v"] if prim and prim.get("t") == "sid" else None
    tree = by_off(st, "0x018")
    nodes, anims, subs = [], [], []
    if tree and tree.get("c") is not None:
        for x in walk(tree):
            if x.get("t", "").startswith("anim-node"):
                nodes.append(x["t"])
                if x["t"] == "anim-node-animation":
                    a = by_off(x, "0x008")
                    if a and a.get("t") == "sid":
                        anims.append(a["v"])
            if x.get("t") == "sid" and re.match(r"[A-Z]\w+Action$", x["v"]):
                subs.append(x["v"])
    out["node_types"] = sorted(set(nodes))
    out["anims"] = sorted(set(anims))
    tg = by_off(st, "0x048")
    trans = []
    if tg:
        arr = first(tg, "array")
        for tr in (arr or {}).get("c", []):
            ev = by_off(tr, "0x000"); tgt = by_off(tr, "0x020"); bl = by_off(tr, "0x038")
            ev, tgt, bl = [x if x and "v" in x else None for x in (ev, tgt, bl)]
            conds = []
            for x in walk(tr):
                if x.get("t") == "anim-transition-condition":
                    vals = [c.get("v") for c in x["c"]]
                    conds.append({"type": "phase/cond", "raw": vals[:2]})
                if x.get("t") == "script-lambda":
                    conds.append({"type": "lambda", "calls": sorted(set(x.get("fns", [])))})
            trans.append({"event": ev["v"] if ev else None, "target": tgt["v"] if tgt else None,
                          "blend": bl["v"] if bl else None, "conds": conds})
    out["transitions"] = trans
    ht = by_off(st, "0x070")
    info = {}
    dyn = []
    if ht:
        for x in walk(ht):
            if x.get("t", "").endswith("-state-info") and x["t"] not in ("anim-state-player-info",):
                pass
            if x.get("t") == "subsystem-state-info":
                subs += [v for v in sids(x)]
            if x.get("t") == "dynamic-state-info-array":
                arr = first(x, "array")
                for d in (arr or {}).get("c", []):
                    vals = [(c.get("t"), c.get("v")) for c in d.get("c", []) if "v" in c]
                    dyn.append([v for _t, v in vals])
            if x.get("t") in ("door-state-info", "anim-state-player-info"):
                info[x["t"]] = [v for v in sids(x)]
            elif x.get("t", "").endswith("-state-info") and x.get("t") not in ("subsystem-state-info",):
                s_ = sids(x)
                if s_:
                    info[x["t"]] = s_
    out["subsystems"] = sorted(set(subs))
    out["dynamic"] = dyn
    out["info"] = info
    lam = by_off(st, "0x060")
    if lam and lam.get("t") == "script-lambda":
        out["speed_lambda_calls"] = sorted(set(lam.get("fns", [])))
    return out


def main():
    res = {}
    for p in sys.argv[1:]:
        root = parse(open(p, encoding="utf-8", errors="replace"))
        mods = []
        for top in root["c"]:
            if top.get("t") in ("actor-state-list",):
                hdr = [c.get("v") for c in top["c"] if "v" in c]
                arr = first(top, "array")
                states = [summarize_state(s) for s in (arr or {}).get("c", [])]
                mods.append({"name": top.get("name"), "type": top["t"], "header": hdr, "states": states})
            else:
                mods.append({"type": top.get("t"), "header": [c.get("v") for c in top.get("c", []) if "v" in c][:6]})
        res[p.split("dc1/")[-1]] = mods
    json.dump(res, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
