#!/usr/bin/env python3
"""q — cross-reference query tool over the generated databases.

  q.py fn <name>            function: call count, kind (dc/native), definition, callers
  q.py callers <name>       every call site (file::script:state or fn:<name>) with args
  q.py event <name>         who handles / sends / waits on an event
  q.py uses <string>        every file whose DATA or CODE references the SID of <string>
  q.py ss <name|file>       state machine summary (states, events handled, transitions, sends)
  q.py sid <hex|string>     resolve either direction
  q.py find <regex>         search names in functions/events/state scripts
  q.py dcpl <file>          print path of the dconstruct pseudo-code for a corpus file

Environment: TLOU2_PRIVATE (default <repo>/.private)
"""
import gzip
import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PRIV = os.environ.get("TLOU2_PRIVATE", os.path.join(REPO, ".private"))
DBS = os.path.join(REPO, "databases")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dclib import fnv1a64, sidhex  # noqa: E402

_cache = {}


def load(name):
    if name not in _cache:
        _cache[name] = json.load(open(os.path.join(DBS, name), encoding="utf-8"))
    return _cache[name]


def sid_lookup():
    if "sids" not in _cache:
        m = {}
        for line in open(os.path.join(PRIV, "sid", "sid_full.tsv"), encoding="utf-8"):
            p = line.split("\t")
            m[p[0]] = p[1]
        _cache["sids"] = m
    return _cache["sids"]


def cmd_fn(name):
    f = load("functions.json").get(name)
    print(json.dumps(f, indent=1) if f else "not called/defined anywhere")


def cmd_callers(name):
    sids = sid_lookup()
    target = sidhex(fnv1a64(name))
    # map lambda offsets to context, per file
    for line in gzip.open(os.path.join(PRIV, "db", "corpus.jsonl.gz"), "rt", encoding="utf-8"):
        r = json.loads(line)
        ctx = {}
        for ss in r.get("state_scripts", []):
            for st in ss["states"]:
                for b in st["blocks"]:
                    ev = sids.get(b["event"], b["event"]) if b["event"] else ""
                    for t in b["tracks"]:
                        for lo in t["lambdas"]:
                            ctx[lo] = f"{sids.get(ss['id'], ss['id'])}:{sids.get(st['id'], st['id'])}:{b['type']} {ev}".strip()
        fnames = {e["off"]: sids.get(e["name"], e["name"]) for e in r.get("entries", [])}
        for lam in r.get("lambdas", []):
            for _i, fn, args in lam["calls"]:
                if fn == target:
                    where = ctx.get(lam["off"]) or ("fn:" + fnames[lam["off"]] if lam["off"] in fnames else f"lambda@{lam['off']:#x}")
                    a = []
                    for x in args:
                        if x is None:
                            a.append("?")
                        elif x[0] == "s":
                            a.append(sids.get(x[1], x[1]) if int(x[1], 16) > 0xFFFFF else str(int(x[1], 16)))
                        elif x[0] in ("l", "p"):
                            a.append("<" + x[0] + ">")
                        elif x[0] == "r":
                            a.append(f"({sids.get(x[1], '?')} ...)")
                        else:
                            a.append(json.dumps(x[1]) if x[0] == "str" else str(x[1]))
                    print(f"{r['file']}  {where}  {name}({', '.join(a)})")


def cmd_event(name):
    e = load("events.json").get(name)
    print(json.dumps(e, indent=1) if e else "no handlers/senders found in script (may be native-only)")


def cmd_uses(s):
    h = s if re.fullmatch(r"[0-9a-f]{16}", s) else sidhex(fnv1a64(s))
    inv = _cache.get("inv")
    if inv is None:
        inv = json.load(gzip.open(os.path.join(PRIV, "db", "xref_inverted.json.gz"), "rt"))
        _cache["inv"] = inv
    data_files = inv.get(h, [])
    print(f"sid {h}  data-references in {len(data_files)} files")
    for f in data_files[:400]:
        print("  data:", f)
    ref = json.load(open(os.path.join(DBS, "sid_database.json"), encoding="utf-8")).get(h)
    if ref:
        print("code roles:", ref["roles"], "count", ref["n"], "files", ref["files"])


def cmd_ss(name):
    ss = load("state_scripts.json")
    keys = [k for k in ss if k.endswith("::" + name) or k.split("::")[0] == name or name in k]
    for k in keys[:20]:
        d = ss[k]
        print(f"== {k}  initial={d['initial_state']}  src={d['debug_file']}")
        print("   decls:", ", ".join(f"{x['type']} {x['name']}" for x in d["declarations"])[:2000])
        for st, v in d["states"].items():
            evs = [b["event"] for b in v["blocks"] if b.get("event")]
            print(f"   {st:32s} -> {', '.join(v['transitions']) or '-'}")
            if evs:
                print(f"   {'':32s}    on-events: {', '.join(evs)}")
            if v["events_sent"]:
                print(f"   {'':32s}    sends: {', '.join(v['events_sent'])}")


def cmd_sid(x):
    if re.fullmatch(r"(0x)?[0-9a-fA-F]{16}", x):
        print(sid_lookup().get(x.lower().replace("0x", ""), "unresolved"))
    else:
        print(sidhex(fnv1a64(x)))


def cmd_find(rx):
    r = re.compile(rx)
    for name, db in (("function", "functions.json"), ("event", "events.json")):
        for k in load(db):
            if r.search(k):
                print(name, k)
    for k in load("state_scripts.json"):
        if r.search(k):
            print("state-script", k)


def cmd_dcpl(f):
    f = f.replace("dc1/", "")
    print(os.path.join(PRIV, "dconstruct_out", "dc1", f + ".dcpl"))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    globals()["cmd_" + sys.argv[1]](" ".join(sys.argv[2:]))
