#!/usr/bin/env python3
"""Unwrap a Naughty Dog PC DSAR container into the plain PSARC it encloses.

DSAR layout (observed on TLOU2R PC 1.6 bin.psarc):
  0x00 char[4]  'DSAR'
  0x04 u16      version major (3)
  0x06 u16      version minor (1)
  0x08 u32      block count
  0x0C u32      header size (= 0x20 + 32*count, data starts here)
  0x10 u64      total uncompressed size
  0x18 char[8]  'PADDING*'
  0x20 block[count], 32 bytes each:
       u64 uncompressed offset, u64 compressed offset,
       u32 uncompressed size,   u32 compressed size,
       u8 codec (3 = LZ4 raw block, 254 = stored / zero-fill if csize==0), 7 bytes pad (0x55)

Usage: dsar_unpack.py <in.dsar> <out.psarc>
"""
import struct
import sys

import lz4.block


def unpack(src: bytes) -> bytes:
    if src[:4] != b"DSAR":
        return src  # already plain
    count, hdr, total = struct.unpack_from("<IIQ", src, 8)
    out = bytearray(total)
    for i in range(count):
        uoff, coff, usz, csz, codec = struct.unpack_from("<QQIIB", src, 0x20 + i * 32)
        blob = src[coff:coff + csz]
        if codec == 3:
            data = lz4.block.decompress(blob, uncompressed_size=usz)
        elif codec == 254 and csz == 0:
            data = bytes(usz)  # zero-fill (alignment padding between files)
        elif codec == 254 or csz == usz:
            data = blob
        else:
            raise ValueError(f"block {i}: unknown codec {codec}")
        if len(data) != usz:
            raise ValueError(f"block {i}: size mismatch {len(data)} != {usz}")
        out[uoff:uoff + usz] = data
    return bytes(out)


if __name__ == "__main__":
    data = unpack(open(sys.argv[1], "rb").read())
    open(sys.argv[2], "wb").write(data)
    print(f"wrote {len(data)} bytes, magic={data[:4]!r}")
