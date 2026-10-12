#!/usr/bin/env python3
"""Build the corpus-wide EVENT GRAPH: sender (script/function) --event--> handler (script:state).

Outputs:
  databases/event_graph.json   {"edges":[{"event","from","from_where","via","to","to_state"}], "stats":{...}}
  <out_dir>/event_graph_<filter>.dot  Graphviz for events matching a regex filter (optional)

Usage: event_graph.py [--filter REGEX] [--dot OUT_DIR]

Senders come from script calls to send-event / broadcast-event / net-send-*;
handlers from `on (event X)` blocks. Events that are handled but never sent by script
are listed in stats.native_only_candidates (likely sent by native code).
"""
import argparse
import json
import os
import re
from collections import Counter, defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default=None)
    ap.add_argument("--dot", default=None)
    a = ap.parse_args()
    ss = json.load(open(os.path.join(REPO, "databases", "state_scripts.json"), encoding="utf-8"))
    handlers = defaultdict(list)
    senders = defaultdict(list)
    for key, d in ss.items():
        for st, v in d["states"].items():
            for b in v["blocks"]:
                if b.get("event"):
                    handlers[b["event"]].append((d["file"], d["name"], st))
            for s in v["events_sent"]:
                via, _, ev = s.partition(":")
                senders[ev].append((d["file"], d["name"], st, via))
    # also senders from free functions (events.json covers them)
    evdb = json.load(open(os.path.join(REPO, "databases", "events.json"), encoding="utf-8"))
    for ev, v in evdb.items():
        for s in v["sent_by"]:
            if s["where"] and s["where"].startswith("fn:"):
                senders[ev].append((s["file"], s["where"], "-", s["via"]))
    edges = []
    for ev in set(handlers) & set(senders):
        if a.filter and not re.search(a.filter, ev):
            continue
        for sf, sn, sst, via in senders[ev][:40]:
            for hf, hn, hst in handlers[ev][:80]:
                edges.append({"event": ev, "from": sn, "from_file": sf, "from_where": sst, "via": via,
                              "to": hn, "to_file": hf, "to_state": hst})
    # timers deliver an event named after the timer: collect timer names so they are not
    # mistaken for engine-originated events
    import gzip
    timers = set()
    rx = re.compile(r"\b(?:start-timer|start-timer-if-not-running|restart-timer)\(([^,()]+),")
    for line in gzip.open(os.path.join(REPO, "databases", "call_graph_full.jsonl.gz"), "rt", encoding="utf-8"):
        for m in rx.finditer(line):
            timers.add(m.group(1).strip())
    native_only = sorted(((ev, len(h)) for ev, h in handlers.items() if ev not in senders and ev not in timers),
                         key=lambda x: -x[1])
    timer_events = sorted(ev for ev in handlers if ev in timers)
    unheard = sorted(((ev, len(s)) for ev, s in senders.items() if ev not in handlers), key=lambda x: -x[1])
    stats = {"events_with_script_handlers": len(handlers), "events_with_script_senders": len(senders),
             "linked_events": len(set(handlers) & set(senders)), "edges_written": len(edges),
             "native_only_candidates_top": native_only[:150],
             "sent_but_no_script_handler_top": unheard[:150]}
    vocab = {"_doc": "engine_to_script: events handled by DC state scripts but never sent by any DC script "
                     "(=> originate in native code). script_to_native: events sent by DC but with no DC handler "
                     "(=> consumed by native object/actor handlers). Counts = number of handler/sender sites.",
             "engine_to_script": dict(native_only), "script_to_native": dict(unheard),
             "timer_events": timer_events}
    json.dump(vocab, open(os.path.join(REPO, "databases", "native_event_vocabulary.json"), "w"), indent=0)
    name = "event_graph.json" if not a.filter else "event_graph_filtered.json"
    json.dump({"stats": stats, "edges": edges}, open(os.path.join(REPO, "databases", name), "w"),
              separators=(",", ":"))
    print(json.dumps({k: v for k, v in stats.items() if not k.endswith("top")}, indent=1))
    if a.dot:
        os.makedirs(a.dot, exist_ok=True)
        tag = re.sub(r"[^a-z0-9]+", "_", (a.filter or "all").lower())[:40]
        p = os.path.join(a.dot, f"event_graph_{tag}.dot")
        cnt = Counter((e["from"], e["event"], e["to"]) for e in edges)
        with open(p, "w") as fo:
            fo.write("digraph events {\n  rankdir=LR; node [shape=box,fontsize=9]; edge [fontsize=8];\n")
            for (f, ev, t), _n in cnt.items():
                fo.write(f'  "{f}" -> "{t}" [label="{ev}"];\n')
            fo.write("}\n")
        print("wrote", p)


if __name__ == "__main__":
    main()
