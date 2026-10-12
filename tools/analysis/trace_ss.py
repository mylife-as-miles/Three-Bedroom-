#!/usr/bin/env python3
"""Pretty-print a state script: states -> blocks -> tracks -> lambdas -> calls.
Usage: trace_ss.py <file.bin> [--sids sid.tsv] [--state NAME] [--raw]"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dclib import DCFile, SidDB, Tracer, fmt_val, sidhex

def load_sids(path):
    S = SidDB()
    if path and os.path.exists(path):
        S.load_tsv(path)
    return S

def dump_lambda(dc, T, S, off, indent, seen, depth=0):
    lam = dc.lambda_at(off)
    if not lam:
        print(indent + f"<bad lambda {off:#x}>"); return
    r = T.run(lam)
    for c in r["calls"]:
        fn = S.name(c["fn"]) if c["fn"] else "?"
        args = ", ".join(fmt_val(a, S) for a in c["args"])
        print(f"{indent}[{c['idx']:03d}] {fn}({args})")
        for a in c["args"]:
            if a and a[0] == "lambda" and a[1] not in seen and depth < 4:
                seen.add(a[1])
                print(indent + "    { lambda")
                dump_lambda(dc, T, S, a[1], indent + "      ", seen, depth + 1)
                print(indent + "    }")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--sids"); ap.add_argument("--state")
    ap.add_argument("--funcs", action="store_true", help="also dump top-level script-lambda entries")
    a = ap.parse_args()
    S = load_sids(a.sids)
    dc = DCFile(a.file); T = Tracer(dc, S)
    for name, typ, val, _ in dc.entries():
        tn = S.name(typ)
        if tn == "state-script":
            ss = dc.parse_state_script(val, S)
            print(f"STATE-SCRIPT {ss['name']}  initial={ss['initial_state_name']}  src={ss['debug_file']}")
            for st in ss["states"]:
                if a.state and st["name"] != a.state: continue
                print(f"\n== state {st['name']}")
                for b in st["blocks"]:
                    ev = f" {b.get('event_name')}" if b["event"] else ""
                    print(f"  on ({b['type']}{ev})")
                    for t in b["tracks"]:
                        print(f"    track {t['name']}")
                        seen = set()
                        for k, l in enumerate(t["lambdas"]):
                            print(f"      -- segment {k}")
                            dump_lambda(dc, T, S, l, "        ", seen)
        elif a.funcs and tn in ("script-lambda", "function"):
            print(f"\nFUNC {S.name(name)} ({tn})")
            dump_lambda(dc, T, S, val, "    ", set())

if __name__ == "__main__":
    main()
