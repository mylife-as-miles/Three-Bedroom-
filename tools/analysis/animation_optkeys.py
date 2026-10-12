#!/usr/bin/env python3
"""animation_optkeys — extract (i32 key, value) option arrays built with #%alloc-array in
dconstruct .dcpl output and attribute each array to the call that consumes it.

Usage: python3 -I tools/analysis/animation_optkeys.py [out.jsonl.gz]
Writes one JSON record per consuming call: file, func, target, anim, ctx(state/fn), pairs[[key,type,value]].
"""
import gzip, json, os, re, sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROOT = os.path.join(os.environ.get("TLOU2_PRIVATE", os.path.join(REPO, ".private")), "dconstruct_out", "dc1")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, ".private", "scratch", "animation", "optarrays.jsonl.gz")

re_alloc = re.compile(r"\b(var_\d+) = #%alloc-array\(single-frame, 16, (\d+), 1\)")
re_key = re.compile(r"^\s*\*\(i32 \*\)\*\(\*(var_\d+) \+ \((\d+) \* 8\)\) = (-?\d+);")
re_val = re.compile(r"^\s*\*\((\w+) \*\)\(\*\(\*(var_\d+) \+ \((\d+) \* 8\)\) \+ 8\) = (.*);\s*$")
re_assign = re.compile(r"^\s*(?:\w+\??\s+)?(var_\d+) = (.*?);\s*$")
re_state = re.compile(r"^\s*state ([\w\-?!*<>=/.%+]+) \{")
re_script = re.compile(r"^\s*statescript\b")
re_fn = re.compile(r"^[\w?]+\s+([\w\-?!*<>=/.%+]+)\((.*)\) \{\s*$")
re_block = re.compile(r"^\s*block ([\w\-?!*<>=/.%+]+)")


def split_args(s):
    out, depth, cur, q = [], 0, "", False
    for ch in s:
        if ch == '"':
            q = not q
        if not q:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            if ch == "," and depth == 0:
                out.append(cur.strip()); cur = ""; continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def find_call(line, var):
    """return (fname, args) for the innermost call whose args contain var as a top-level arg"""
    for m in re.finditer(r"([\w\-?!*<>=/.%+#]+)\(", line):
        name = m.group(1)
        i = m.end(); depth = 1; q = False; j = i
        while j < len(line) and depth:
            c = line[j]
            if c == '"':
                q = not q
            elif not q:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
            j += 1
        args = split_args(line[i:j - 1])
        if var in args:
            return name, args
    return None, None


def main():
    recs = []
    for dp, _dn, fns in os.walk(ROOT):
        for fn in fns:
            if not fn.endswith(".dcpl"):
                continue
            path = os.path.join(dp, fn)
            rel = os.path.relpath(path, ROOT)[:-5]
            arrays = {}  # var -> {"n":, "pairs":{slot:[key,type,val]}}
            assigns = {}
            ctx = {"script": "", "state": "", "block": "", "fn": ""}
            for line in open(path, encoding="utf-8", errors="replace"):
                m = re_fn.match(line)
                if m:
                    ctx = {"script": "", "state": "", "block": "", "fn": m.group(1)}
                m = re_script.match(line)
                if m:
                    ctx = {"script": os.path.basename(rel), "state": "", "block": "", "fn": ""}
                m = re_state.match(line)
                if m:
                    ctx["state"] = m.group(1)
                m = re_block.match(line)
                if m:
                    ctx["block"] = m.group(1)
                m = re_alloc.search(line)
                if m:
                    arrays[m.group(1)] = {"n": int(m.group(2)), "pairs": {}}
                    continue
                m = re_key.match(line)
                if m and m.group(1) in arrays:
                    arrays[m.group(1)]["pairs"].setdefault(int(m.group(2)), [None, None, None])[0] = int(m.group(3))
                    continue
                m = re_val.match(line)
                if m and m.group(2) in arrays:
                    ty, var, slot, val = m.groups()
                    p = arrays[var]["pairs"].setdefault(int(slot), [None, None, None])
                    if ty == "u64" and val == "0" and p[1] is None:
                        continue
                    if re.fullmatch(r"var_\d+", val) and val in assigns:
                        val = val + "{" + " | ".join(assigns[val][-4:]) + "}"
                    p[1] = ty; p[2] = val
                    continue
                m = re_assign.match(line)
                if m:
                    assigns.setdefault(m.group(1), []).append(m.group(2))
                    if len(assigns[m.group(1)]) > 8:
                        assigns[m.group(1)] = assigns[m.group(1)][-8:]
                for var in list(arrays):
                    if re.search(r"\b" + var + r"\b", line):
                        name, args = find_call(line, var)
                        if name:
                            a = arrays.pop(var)
                            recs.append({"file": rel, "func": name, "argpos": args.index(var),
                                         "args": [x if x != var else "<opts>" for x in args],
                                         "ctx": dict(ctx), "n": a["n"],
                                         "pairs": [a["pairs"][k] for k in sorted(a["pairs"])]})
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    print(len(recs), "records ->", OUT)


if __name__ == "__main__":
    main()
