#!/usr/bin/env python3
"""Isolated authored fixture round-trip. Restores decompiler SID seed in finally."""
import argparse, json, struct, subprocess, sys
from pathlib import Path
from build import HERE, ROOT, run, sha
sys.path.insert(0,str(ROOT/'tools/sid'))
from fnv import fnv1a64

def extend(seed,name):
    n=struct.unpack_from('<Q',seed)[0]
    entries=[(h,o+16) for h,o in struct.iter_unpack('<QQ',seed[8:8+16*n])]
    entries.append((fnv1a64(name),len(seed)+16))
    return struct.pack('<Q',n+1)+b''.join(struct.pack('<QQ',*e) for e in sorted(entries))+seed[8+16*n:]+name.encode()+b'\0'

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--compiler',type=Path,required=True);a.add_argument('--dconstruct',type=Path,required=True);a.add_argument('--output',type=Path,required=True);v=a.parse_args();out=v.output.resolve()
    if not out.is_relative_to((ROOT/'.private').resolve()):a.error('round-trip output must be private')
    out.mkdir(parents=True,exist_ok=True);sidbase=v.dconstruct.resolve().parent/'sidbase.bin';original_seed=sidbase.read_bytes()
    before=out/'roundtrip-before.bin';after=out/'roundtrip-after.bin';source=HERE/'src/roundtrip.dcpl'
    try:
        sidbase.write_bytes(extend(original_seed,'drawer_diag_roundtrip'))
        run([v.compiler,source,before],out/'compile-before.log')
        run([v.dconstruct,'-i',before,'-o',out/'roundtrip.asm'],out/'decompile.log')
        run([v.compiler,out/'roundtrip.dcpl',after],out/'compile-after.log')
    finally:sidbase.write_bytes(original_seed)
    summary={'kind':'authored no-argument smoke fixture; not a full drawer or native API round-trip','compiler_sha256':sha(v.compiler),
             'decompiler_sha256':sha(v.dconstruct),'source_sha256':sha(source),
             'before_sha256':sha(before),'after_sha256':sha(after),
             'byte_identical':before.read_bytes()==after.read_bytes(),'seed_restored':sidbase.read_bytes()==original_seed,
             'seed_extension':'one sorted entry for our authored function; not an upstream SID database change',
             'runtime_game_tested':False}
    (out/'roundtrip.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    if not summary['byte_identical']:raise RuntimeError('round-trip bytes differ; review decompiler/typing limitations')
if __name__=='__main__':main()
