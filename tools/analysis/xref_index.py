#!/usr/bin/env python3
"""Pass 2 — data-level SID cross-reference.

For every file, every 8-byte-aligned, non-pointer word inside the text
region whose value is a known SID is counted.  This captures SIDs living in
*data* structs (interaction definitions, level placements, settings tables,
anim/audio references) — not only in bytecode symbol tables.

Output: <db>/xref.jsonl.gz  {"file":..., "sids":{hex:count}}
        <db>/xref_inverted.json.gz  {hex: [files...]}
Usage: xref_index.py <dc1_root> <db_dir> <sid_full.tsv>
"""
import gzip
import json
import os
import sys
from collections import defaultdict
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dclib import DCFile  # noqa: E402

KNOWN = None


def init(path):
    global KNOWN
    KNOWN = np.load(path)


def work(args):
    path, root = args
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    try:
        dc = DCFile(path)
    except Exception:  # noqa: BLE001
        return rel, {}
    n = dc.text_size // 8
    words = np.frombuffer(dc.b, dtype="<u8", count=n)
    bits = np.unpackbits(np.frombuffer(dc.reloc, dtype=np.uint8), bitorder="little")[:n]
    if len(bits) < n:
        bits = np.concatenate([bits, np.zeros(n - len(bits), dtype=np.uint8)])
    cand = words[(bits == 0) & (words > 0xFFFFF)]
    # KNOWN is sorted+unique: binary search is O(n log m) without re-sorting
    pos = np.searchsorted(KNOWN, cand)
    pos[pos >= len(KNOWN)] = 0
    hit = cand[KNOWN[pos] == cand]
    vals, cnts = np.unique(hit, return_counts=True)
    return rel, {f"{int(v):016x}": int(c) for v, c in zip(vals, cnts)}


def main():
    root, db, tsv = sys.argv[1:4]
    npy = os.path.join(db, "known_sids.npy")
    if not os.path.exists(npy):
        arr = []
        for line in open(tsv, encoding="utf-8"):
            h = line[:16]
            try:
                arr.append(int(h, 16))
            except ValueError:
                pass
        np.save(npy, np.unique(np.array(arr, dtype=np.uint64)))
    files = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.endswith(".bin"):
                files.append((os.path.join(dp, f), root))
    files.sort()
    inv = defaultdict(list)
    with gzip.open(os.path.join(db, "xref.jsonl.gz"), "wt") as fo, Pool(os.cpu_count(), init, (npy,)) as p:
        for rel, sids in p.imap(work, files, chunksize=16):
            fo.write(json.dumps({"file": rel, "sids": sids}, separators=(",", ":")) + "\n")
            for h in sids:
                inv[h].append(rel)
    with gzip.open(os.path.join(db, "xref_inverted.json.gz"), "wt") as fo:
        json.dump(inv, fo, separators=(",", ":"))
    print(f"{len(files)} files, {len(inv)} distinct data SIDs")


if __name__ == "__main__":
    main()
