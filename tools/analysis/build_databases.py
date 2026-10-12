#!/usr/bin/env python3
"""Pass 3 — resolve the raw corpus scan into the committed databases.

Inputs (private): <db>/corpus.jsonl.gz, <db>/xref.jsonl.gz, <sid>/sid_full.tsv,
                  dconstruct sid_addresses.tsv (native function addresses)
Outputs (repo):   databases/state_scripts.json
                  databases/functions.json
                  databases/events.json
                  databases/call_graph.json          (interaction-related scripts)
                  databases/call_graph_full.jsonl.gz (every state script)
                  databases/sid_database.tsv.gz       (all referenced SIDs)
                  databases/sid_database.json         (interaction-relevant subset)
                  databases/file_manifest.json
                  databases/interaction_files.json    (classification)

Usage: build_databases.py <db_dir> <sid_dir> <sid_addresses.tsv> <out_dir> [<psarc_manifest.json>]
"""
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dclib import SidDB  # noqa: E402

GO_FUNCS = {"go", "go-if-not-in-state"}
SEND_FUNCS = {"send-event": "send", "broadcast-event": "broadcast", "net-send-event-all": "net-all",
              "net-send-event-to-host": "net-host", "broadcast-event-to-npcs": "broadcast-npcs",
              "send-event-box-result": "send-box"}

# keyword -> category, applied to file path, script names, state names and called functions
CATEGORIES = {
    "drawers_cabinets": r"drawer|cabinet|openable|scaveng|locker|fridge",
    "doors_gates": r"\bdoor|-door|gate\b|-gate|door-",
    "pickups_inventory": r"pickup|pick-up|inventory|loot|ammo|resource|craft|item-",
    "investigate_examine": r"investigat|examine|inspect|look-at",
    "notes_journal_collectibles": r"journal|note|artifact|collectib|treasure|letter|card|coin",
    "safes_keypads_locks": r"safe|keypad|lock|tumbler|combo|combination",
    "power_switches": r"generator|power|switch|lever|button|circuit|electric|fuse|breaker",
    "ladders_climb_traversal": r"ladder|climb|squeeze|vault|ledge|crawl|traversal|edge-",
    "ropes": r"rope|cable|winch",
    "pushables": r"push-object|pushable|push-|pull-object|cart|dumpster",
    "workbench_crafting": r"workbench|upgrade|crafting",
    "ui_hud": r"hud|gui|menu|prompt|widget|interact-def|icon",
    "camera": r"camera",
    "audio": r"aud-|audio|sfx|vox",
    "ai": r"^ai/|ai-|perception|hearing|encounter|search-|combat|infected|clicker|knowledge",
    "persistence_world_state": r"svar|checkpoint|save|persistent|fact-|task-",
}
INTERACTION_CATS = {"drawers_cabinets", "doors_gates", "pickups_inventory", "investigate_examine",
                    "notes_journal_collectibles", "safes_keypads_locks", "power_switches",
                    "ladders_climb_traversal", "ropes", "pushables", "workbench_crafting"}
INTERACTION_FUNCS = re.compile(r"interact|pickup|investigat|examine|scripted-move|ladder|rope|push-object|"
                               r"workbench|openable|safe|keypad|door")


def fmt(a, S):
    if a is None:
        return "?"
    t, x = a[0], a[1]
    if t == "s":
        v = int(x, 16)
        if v == 0:
            return "0"
        s = S.get(v)
        if s is not None:
            return s
        return str(v) if v < 1 << 20 else "#" + x
    if t in ("i", "f"):
        return repr(x) if t == "f" else str(x)
    if t == "str":
        return json.dumps(x)
    if t == "l":
        return "<lambda>"
    if t == "p":
        return "<data>"
    if t == "r":
        return f"({S.name(int(x, 16)) if x else '?'} ...)"
    return "?"


def classify(text):
    cats = []
    for c, rx in CATEGORIES.items():
        if re.search(rx, text):
            cats.append(c)
    return cats


def main():
    db, sid_dir, sid_addr, out = sys.argv[1:5]
    psarc_manifest = sys.argv[5] if len(sys.argv) > 5 else None
    os.makedirs(out, exist_ok=True)
    S = SidDB()
    S.load_tsv(os.path.join(sid_dir, "sid_full.tsv"))
    native = {}
    if os.path.exists(sid_addr):
        for line in open(sid_addr, encoding="utf-8", errors="replace"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3:
                native[p[1]] = p[2]
    N = lambda h: S.name(int(h, 16)) if h else None  # noqa: E731

    state_scripts = {}
    fn_calls = Counter()
    fn_files = defaultdict(set)
    fn_argc = defaultdict(Counter)
    fn_callers = defaultdict(set)
    fn_defined = defaultdict(list)
    ev_handled = defaultdict(list)
    ev_sent = defaultdict(list)
    ev_waited = defaultdict(list)
    manifest = []
    classes = {}
    cg_full = gzip.open(os.path.join(out, "call_graph_full.jsonl.gz"), "wt", encoding="utf-8")
    cg_inter = {}

    for line in gzip.open(os.path.join(db, "corpus.jsonl.gz"), "rt", encoding="utf-8"):
        r = json.loads(line)
        f = r["file"]
        ent_types = Counter(N(e["type"]) for e in r.get("entries", []))
        manifest.append({"file": f, "size": r["size"], "entries": sum(ent_types.values()),
                         "entry_types": dict(ent_types.most_common(8)),
                         "state_scripts": [N(s["id"]) for s in r.get("state_scripts", [])],
                         "lambdas": len(r.get("lambdas", []))})
        for e in r.get("entries", []):
            if N(e["type"]) in ("script-lambda", "function"):
                fn_defined[N(e["name"])].append(f)
        lam_by_off = {l["off"]: l for l in r.get("lambdas", [])}
        # context map for lambdas belonging to state scripts
        ctx = {}
        for ss in r.get("state_scripts", []):
            for st in ss["states"]:
                for b in st["blocks"]:
                    for t in b["tracks"]:
                        for k, lo in enumerate(t["lambdas"]):
                            ctx[lo] = (N(ss["id"]), N(st["id"]), b["type"], N(b["event"]) if b["event"] else None,
                                       N(t["id"]), k)
        # name map for top-level function lambdas
        fname = {}
        for e in r.get("entries", []):
            if N(e["type"]) in ("script-lambda", "function"):
                fname[e["off"]] = N(e["name"])
        # propagate context to nested lambdas
        changed = True
        while changed:
            changed = False
            for lo, lam in lam_by_off.items():
                parent = ctx.get(lo) or (("fn", fname[lo]) if lo in fname else None)
                if parent is None:
                    continue
                for _i, _fn, args in lam["calls"]:
                    for a in args:
                        if a and a[0] == "l" and a[1] not in ctx and a[1] not in fname:
                            ctx[a[1]] = parent
                            changed = True
        texts = [f]
        for lam in r.get("lambdas", []):
            c = ctx.get(lam["off"]) or (("fn", fname.get(lam["off"])) if lam["off"] in fname else None)
            where = None
            if c and c[0] != "fn":
                where = f"{c[0]}:{c[1]}"
            elif c:
                where = f"fn:{c[1]}"
            for _i, fn, args in lam["calls"]:
                if not fn:
                    continue
                nm = N(fn)
                fn_calls[nm] += 1
                fn_files[nm].add(f)
                fn_argc[nm][len(args)] += 1
                if where and len(fn_callers[nm]) < 25:
                    fn_callers[nm].add(f"{f}::{where}")
                if nm in SEND_FUNCS and args and args[0] and args[0][0] == "s":
                    ev = fmt(args[0], S)
                    ev_sent[ev].append({"file": f, "where": where, "via": SEND_FUNCS[nm],
                                        "target": fmt(args[1], S) if len(args) > 1 else None})
                if nm in ("wait-for-event", "wait-for-event-or-skip-to") and args and args[0] and args[0][0] == "s":
                    ev_waited[fmt(args[0], S)].append({"file": f, "where": where})
        for ss in r.get("state_scripts", []):
            ssn = N(ss["id"])
            texts.append(ssn)
            key = f"{f}::{ssn}"
            states = {}
            graph = {}
            for st in ss["states"]:
                stn = N(st["id"])
                texts.append(stn)
                trans = []
                sent = []
                calls_u = []
                blocks = []
                gblocks = []
                for b in st["blocks"]:
                    evn = N(b["event"]) if b["event"] else None
                    blocks.append({"type": b["type"], "event": evn} if evn else {"type": b["type"]})
                    if evn:
                        ev_handled[evn].append({"file": f, "script": ssn, "state": stn})
                    gtracks = []
                    for t in b["tracks"]:
                        segs = []
                        stack = list(t["lambdas"])
                        seen = set()
                        order = []
                        while stack:
                            lo = stack.pop(0)
                            if lo in seen or lo not in lam_by_off:
                                continue
                            seen.add(lo)
                            order.append(lo)
                        for lo in order:
                            seg = []
                            todo = [lo]
                            vis = set()
                            while todo:
                                x = todo.pop(0)
                                if x in vis or x not in lam_by_off:
                                    continue
                                vis.add(x)
                                for _i, fn, args in lam_by_off[x]["calls"]:
                                    if not fn:
                                        continue
                                    nm = N(fn)
                                    seg.append(f"{nm}({', '.join(fmt(a, S) for a in args)})")
                                    if nm not in calls_u:
                                        calls_u.append(nm)
                                    texts.append(nm)
                                    if nm in GO_FUNCS and args and args[0] and args[0][0] == "s":
                                        trans.append(fmt(args[0], S))
                                    if nm in SEND_FUNCS and args and args[0] and args[0][0] == "s":
                                        sent.append(f"{SEND_FUNCS[nm]}:{fmt(args[0], S)}")
                                    for a in args:
                                        if a and a[0] == "l":
                                            todo.append(a[1])
                            segs.append(seg)
                        gtracks.append({"track": N(t["id"]), "segments": segs})
                    gblocks.append({"on": b["type"] + (f" {evn}" if evn else ""), "tracks": gtracks})
                states[stn] = {"blocks": blocks, "transitions": list(dict.fromkeys(trans)),
                               "events_sent": list(dict.fromkeys(sent)), "calls": calls_u}
                graph[stn] = {"blocks": gblocks, "next": list(dict.fromkeys(trans))}
            state_scripts[key] = {
                "file": f, "name": ssn, "debug_file": ss.get("debug_file"),
                "initial_state": N(ss["initial_state"]),
                "options": ss.get("options_symbols") and [S.name(int(x, 16)) if re.fullmatch(r"[0-9a-f]{16}", x) else x
                                                          for x in ss["options_symbols"]],
                "declarations": [{"name": N(d["id"]), "type": N(d["type"]),
                                  "default": d["value"] if not isinstance(d["value"], dict) else None}
                                 for d in ss["declarations"]],
                "states": states,
            }
            cg_full.write(json.dumps({"key": key, "states": graph}, separators=(",", ":")) + "\n")
            cats = classify(" ".join([f, ssn] + list(states)))
            if any(c in INTERACTION_CATS for c in cats):
                cg_inter[key] = graph
        cats = classify(" ".join(texts[:4000]))
        classes[f] = cats
    cg_full.close()

    # options symbols were stored resolved already when sids passed; normalise
    funcs = {}
    for nm, c in fn_calls.most_common():
        funcs[nm] = {
            "calls": c, "files": len(fn_files[nm]),
            "argc": {str(k): v for k, v in sorted(fn_argc[nm].items())},
            "dc_defined_in": sorted(set(fn_defined.get(nm, [])))[:10],
            "native_address": native.get(nm),
            "kind": "dc-script" if nm in fn_defined else ("native-confirmed" if nm in native else "native-or-builtin"),
            "sample_callers": sorted(fn_callers[nm])[:12],
            "categories": classify(nm),
        }
    # DC-defined functions never called still listed
    for nm, fl in fn_defined.items():
        if nm not in funcs:
            funcs[nm] = {"calls": 0, "files": 0, "argc": {}, "dc_defined_in": sorted(set(fl))[:10],
                         "native_address": native.get(nm), "kind": "dc-script", "sample_callers": [],
                         "categories": classify(nm)}
    events = {}
    for ev in set(ev_handled) | set(ev_sent) | set(ev_waited):
        events[ev] = {"handled_by": ev_handled.get(ev, [])[:60], "n_handlers": len(ev_handled.get(ev, [])),
                      "sent_by": ev_sent.get(ev, [])[:60], "n_senders": len(ev_sent.get(ev, [])),
                      "waited_by": ev_waited.get(ev, [])[:30]}
    events = dict(sorted(events.items(), key=lambda kv: -(kv[1]["n_handlers"] + kv[1]["n_senders"])))

    def dump(name, obj):
        with open(os.path.join(out, name), "w", encoding="utf-8") as fo:
            json.dump(obj, fo, indent=None, separators=(",", ":"), ensure_ascii=False)
        print(name, os.path.getsize(os.path.join(out, name)) // 1024, "KB")

    dump("state_scripts.json", state_scripts)
    dump("functions.json", funcs)
    dump("events.json", events)
    dump("call_graph.json", cg_inter)
    if psarc_manifest and os.path.exists(psarc_manifest):
        sizes = {m["path"]: m["size"] for m in json.load(open(psarc_manifest))}
        for m in manifest:
            m["in_main_psarc"] = ("dc1/" + m["file"]) in sizes
    dump("file_manifest.json", manifest)
    dump("interaction_files.json", {f: c for f, c in classes.items() if any(x in INTERACTION_CATS for x in c)})

    # SID database
    ref = json.load(open(os.path.join(sid_dir, "sid_referenced.json")))
    with gzip.open(os.path.join(out, "sid_database.tsv.gz"), "wt", encoding="utf-8") as fo:
        fo.write("sid\tstring\tsource\tcount\troles\tfiles_sample\n")
        for h, v in ref.items():
            s = (v["string"] or "").replace("\t", " ").replace("\n", " ")
            fo.write(f"{h}\t{s}\t{v['source']}\t{v['count']}\t{','.join(v['roles'])}\t{';'.join(v['files'][:3])}\n")
    sub = {}
    for h, v in ref.items():
        s = v["string"] or ""
        if INTERACTION_FUNCS.search(s) or any(r in v["roles"] for r in ("state", "event-handler", "state-script",
                                                                          "call-target", "declaration", "track")):
            sub[h] = {"s": v["string"], "n": v["count"], "roles": v["roles"], "files": v["files"][:4]}
    dump("sid_database.json", sub)
    print("state scripts", len(state_scripts), "functions", len(funcs), "events", len(events),
          "interaction call graphs", len(cg_inter))


if __name__ == "__main__":
    main()
