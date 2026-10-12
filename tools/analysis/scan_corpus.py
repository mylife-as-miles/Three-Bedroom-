#!/usr/bin/env python3
"""Pass 1 — scan every DC .bin in the corpus and dump raw structured facts.

Output (all under the private workspace, never committed):
  <out>/corpus.jsonl.gz   one JSON record per file (raw SIDs as hex)
  <out>/strings.tsv.gz    file \t string   (every string-table string)

SIDs are kept unresolved here so the dictionary can be improved and
re-applied later without rescanning.

Usage: scan_corpus.py <dc1_root> <out_dir> [-j N]
"""
import argparse
import gzip
import json
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dclib import DCFile, Tracer, sidhex  # noqa: E402


def enc(v):
    if v is None:
        return None
    t, x = v
    if t == "sid":
        return ["s", sidhex(x)]
    if t == "int":
        return ["i", x]
    if t == "float":
        return ["f", x]
    if t == "str":
        return ["str", x[:300]]
    if t == "lambda":
        return ["l", x]
    if t == "ptr":
        return ["p", x]
    if t == "ret":
        return ["r", sidhex(x) if x else None]
    return None


def scan(path_root):
    path, root = path_root
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    rec = {"file": rel, "size": os.path.getsize(path)}
    try:
        dc = DCFile(path)
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"open: {e}"
        return rec, []
    strings = dc.strings()
    rec["entries"] = [{"name": sidhex(n), "type": sidhex(t), "off": v} for n, t, v, _ in dc.entries()]
    rec["state_scripts"] = []
    for n, t, v, _ in dc.entries():
        # state-script type sid
        if t == 0xCE1173292ADCBD6E:
            try:
                rec["state_scripts"].append(dc.parse_state_script(v))
            except Exception as e:  # noqa: BLE001
                rec.setdefault("errors", []).append(f"ss {sidhex(n)}: {e}")
    tr = Tracer(dc)
    lams = []
    sid_refs = {}
    try:
        found = dc.find_lambdas()
    except Exception as e:  # noqa: BLE001
        found = []
        rec.setdefault("errors", []).append(f"lambdas: {e}")
    for lam in found:
        try:
            r = tr.run(lam)
        except Exception as e:  # noqa: BLE001
            rec.setdefault("errors", []).append(f"trace {lam.offset:#x}: {e}")
            continue
        calls = [[c["idx"], sidhex(c["fn"]) if c["fn"] else None, [enc(a) for a in c["args"]]]
                 for c in r["calls"]]
        for kind, v in r["refs"]:
            if v > 0xFFFFF:
                sid_refs[sidhex(v)] = sid_refs.get(sidhex(v), 0) + 1
        lams.append({"off": lam.offset, "name": sidhex(lam.func_name) if lam.func_name else None,
                     "scope": sidhex(lam.scope) if lam.scope else None, "n": lam.n_instr, "calls": calls})
    rec["lambdas"] = lams
    rec["sid_refs"] = sid_refs
    return rec, strings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("out")
    ap.add_argument("-j", type=int, default=os.cpu_count())
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    files = []
    for dp, _dn, fn in os.walk(a.root):
        for f in fn:
            if f.endswith(".bin"):
                files.append((os.path.join(dp, f), a.root))
    files.sort()
    t0 = time.time()
    n_err = 0
    with gzip.open(os.path.join(a.out, "corpus.jsonl.gz"), "wt", encoding="utf-8") as fo, \
            gzip.open(os.path.join(a.out, "strings.tsv.gz"), "wt", encoding="utf-8") as fs, \
            Pool(a.j) as pool:
        for i, (rec, strings) in enumerate(pool.imap(scan, files, chunksize=8)):
            if "error" in rec or rec.get("errors"):
                n_err += 1
            fo.write(json.dumps(rec, separators=(",", ":")) + "\n")
            for s in strings:
                fs.write(rec["file"] + "\t" + s.replace("\t", " ").replace("\n", " ") + "\n")
            if i % 1000 == 0:
                print(f"{i}/{len(files)} {time.time() - t0:.0f}s", flush=True)
    print(f"done {len(files)} files, {n_err} with errors, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
