#!/usr/bin/env python3
"""Reproduce the independent MIT reference-disassembler comparison on Linux.
Requires the pinned upstream clone at .private/vendor/t2r-reference.
Compatibility files and disassembled game code remain private.
"""
import json,re,shutil,struct,subprocess
from pathlib import Path
from data import ROOT,load
from corpus import dump
FILES=['dc1/ss-t2/ss-openable-drawer.bin','dc1/ss/ss-investigate-object.bin','dc1/ss/ss-examine.bin','dc1/ss/ss-tumbler-safe.bin','dc1/ss-hud2/ss-hud2-lock-minigame.bin']
build=ROOT/'.private/vendor/t2r-linux';build.mkdir(parents=True,exist_ok=True);shutil.copytree(ROOT/'.private/vendor/t2r-reference/t2r-dc-disasm/src',build/'src',dirs_exist_ok=True)
p=build/'src/script/script-manager-eval.cpp';p.write_text(p.read_text().replace('../stringId/','../stringid/'))
(build/'compat.h').write_text('#include <cstdio>\n#include <cstring>\n#include <cstdint>\n#include <cmath>\ninline int fopen_s(FILE** p,const char* n,const char* m){*p=fopen(n,m);return *p?0:1;}\ninline int memcpy_s(void* d,size_t cap,const void* s,size_t n){if(n>cap)return 1;memcpy(d,s,n);return 0;}\n#define sscanf_s sscanf\n')
(build/'intrin.h').write_text('#include <cstdint>\ninline unsigned char _bittest(const long* p,long b){return (*reinterpret_cast<const uint32_t*>(p)>>b)&1;}\n')
exe=build/'t2r-dc-disasm';sources=sorted((build/'src').rglob('*.cpp'));subprocess.run(['g++','-std=c++17','-O2','-include',str(build/'compat.h'),'-I'+str(build),*(str(p) for p in sources),'-o',str(exe)],check=True,capture_output=True)
db={int(h,16):s for h,s in json.load(open(ROOT/'.private/sid_dictionary.json')).items()};subset={};run=ROOT/'.private/reference_run';(run/'sid1').mkdir(parents=True,exist_ok=True)
for file in FILES:
 b=(ROOT/'.private/extracted'/file).read_bytes();strings=struct.unpack_from('<I',b,12)[0]
 for h, in struct.iter_unpack('<Q',b[:strings//8*8]):
  if h in db:subset[h]=db[h]
base=8+16*len(subset);table=bytearray(struct.pack('<Q',len(subset)));strings=bytearray()
for h,s in sorted(subset.items()):table+=struct.pack('<QQ',h,base+len(strings));strings+=s.encode()+b'\0'
(run/'sid1/sidbase.bin').write_bytes(table+strings)
calls=load('calls.json');report=[]
for file in FILES:
 src=ROOT/'.private/extracted'/file;subprocess.run([str(exe),str(src)],cwd=run,check=True,capture_output=True,timeout=45)
 text=Path(str(src)+'.txt').read_text();ref={int(o,16):name for o,name in re.findall(r'CODE: 0x([0-9A-Fa-f]+).*?DC::kCall(?:Ff)?:\s*\(\s*(\S+)',text)};mine={c['offset']:c['target'][1] for c in calls if c['file']==file and c['target'][0]=='sid'};common=set(ref)&set(mine);mis=[{'offset':hex(o),'indexer':mine[o],'reference':ref[o]} for o in common if mine[o]!=ref[o]]
 report.append({'file':file,'reference_call_offsets':len(ref),'comparable_call_offsets':len(common),'matching_targets':len(common)-len(mis),'mismatches':mis})
dump(ROOT/'databases/reference_validation.json',report);assert not any(r['mismatches'] for r in report);print('Independent matching call targets:',sum(r['matching_targets'] for r in report))
