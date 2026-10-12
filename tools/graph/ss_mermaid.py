#!/usr/bin/env python3
"""Render state scripts from databases/state_scripts.json as Mermaid stateDiagram-v2.

  ss_mermaid.py <name-or-substring> [...]        print diagrams to stdout
  ss_mermaid.py --all-interaction <out_dir>      one .md per interaction-classified script

Edges come from recovered `go(...)` targets (CONFIRMED transitions); conditions are not
encoded — read the per-state call graph for those. Event-handler blocks are noted.
"""
import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def ident(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s) or "_"


def render(key, d):
    lines = [f"%% {key}  (initial: {d['initial_state']})", "stateDiagram-v2",
             f"    [*] --> {ident(d['initial_state'])}"]
    for st, v in d["states"].items():
        evs = [b["event"] for b in v["blocks"] if b.get("event")]
        lines.append(f"    state \"{st}\" as {ident(st)}")
        if evs:
            lines.append(f"    note right of {ident(st)}: on {', '.join(evs[:6])}{' …' if len(evs) > 6 else ''}")
        for t in v["transitions"]:
            if t in d["states"]:
                lines.append(f"    {ident(st)} --> {ident(t)}")
            else:
                lines.append(f"    {ident(st)} --> {ident(t)}: (external/unresolved)")
        if not v["transitions"] and st in ("complete", "done"):
            lines.append(f"    {ident(st)} --> [*]")
    return "\n".join(lines)


def main():
    ss = json.load(open(os.path.join(REPO, "databases", "state_scripts.json"), encoding="utf-8"))
    if sys.argv[1] == "--all-interaction":
        out = sys.argv[2]
        os.makedirs(out, exist_ok=True)
        inter = json.load(open(os.path.join(REPO, "databases", "call_graph.json"), encoding="utf-8"))
        for key in inter:
            d = ss[key]
            fn = ident(key.replace(".bin::", "__"))[:150] + ".md"
            with open(os.path.join(out, fn), "w") as fo:
                fo.write(f"# {d['name']}\n\nfile: `{d['file']}` · src: `{d['debug_file']}`\n\n```mermaid\n{render(key, d)}\n```\n")
        print(len(inter), "diagrams")
        return
    for q in sys.argv[1:]:
        for key, d in ss.items():
            if key.endswith("::" + q) or (q in key and len(sys.argv) > 1 and q.startswith("ss-") is False):
                print("```mermaid\n" + render(key, d) + "\n```\n")


if __name__ == "__main__":
    main()
