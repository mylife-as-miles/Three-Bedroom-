#!/usr/bin/env python3
"""Build the global reverse StringID dictionary.

Sources (in priority order):
  1. dconstruct sidbase_new_fixed.bin  (public, 1.41M entries)
  2. dconstruct sid_addresses.tsv      (native function names, if present)
  3. FNV-1a 64 of every string in every DC string table of the corpus
  4. FNV-1a 64 of tokens derived from those strings (split on whitespace,
     parentheses, quotes, ':' '/' '.' etc.) and simple affix variants
  5. Optional extra wordlists (--extra file, one candidate per line)

Then every SID *referenced* by the corpus (entry names/types, state ids,
declarations, events, tracks, call targets, call args, symbol-table refs)
is counted and checked for resolution.

Usage: build_sid_dict.py <db_dir> <sidbase.bin> <out_dir> [--sid-addresses tsv] [--extra f]
Outputs:
  <out_dir>/sid_full.tsv           every known SID (private, large)
  <out_dir>/sid_referenced.json    referenced SIDs: name, source, count, files (sample)
  <out_dir>/sid_unresolved.tsv     referenced but unresolved, by count
  <out_dir>/sid_stats.json
"""
import argparse
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
from dclib import SidDB, fnv1a64, sidhex  # noqa: E402

SPLIT = re.compile(r"[\s()\[\]{}\"'`,;=<>|]+")
SUBSPLIT = re.compile(r"[:/.]+")


def candidates(s):
    yield s
    s2 = s.strip()
    if s2 != s:
        yield s2
    for tok in SPLIT.split(s):
        if not tok:
            continue
        yield tok
        yield tok.lower()
        for sub in SUBSPLIT.split(tok):
            if sub:
                yield sub
        # strip trailing punctuation / format specifiers
        t2 = tok.strip("%.:-_!?#")
        if t2 and t2 != tok:
            yield t2
        if tok.endswith(".dcx") or tok.endswith(".dc"):
            base = os.path.basename(tok).rsplit(".", 1)[0]
            yield base


def iter_referenced(rec):
    """Yield (sid_hex, role) for every SID a file references."""
    for e in rec.get("entries", []):
        yield e["name"], "entry-name"
        yield e["type"], "entry-type"
    for ss in rec.get("state_scripts", []):
        yield ss["id"], "state-script"
        yield ss["initial_state"], "state"
        for d in ss["declarations"]:
            yield d["id"], "declaration"
            yield d["type"], "decl-type"
            v = d.get("value")
            if isinstance(v, dict) and v.get("raw") and v["raw"] != "0" * 16:
                yield v["raw"], "decl-value"
        for st in ss["states"]:
            yield st["id"], "state"
            for b in st["blocks"]:
                if b["event"]:
                    yield b["event"], "event-handler"
                for t in b["tracks"]:
                    yield t["id"], "track"
    for lam in rec.get("lambdas", []):
        if lam["name"]:
            yield lam["name"], "lambda-name"
        for _idx, fn, args in lam["calls"]:
            if fn:
                yield fn, "call-target"
            for a in args:
                if a and a[0] == "s" and int(a[1], 16) > 0xFFFFF:
                    yield a[1], "call-arg"
    for s in rec.get("sid_refs", {}):
        yield s, "symbol-ref"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("sidbase")
    ap.add_argument("out")
    ap.add_argument("--sid-addresses")
    ap.add_argument("--extra", action="append", default=[])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    S = SidDB()
    n_base = S.load_sidbase(a.sidbase)
    if a.sid_addresses and os.path.exists(a.sid_addresses):
        for line in open(a.sid_addresses, encoding="utf-8", errors="replace"):
            parts = line.rstrip("\n").split("\t")
            for p in parts:
                if p and not re.fullmatch(r"(0x)?[0-9a-fA-F]{8,16}", p):
                    S.add(p, "sid_addresses")
    before = len(S.map)

    n_str = 0
    with gzip.open(os.path.join(a.db, "strings.tsv.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            _file, _, s = line.rstrip("\n").partition("\t")
            n_str += 1
            for c in candidates(s):
                if c:
                    S.add(c, "corpus-string")
    after_strings = len(S.map)

    for path in a.extra:
        for line in open(path, encoding="utf-8", errors="replace"):
            w = line.strip()
            if w:
                S.add(w, "extra:" + os.path.basename(path))

    # referenced-SID census
    count = Counter()
    roles = defaultdict(Counter)
    files = defaultdict(set)
    with gzip.open(os.path.join(a.db, "corpus.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for h, role in iter_referenced(rec):
                if h == "0" * 16:
                    continue
                count[h] += 1
                roles[h][role] += 1
                if len(files[h]) < 12:
                    files[h].add(rec["file"])
                # file path itself as a candidate (module names)
            base = os.path.basename(rec["file"]).rsplit(".", 1)[0]
            S.add(base, "file-name")
            S.add(rec["file"].rsplit(".", 1)[0], "file-name")

    resolved = {h for h in count if S.get(int(h, 16)) is not None}
    by_src = Counter(S.source[int(h, 16)] for h in resolved)
    stats = {
        "sidbase_entries": n_base,
        "dictionary_size": len(S.map),
        "added_from_corpus_strings": after_strings - before,
        "corpus_strings_scanned": n_str,
        "referenced_unique": len(count),
        "referenced_resolved": len(resolved),
        "referenced_unresolved": len(count) - len(resolved),
        "resolution_rate": round(len(resolved) / max(1, len(count)), 4),
        "resolved_by_source": dict(by_src),
        "weighted_resolution_rate": round(sum(count[h] for h in resolved) / max(1, sum(count.values())), 4),
    }
    by_role = {}
    for h in count:
        for r in roles[h]:
            t = by_role.setdefault(r, [0, 0])
            t[0] += 1
            t[1] += h in resolved
    stats["by_role_unique_total_resolved"] = by_role
    json.dump(stats, open(os.path.join(a.out, "sid_stats.json"), "w"), indent=1)
    print(json.dumps(stats, indent=1))

    S.save_tsv(os.path.join(a.out, "sid_full.tsv"))
    ref = {}
    for h, c in count.most_common():
        v = S.get(int(h, 16))
        ref[h] = {"string": v, "source": S.source.get(int(h, 16)), "count": c,
                  "roles": dict(roles[h]), "files": sorted(files[h])}
    json.dump(ref, open(os.path.join(a.out, "sid_referenced.json"), "w"))
    with open(os.path.join(a.out, "sid_unresolved.tsv"), "w") as fo:
        for h, c in count.most_common():
            if h not in resolved:
                fo.write(f"{h}\t{c}\t{','.join(f'{k}:{v}' for k, v in roles[h].items())}\t{';'.join(sorted(files[h])[:5])}\n")


if __name__ == "__main__":
    main()
