#!/usr/bin/env python3
"""dclib — minimal, dependency-light reader for Naughty Dog DC00 script binaries
(The Last of Us Part II Remastered, PC 1.6).

Structure knowledge is taken from the public t2r-dc-disasm (icemesh) and
dconstruct (DeepQuantum) projects; this is an independent Python
re-implementation for batch analysis on Linux.

Layout recap
------------
DC_Header (0x28 bytes)
  0x00 'DC00' magic (0x44433030 LE)
  0x04 u32 version (1)
  0x08 u32 text size  -> relocation table lives at this offset
  0x0C u32 strings offset
  0x10 u32 always 1
  0x14 u32 entry count
  0x18 u64 ptr -> Entry[count] (each: sid name, sid type, ptr value)

All pointers are stored as file-relative offsets; a bitmap at <text size>
(u32 byte-count followed by one bit per 8-byte word) marks which 8-byte
words are pointers.

Script code: ScriptLambda (0x50) -> u64 instructions[] (8 bytes each:
opcode, dest, op1, op2, pad[4]) and a u64 symbol table.  Argument
registers start at r49.  `Call/CallFf dest, fnreg, argc`.
"""
from __future__ import annotations

import bisect
import os
import struct
from dataclasses import dataclass, field

MASK64 = 0xFFFFFFFFFFFFFFFF
LAMBDA_FLAG = 0xDEADBEEF1337F00D
ARG0 = 49


def fnv1a64(s: str | bytes) -> int:
    if isinstance(s, str):
        s = s.encode("utf-8", "replace")
    h = 0xCBF29CE484222325
    for c in s:
        h ^= c
        h = (h * 0x100000001B3) & MASK64
    return h


def sidhex(v: int) -> str:
    return f"{v & MASK64:016x}"


OPCODES = [
    "Return", "IAdd", "ISub", "IMul", "IDiv", "FAdd", "FSub", "FMul", "FDiv",
    "LoadStaticInt", "LoadStaticFloat", "LoadStaticPointer", "LoadU16Imm", "LoadU32",
    "LoadFloat", "LoadPointer", "StoreInt", "StoreFloat", "StorePointer", "LookupInt",
    "LookupFloat", "LookupPointer", "MoveInt", "MoveFloat", "MovePointer", "CastInteger",
    "CastFloat", "Call", "CallFf", "IEqual", "IGreaterThan", "IGreaterThanEqual",
    "ILessThan", "ILessThanEqual", "FEqual", "FGreaterThan", "FGreaterThanEqual",
    "FLessThan", "FLessThanEqual", "IMod", "FMod", "IAbs", "FAbs", "GoTo", "Label",
    "Branch", "BranchIf", "BranchIfNot", "OpLogNot", "OpBitAnd", "OpBitNot", "OpBitOr",
    "OpBitXor", "OpBitNor", "OpLogAnd", "OpLogOr", "INeg", "FNeg", "LoadParamCnt",
    "IAddImm", "ISubImm", "IMulImm", "IDivImm", "LoadStaticI32Imm", "LoadStaticFloatImm",
    "LoadStaticPointerImm", "IntAsh", "Move", "LoadStaticU32Imm", "LoadStaticI8Imm",
    "LoadStaticU8Imm", "LoadStaticI16Imm", "LoadStaticU16Imm", "LoadStaticI64Imm",
    "LoadStaticU64Imm", "LoadI8", "LoadU8", "LoadI16", "LoadU16", "LoadI32", "LoadI64",
    "LoadU64", "StoreI8", "StoreU8", "StoreI16", "StoreU16", "StoreI32", "StoreU32",
    "StoreI64", "StoreU64", "INotEqual", "FNotEqual", "StoreArray", "AssertPointer",
    "BreakFlag", "Breakpoint", "QEX_InRangeI",
]
OP = {n: i for i, n in enumerate(OPCODES)}

BLOCK_TYPES = {0: "start", 1: "end", 2: "event", 3: "update", 4: "virtual"}


# --------------------------------------------------------------------------
# SID database
# --------------------------------------------------------------------------
class SidDB:
    """Merged reverse dictionary: dconstruct sidbase + corpus-derived strings."""

    def __init__(self):
        self.map: dict[int, str] = {}
        self.source: dict[int, str] = {}

    def load_sidbase(self, path: str):
        b = open(path, "rb").read()
        n = struct.unpack_from("<Q", b, 0)[0]
        for i in range(n):
            h, o = struct.unpack_from("<QQ", b, 8 + 16 * i)
            if o >= len(b):
                continue
            e = b.find(b"\0", o)
            if h not in self.map:
                self.map[h] = b[o:e].decode("utf-8", "replace")
                self.source[h] = "sidbase"
        return n

    def add(self, s: str, src: str = "corpus") -> int:
        h = fnv1a64(s)
        if h not in self.map:
            self.map[h] = s
            self.source[h] = src
        return h

    def get(self, h: int) -> str | None:
        return self.map.get(h & MASK64)

    def name(self, h: int) -> str:
        s = self.map.get(h & MASK64)
        return s if s is not None else f"#{sidhex(h)}"

    def save_tsv(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            for h in sorted(self.map):
                v = self.map[h].replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
                f.write(f"{sidhex(h)}\t{v}\t{self.source[h]}\n")

    def load_tsv(self, path: str):
        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2 and len(parts[0]) == 16:
                    h = int(parts[0], 16)
                    self.map[h] = parts[1].replace("\\t", "\t").replace("\\n", "\n").replace("\\r", "\r").replace("\\\\", "\\")
                    self.source[h] = parts[2] if len(parts) > 2 else "?"


# --------------------------------------------------------------------------
# DC file
# --------------------------------------------------------------------------
@dataclass
class Instr:
    idx: int
    op: int
    dst: int
    a: int
    b: int

    @property
    def name(self):
        return OPCODES[self.op] if self.op < len(OPCODES) else f"op{self.op}"


@dataclass
class Lambda:
    offset: int
    instr_off: int
    sym_off: int
    n_instr: int
    func_name: int
    scope: int
    instrs: list = field(default_factory=list)


class DCFile:
    def __init__(self, path: str, data: bytes | None = None):
        self.path = path
        self.b = data if data is not None else open(path, "rb").read()
        b = self.b
        if b[:4] != b"00CD":
            raise ValueError("not DC00")
        (self.version, self.text_size, self.strings_off, _one,
         self.n_entries) = struct.unpack_from("<IIIII", b, 4)
        self.entries_ptr = struct.unpack_from("<Q", b, 0x18)[0]
        rt = self.text_size
        self.reloc_n = struct.unpack_from("<I", b, rt)[0]
        self.reloc = b[rt + 4: rt + 4 + self.reloc_n]

    # -- primitive readers ------------------------------------------------
    def u8(self, o): return self.b[o]
    def u16(self, o): return struct.unpack_from("<H", self.b, o)[0]
    def i16(self, o): return struct.unpack_from("<h", self.b, o)[0]
    def u32(self, o): return struct.unpack_from("<I", self.b, o)[0]
    def i32(self, o): return struct.unpack_from("<i", self.b, o)[0]
    def u64(self, o): return struct.unpack_from("<Q", self.b, o)[0]
    def f32(self, o): return struct.unpack_from("<f", self.b, o)[0]

    def is_ptr(self, o: int) -> bool:
        if o & 7 or o < 0 or o >= self.text_size:
            return False
        w = o >> 3
        return bool(self.reloc[w >> 3] & (1 << (w & 7))) if (w >> 3) < len(self.reloc) else False

    def ptr(self, o: int) -> int | None:
        return self.u64(o) if self.is_ptr(o) else None

    def cstr(self, o: int, limit: int = 4096) -> str | None:
        if o is None or o <= 0 or o >= len(self.b):
            return None
        e = self.b.find(b"\0", o, o + limit)
        if e < 0:
            return None
        return self.b[o:e].decode("utf-8", "replace")

    def in_strings(self, o: int) -> bool:
        return self.strings_off <= o < self.text_size

    # -- strings ----------------------------------------------------------
    def strings(self) -> list[str]:
        """All NUL-terminated strings in the string table region."""
        seg = self.b[self.strings_off:self.text_size]
        out = []
        for s in seg.split(b"\0"):
            if len(s) >= 2:
                try:
                    out.append(s.decode("utf-8"))
                except UnicodeDecodeError:
                    pass
        return out

    # -- entries ----------------------------------------------------------
    def entries(self):
        out = []
        for i in range(self.n_entries):
            o = self.entries_ptr + 24 * i
            out.append((self.u64(o), self.u64(o + 8), self.u64(o + 16), o))
        return out

    # -- lambdas ----------------------------------------------------------
    def find_lambdas(self) -> list[Lambda]:
        """Scan for ScriptLambda structs by their 0xDEADBEEF1337F00D marker."""
        marker = struct.pack("<Q", LAMBDA_FLAG)
        res = []
        start = 0
        while True:
            k = self.b.find(marker, start, self.text_size)
            if k < 0:
                break
            start = k + 8
            base = k - 0x28
            if base < 0 or base & 7:
                continue
            if not (self.is_ptr(base) and self.is_ptr(base + 8)):
                continue
            io, so = self.u64(base), self.u64(base + 8)
            n = self.u32(base + 0x34)
            if n <= 0 or n > 200000 or io + 8 * n > len(self.b):
                continue
            lam = Lambda(base, io, so, n, self.u64(base + 0x20), self.u64(base + 0x40))
            lam.instrs = [Instr(i, *self.b[io + 8 * i: io + 8 * i + 4]) for i in range(n)]
            res.append(lam)
        return res

    def lambda_at(self, base: int) -> Lambda | None:
        if base is None or base + 0x50 > len(self.b) or self.u64(base + 0x28) != LAMBDA_FLAG:
            return None
        io, so = self.u64(base), self.u64(base + 8)
        n = self.u32(base + 0x34)
        lam = Lambda(base, io, so, n, self.u64(base + 0x20), self.u64(base + 0x40))
        lam.instrs = [Instr(i, *self.b[io + 8 * i: io + 8 * i + 4]) for i in range(n)]
        return lam

    def sym(self, lam: Lambda, i: int) -> int:
        return self.u64(lam.sym_off + 8 * i)

    def sym_is_ptr(self, lam: Lambda, i: int) -> bool:
        return self.is_ptr(lam.sym_off + 8 * i)

    # -- state scripts ----------------------------------------------------
    def parse_state_script(self, o: int, sids: SidDB | None = None) -> dict:
        """Parse a StateScript struct at file offset o."""
        nm = lambda h: sids.name(h) if sids else sidhex(h)
        ss = {
            "offset": o,
            "id": sidhex(self.u64(o)),
            "initial_state": sidhex(self.u64(o + 0x10)),
            "debug_file": self.cstr(self.ptr(o + 0x38)) if self.is_ptr(o + 0x38) else None,
            "line": self.i16(o + 0x32),
            "declarations": [],
            "options_symbols": [],
            "states": [],
        }
        if sids:
            ss["name"] = nm(self.u64(o))
            ss["initial_state_name"] = nm(self.u64(o + 0x10))
        dl = self.ptr(o + 0x08)
        if dl:
            nd = self.u32(dl + 4)
            dp = self.ptr(dl + 8)
            for i in range(nd if dp else 0):
                d = dp + 0x30 * i
                decl = {
                    "id": sidhex(self.u64(d)),
                    "type": sidhex(self.u64(d + 0x10)),
                    "size": self.u16(d + 0x18),
                    "is_var": self.u16(d + 0x1A),
                }
                if sids:
                    decl["name"] = nm(self.u64(d))
                    decl["type_name"] = nm(self.u64(d + 0x10))
                vp = self.ptr(d + 0x20)
                decl["value"] = self._decl_value(vp, self.u64(d + 0x10), sids) if vp else None
                ss["declarations"].append(decl)
        op = self.ptr(o + 0x18)
        if op:
            sa = self.ptr(op + 0x18)
            if sa:
                cnt = self.u32(sa)
                sp = self.ptr(sa + 8)
                if sp:
                    ss["options_symbols"] = [nm(self.u64(sp + 8 * i)) for i in range(min(cnt, 4096))]
        st = self.ptr(o + 0x28)
        n_states = self.i16(o + 0x30)
        for i in range(n_states if st else 0):
            so = st + 0x18 * i
            sid = self.u64(so)
            nblk = self.u64(so + 8)
            bp = self.ptr(so + 0x10)
            state = {"id": sidhex(sid), "blocks": []}
            if sids:
                state["name"] = nm(sid)
            for j in range(nblk if bp else 0):
                bo = bp + 0x50 * j  # SsOnBlock: 0x18 header + 0x38 track group
                state["blocks"].append(self._parse_block(bo, sids))
            ss["states"].append(state)
        return ss

    def _decl_value(self, vp, type_sid, sids):
        t = sids.name(type_sid) if sids else sidhex(type_sid)
        try:
            if t in ("boolean", "bool"):
                return bool(self.u8(vp))
            if t in ("int32", "i32", "int"):
                return self.i32(vp)
            if t in ("uint32", "u32"):
                return self.u32(vp)
            if t in ("uint64", "u64", "int64", "i64"):
                return self.u64(vp)
            if t in ("float", "f32"):
                return round(self.f32(vp), 6)
            if t in ("string",):
                p = self.ptr(vp)
                return self.cstr(p) if p else None
            if t in ("symbol", "sid", "string-id", "string-id-64"):
                v = self.u64(vp)
                return sids.name(v) if sids else sidhex(v)
        except struct.error:
            return None
        v = self.u64(vp) if vp + 8 <= len(self.b) else None
        if v is None:
            return None
        if self.is_ptr(vp):
            return {"ptr": v}
        return {"raw": sidhex(v), "as_sid": sids.get(v) if sids else None}

    def _parse_block(self, bo, sids):
        btype = self.u32(bo)
        evt = self.u64(bo + 8)
        blk = {"type": BLOCK_TYPES.get(btype, str(btype)), "event": sidhex(evt) if evt else None,
               "lambda": self.ptr(bo + 0x10), "tracks": []}
        if sids and evt:
            blk["event_name"] = sids.name(evt)
        tg = bo + 0x18
        ntracks = self.i16(tg + 0x0A)
        tp = self.ptr(tg + 0x10)
        nmp = self.ptr(tg + 0x18)
        blk["debug_name"] = self.cstr(nmp) if nmp else None
        for k in range(ntracks if tp and 0 < ntracks < 4096 else 0):
            to = tp + 0x18 * k
            tid = self.u64(to)
            nl = self.i16(to + 0x0A)
            lp = self.ptr(to + 0x10)
            lams = []
            for m in range(nl if lp and 0 < nl < 65536 else 0):
                p = self.ptr(lp + 0x10 * m)
                if p:
                    lams.append(p)
            tr = {"id": sidhex(tid), "lambdas": lams}
            if sids:
                tr["name"] = sids.name(tid)
            blk["tracks"].append(tr)
        return blk


# --------------------------------------------------------------------------
# Lambda tracer — linear register simulation for call/arg recovery
# --------------------------------------------------------------------------
class Tracer:
    """Best-effort linear simulation of a ScriptLambda.

    Tracks register contents as tagged values:
      ('sid', v)  symbol/SID      ('int', v)  ('float', v)
      ('str', s)  string literal  ('lambda', off) nested lambda pointer
      ('ptr', off) other data pointer  ('arg', n) incoming argument
      ('ret', fn_sid) result of a call     None = unknown
    Branches are not followed; register state is carried linearly, which is
    reliable for argument marshalling (always emitted straight before a Call).
    """

    def __init__(self, dc: DCFile, sids: SidDB | None = None):
        self.dc = dc
        self.sids = sids

    def run(self, lam: Lambda):
        dc = self.dc
        regs: dict[int, tuple | None] = {}
        calls = []
        refs = []  # every symbol-table SID/pointer loaded
        branches = []
        for ins in lam.instrs:
            n = ins.op
            d, a, b = ins.dst, ins.a, ins.b
            if n == OP["LookupPointer"] or n == OP["LookupInt"]:
                v = dc.sym(lam, a)
                regs[d] = ("sid", v)
                refs.append(("lookup", v))
            elif n == OP["LoadStaticU64Imm"] or n == OP["LoadStaticI64Imm"]:
                v = dc.sym(lam, a)
                if dc.sym_is_ptr(lam, a):
                    regs[d] = self._ptrval(v)
                else:
                    regs[d] = ("sid", v)
                    refs.append(("u64", v))
            elif n in (OP["LoadStaticPointerImm"], OP["LoadStaticPointer"]):
                v = dc.sym(lam, a)
                regs[d] = self._ptrval(v) if dc.sym_is_ptr(lam, a) else ("sid", v)
                if regs[d][0] == "sid":
                    refs.append(("u64", v))
            elif n == OP["LoadStaticI32Imm"] or n == OP["LoadStaticInt"]:
                regs[d] = ("int", struct.unpack("<i", struct.pack("<I", dc.sym(lam, a) & 0xFFFFFFFF))[0])
            elif n == OP["LoadStaticU32Imm"]:
                regs[d] = ("int", dc.sym(lam, a) & 0xFFFFFFFF)
            elif n in (OP["LoadStaticU8Imm"], OP["LoadStaticI8Imm"], OP["LoadStaticU16Imm"], OP["LoadStaticI16Imm"]):
                regs[d] = ("int", dc.sym(lam, a))
            elif n in (OP["LoadStaticFloatImm"], OP["LoadStaticFloat"]):
                raw = dc.sym(lam, a) & 0xFFFFFFFF
                regs[d] = ("float", round(struct.unpack("<f", struct.pack("<I", raw))[0], 5))
            elif n == OP["LoadU16Imm"]:
                regs[d] = ("int", a | (b << 8))
            elif n in (OP["Move"], OP["MoveInt"], OP["MoveFloat"], OP["MovePointer"]):
                regs[d] = regs.get(a)
            elif n in (OP["Call"], OP["CallFf"]):
                fn = regs.get(a)
                args = [regs.get(ARG0 + k) for k in range(b)]
                fsid = fn[1] if fn and fn[0] == "sid" else None
                calls.append({"idx": ins.idx, "fn": fsid, "argc": b, "args": args, "far": n == OP["CallFf"]})
                regs[d] = ("ret", fsid)
            elif n in (OP["Branch"], OP["BranchIf"], OP["BranchIfNot"]):
                branches.append((ins.idx, ins.name, d | (b << 8) if n == OP["Branch"] else a | (b << 8)))
            elif n == OP["Return"]:
                pass
            elif n in (OP["LoadParamCnt"],):
                regs[d] = None
            else:
                if n < len(OPCODES) and not OPCODES[n].startswith("Store"):
                    regs[d] = None
        return {"calls": calls, "refs": refs, "branches": branches}

    def _ptrval(self, v):
        dc = self.dc
        if v + 0x30 <= len(dc.b) and dc.u64(v + 0x28) == LAMBDA_FLAG if v + 0x30 <= len(dc.b) else False:
            return ("lambda", v)
        if dc.in_strings(v):
            s = dc.cstr(v)
            if s is not None:
                return ("str", s)
        return ("ptr", v)


def fmt_val(v, sids: SidDB | None):
    if v is None:
        return "?"
    t, x = v
    if t == "sid":
        if x == 0:
            return "0"
        if sids:
            s = sids.get(x)
            if s is not None:
                return s
        # small ints loaded via u64 imm
        if x < 1 << 20:
            return str(x)
        return f"#{sidhex(x)}"
    if t == "int":
        return str(x)
    if t == "float":
        return repr(x)
    if t == "str":
        return '"' + x.replace('"', '\\"')[:200] + '"'
    if t == "lambda":
        return f"<lambda@{x:#x}>"
    if t == "ptr":
        return f"<ptr@{x:#x}>"
    if t == "ret":
        return f"({sids.name(x) if sids and x else '?'} ...)"
    return str(v)


def iter_corpus(root: str):
    for dp, _dn, fn in os.walk(root):
        for f in sorted(fn):
            if f.endswith(".bin"):
                yield os.path.join(dp, f)
