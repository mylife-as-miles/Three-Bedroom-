#!/usr/bin/env python3
"""traversal_asl.py — summarise dconstruct .asm data trees (actor-state-list anim graphs, etc.).

Written for the ladders/ropes/pushables RE pass. Parses the indented dconstruct .asm
listing into a generic tree and prints, per actor-state-list state:
  name, node chain (node types / anim SIDs / subsystem SIDs), transitions (trigger -> target, blend),
  subsystem-state-info, dynamic-state-info keys, functions referenced by embedded lambdas.

Usage:  python3 -I tools/analysis/traversal_asl.py <file.asm> [--json out.json] [--entries]
"""
import json
import re
import sys

LINE = re.compile(r"^(\s*)(?:\[(0x[0-9A-Fa-f]+|\d+)\]\s+)?(.*?)\s*$")


class Node:
    __slots__ = ("key", "text", "children", "parent")

    def __init__(self, key, text, parent=None):
        self.key, self.text, self.children, self.parent = key, text, [], parent

    @property
    def type(self):
        t = self.text
        m = re.match(r"([A-Za-z0-9_\-?!*<>]+(?: [a-z\-]+)?)\s*(?::|\[|$)", t)
        return m.group(1) if m else t

    def val(self):
        if ": " in self.text:
            return self.text.split(": ", 1)[1].strip()
        return None

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


def parse(path):
    root = Node(None, "<root>")
    cur = root
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            if raw.startswith("#"):
                continue
            s = raw.rstrip("\n")
            st = s.strip()
            if not st:
                continue
            if st == "}":
                if cur.parent is not None:
                    cur = cur.parent
                continue
            m = LINE.match(s)
            key, text = m.group(2), m.group(3)
            if text.endswith("{") and not text.startswith("0"):
                n = Node(key, text[:-1].strip(), cur)
                cur.children.append(n)
                cur = n
            else:
                cur.children.append(Node(key, text, cur))
    return root


def sid_of(n, key="0x000"):
    for c in n.children:
        if c.key == key and c.text.startswith("sid: "):
            return c.text[5:]
    return None


def lambda_funcs(n):
    out = []
    for d in n.walk():
        m = re.search(r"function: (\S+)", d.text)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def summarise_transition(t):
    """t = anonymous struct inside anim-transition-group array."""
    trig = sid_of(t, "0x000")
    target = sid_of(t, "0x020")
    blend = None
    for c in t.children:
        if c.key == "0x038" and c.text.startswith("float"):
            blend = c.val()
    conds = []
    for d in t.walk():
        if d is t:
            continue
        if d.text.startswith("anim-transition-condition"):
            ty = d.text.split(" ")[0]
            if ty == "anim-transition-condition-lambda":
                conds.append("lambda(" + ",".join(lambda_funcs(d)) + ")")
            else:
                vals = [c.val() for c in d.children if c.val() is not None]
                conds.append(ty + "(" + ",".join(vals[:3]) + ")")
    return {"trigger": trig, "target": target, "blend": blend, "conds": conds}


def summarise_state(st):
    name = None
    for c in st.children:
        if c.key == "0x000" and c.text.startswith("string:"):
            name = c.val().strip('"')
    nodes, anims, trans, subsys, dyn, funcs, misc_sids = [], [], [], [], [], [], []
    for d in st.walk():
        t = d.text
        if t.startswith("anim-node-") or t.startswith("anim-node "):
            nt = t.split(" ")[0]
            s = sid_of(d, "0x008") if nt == "anim-node-animation" else None
            extra = sid_of(d, "0x010") if nt == "anim-node-subsystem-ik" else None
            nodes.append(nt + (f"({s})" if s else "") + (f"[{extra}]" if extra else ""))
            if s and s not in anims:
                anims.append(s)
        elif t.startswith("anim-transition-group"):
            for arr in d.children:
                if arr.text.startswith("array"):
                    for tr in arr.children:
                        trans.append(summarise_transition(tr))
        elif t.startswith("subsystem-state-info"):
            subsys.append([c.val() for c in d.children if c.text.startswith("sid:")])
        elif t.startswith("dynamic-state-info-array"):
            for arr in d.children:
                if arr.text.startswith("array"):
                    for e in arr.children:
                        k = sid_of(e, "0x000")
                        v = None
                        for c in e.children:
                            if c.key == "0x010":
                                vv = [x.val() for x in c.children if x.val() is not None]
                                v = c.text.split(" ")[0] + ":" + ",".join(vv[:2])
                        dyn.append(f"{k}={v}")
        elif t.startswith("script-lambda"):
            for f in lambda_funcs(d):
                if f not in funcs:
                    funcs.append(f)
        elif t.endswith("-state-info") or "-state-info " in t:
            pass
    # specialised state-info structs (e.g. character-ladder-state-info)
    BUNDLE = {"breath-state-info", "fire-state-info", "player-move-state-info", "face-state-info",
              "pickup-state-info", "player-swim-state-info", "player-edge-state-info",
              "player-explosion-state-info", "player-cover-state-info", "player-t1-strafe-state-info",
              "player-strafe-state-info", "player-bump-state-info", "player-swing-bar-state-info",
              "character-drive-state-info", "player-rope-state-info", "player-backpack-state-info",
              "weapon-state-info", "all-weapons-state-info"}
    nb = 0
    for d in st.walk():
        ty = d.text.split(" ")[0]
        if ty.endswith("-state-info") and ty != "subsystem-state-info":
            if ty in BUNDLE:
                nb += 1
            elif [ty] not in subsys:
                subsys.append([ty])
    if nb:
        subsys.append([f"<generic player state-info bundle x{nb}>"])
    subsys = [x for x in subsys if x]
    seen = set()
    trans_u = []
    for t in trans:
        k = (t["trigger"], t["target"])
        if k not in seen:
            seen.add(k)
            trans_u.append(t)
    return {"name": name, "nodes": nodes, "anims": anims, "transitions": trans_u,
            "subsystem": subsys, "dynamic": dyn, "lambda_funcs": funcs}


def entries(root):
    out = []
    for c in root.children:
        if " = " in c.text:
            nm, rest = c.text.split(" = ", 1)
            out.append((nm.strip(), rest.split(" ")[0], c))
    return out


def summarise_file(path):
    root = parse(path)
    res = []
    for nm, ty, node in entries(root):
        e = {"entry": nm, "type": ty}
        if ty == "actor-state-list":
            states = []
            for arr in node.children:
                if arr.text.startswith("array"):
                    for st in arr.children:
                        states.append(summarise_state(st))
            e["states"] = states
        res.append(e)
    return res


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    path = a[0]
    res = summarise_file(path)
    if "--json" in a:
        with open(a[a.index("--json") + 1], "w") as f:
            json.dump(res, f, indent=1)
    if "--entries" in a:
        for e in res:
            print(e["entry"], e["type"], len(e.get("states", [])))
        return
    for e in res:
        print(f"== {e['entry']} ({e['type']})")
        for s in e.get("states", []):
            print(f"  [{s['name']}]")
            if s["nodes"]:
                print("     nodes:", " > ".join(s["nodes"][:8]) + (" ..." if len(s["nodes"]) > 8 else ""))
            if s["anims"]:
                print("     anims:", ", ".join(s["anims"][:12]) + (f" (+{len(s['anims'])-12})" if len(s["anims"]) > 12 else ""))
            for t in s["transitions"]:
                print(f"     -> {t['target']}  on {t['trigger']} blend={t['blend']} {' '.join(t['conds'])}")
            for sub in s["subsystem"]:
                print("     subsystem:", sub)
            if s["dynamic"]:
                print("     dyn:", "; ".join(s["dynamic"]))
            if s["lambda_funcs"]:
                print("     fns:", ", ".join(s["lambda_funcs"]))


if __name__ == "__main__":
    main()
