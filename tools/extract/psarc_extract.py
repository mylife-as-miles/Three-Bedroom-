#!/usr/bin/env python3
"""Extract a PSARC archive (accepts DSAR-wrapped input too).

Usage: psarc_extract.py <archive> <out_dir> [--filter SUBSTR] [--manifest out.json]
Writes every file under <out_dir>/<path>, and optionally a JSON manifest
(path, size, md5-of-name) — the manifest contains no game data.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dsar_unpack import unpack  # noqa: E402


def read_u40(b, o):
    return int.from_bytes(b[o:o + 5], "big")


def parse(buf):
    assert buf[:4] == b"PSAR", buf[:4]
    major, minor = struct.unpack_from(">HH", buf, 4)
    comp = buf[8:12]
    toc_len, ent_size, nfiles, block_size, flags = struct.unpack_from(">IIIII", buf, 12)
    entries = []
    o = 32
    for _ in range(nfiles):
        md5 = buf[o:o + 16]
        zidx = struct.unpack_from(">I", buf, o + 16)[0]
        ulen = read_u40(buf, o + 20)
        off = read_u40(buf, o + 25)
        entries.append((md5, zidx, ulen, off))
        o += ent_size
    # block-size table fills the rest of the TOC
    width = 2 if block_size <= 0x10000 else (3 if block_size <= 0x1000000 else 4)
    nblk = (toc_len - o) // width
    zs = [int.from_bytes(buf[o + i * width:o + (i + 1) * width], "big") for i in range(nblk)]
    return dict(major=major, minor=minor, comp=comp, flags=flags, block_size=block_size,
                entries=entries, zsizes=zs)


def read_entry(buf, info, ent):
    md5, zidx, ulen, off = ent
    out = bytearray()
    bs = info["block_size"]
    zs = info["zsizes"]
    while len(out) < ulen:
        z = zs[zidx] or bs
        chunk = buf[off:off + z]
        want = min(bs, ulen - len(out))
        if z == want and not (chunk[:1] == b"\x78" and z != want):
            data = chunk
        else:
            try:
                data = zlib.decompress(chunk)
            except zlib.error:
                data = chunk
        out += data
        off += z
        zidx += 1
    return bytes(out[:ulen])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive")
    ap.add_argument("out_dir")
    ap.add_argument("--filter", default=None)
    ap.add_argument("--manifest", default=None)
    a = ap.parse_args()
    buf = unpack(open(a.archive, "rb").read())
    info = parse(buf)
    raw = read_entry(buf, info, info["entries"][0])
    names = [n for n in raw.replace(b"\n", b"\0").split(b"\0") if n]
    # TOC entries are sorted by MD5(path), not manifest order: map by hash.
    by_md5 = {e[0]: e for e in info["entries"][1:]}
    man = []
    for name in names:
        ent = by_md5[hashlib.md5(name).digest()]
        rel = name.decode("utf-8").lstrip("/")
        man.append({"path": rel, "size": ent[2]})
        if a.filter and a.filter not in rel:
            continue
        data = read_entry(buf, info, ent)
        dst = os.path.join(a.out_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(data)
    print(f"PSARC v{info['major']}.{info['minor']} {info['comp']!r} flags={info['flags']} "
          f"files={len(names)} block={info['block_size']}")
    if a.manifest:
        json.dump(man, open(a.manifest, "w"), indent=0)


if __name__ == "__main__":
    main()
