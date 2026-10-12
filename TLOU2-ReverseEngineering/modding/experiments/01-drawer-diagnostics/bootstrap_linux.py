#!/usr/bin/env python3
"""Private Debian/GCC research build of pinned dconstruct core. Not an official Windows build."""
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path
from build import ROOT, PIN, HERE, sha
GVD_URL='https://deb.debian.org/debian/pool/main/g/graphviz/libgraphviz-dev_2.42.4-3_amd64.deb'
GVD_SHA='fa2ebed1e136b351f43b36fd289913576193fcb578425145ec6089eac42277a3'
CTRE_PIN='dab09336d6a221299159a5ddc76cdcf6967ba9dd'
CTRE_URL=f'https://raw.githubusercontent.com/hanickadot/compile-time-regular-expressions/{CTRE_PIN}/single-header/ctre.hpp'
CTRE_SHA='f0d9a70c782914f83066554cc0690e6c68c83f5bfbc8fab111d3f6affdcc653a'
SEED_SHA='c2d983bfb5afbfc51591a2d9c003e2e801abe841042768107dc0bd91ce5ceb94'

def fetch(url,path,expected):
    if not path.exists():subprocess.run(['curl','--fail','--location','--silent','--show-error',url,'-o',str(path)],check=True)
    if sha(path)!=expected:raise ValueError(f'Dependency hash mismatch: {path}')

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--vendor',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--jobs',type=int,default=4);v=a.parse_args()
    vendor=v.vendor.resolve();out=v.output.resolve();private=(ROOT/'.private').resolve()
    if not all(p.is_relative_to(private) for p in (vendor,out)):a.error('vendor and build must be under .private/')
    if any(c.isspace() for c in str(vendor)+str(out)):a.error('Linux make adapter requires paths without spaces')
    if not vendor.exists():
        vendor.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['git','clone','https://github.com/DeepQuantum/dconstruct',str(vendor)],check=True)
        subprocess.run(['git','-C',str(vendor),'checkout','--detach',PIN],check=True)
    if subprocess.check_output(['git','-C',str(vendor),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Wrong upstream commit')
    if subprocess.check_output(['git','-C',str(vendor),'status','--porcelain'],text=True).strip():raise ValueError('Upstream checkout is dirty')
    seed=vendor/'test/fixtures/dc/sidbase_new_fixed.bin'
    if sha(seed)!=SEED_SHA:raise ValueError('SID seed mismatch')
    out.mkdir(parents=True,exist_ok=True);deps=out/'deps';deps.mkdir(exist_ok=True)
    fetch(GVD_URL,out/'graphviz-dev.deb',GVD_SHA)
    subprocess.run(['dpkg-deb','-x',str(out/'graphviz-dev.deb'),str(deps)],check=True)
    fetch(CTRE_URL,deps/'usr/include/ctre.hpp',CTRE_SHA)
    shutil.copytree(vendor/'include',out/'include',dirs_exist_ok=True)
    h=out/'include/base.h';s=h.read_text()
    for suffix in ('r','imm','b'):
        old=f'operator""_{suffix}(u64 v)';new=f'operator""_{suffix}(unsigned long long v)'
        if old not in s:raise ValueError('LP64 compatibility patch did not match pin')
        s=s.replace(old,new)
    h.write_text(s)
    h=out/'include/compilation/lexer.h';h.write_text(h.read_text().replace('namespace dconstruct','#undef TRUE\n#undef FALSE\nnamespace dconstruct',1))
    h=deps/'usr/include/graphviz/types.h';h.write_text(h.read_text().replace('#define FALSE 0','#undef FALSE').replace('#define TRUE NOT(FALSE)','#undef TRUE').replace('#define TRUE 1','#undef TRUE'))
    (out/'control_flow_graph.cpp').write_text((vendor/'source/decompilation/control_flow_graph.cpp').read_text().replace('agsafeset_html(', 'agsafeset('))
    (out/'windows.h').write_text('''#pragma once
#include <cstdint>
#include <unistd.h>
#include <vector>
using DWORD=uint32_t;
constexpr unsigned MAX_PATH=260;
inline DWORD GetModuleFileNameW(void*,wchar_t* out,DWORD capacity){
 std::vector<char> b(65536);ssize_t n=readlink("/proc/self/exe",b.data(),b.size());if(n<0)return 0;
 for(DWORD i=0;i<capacity && i<static_cast<DWORD>(n);++i)out[i]=static_cast<unsigned char>(b[i]);
 if(static_cast<DWORD>(n)<capacity)out[n]=0;
 return static_cast<DWORD>(n)<capacity?static_cast<DWORD>(n):capacity;
}
''')
    shutil.copyfile(HERE/'src/prelude.h',out/'prelude.h')
    (out/'buildinfo.h').write_text('#pragma once\n#define COMPILER_VERSION "GCC 14.2 Linux research adapter"\n#define BUILD_DATE "2026-10-12"\n#define VERSION "2.2.0-pinned-583b38d8"\n')
    sources=sorted(p for group in ('ast','base','compilation','decompilation','disassembly') for p in (vendor/'source'/group).rglob('*.cpp'))
    flags=f'-std=c++23 -fpermissive -O0 -g0 -ftemplate-depth=4096 -include {out}/prelude.h -I{out} -I{out}/include -I{deps}/usr/include'
    objs=[f'obj/{p.relative_to(vendor/"source")}.o' for p in sources]
    links='-l:libgvc.so.6 -l:libcgraph.so.6 -l:libcdt.so.5 -l:libtbb.so.12'
    make=f'CXX := g++\nFLAGS := {flags}\nOBJS := '+ ' '.join(objs)+'\nall: dconstruct compile_core dcc\n'
    drivers={'dconstruct':vendor/'source/main_cli.cpp','dcc':vendor/'source/main_dcc.cpp','compile_core':HERE/'src/compile_core.cpp'}
    for target,driver in drivers.items():
        make+=f'{target}: $(OBJS) obj/{target}.o\n\t$(CXX) $^ {links} -o $@\nobj/{target}.o: {driver}\n\t@mkdir -p obj\n\t$(CXX) $(FLAGS) -c $< -o $@\n'
    for p,obj in zip(sources,objs):
        actual=out/'control_flow_graph.cpp' if p.name=='control_flow_graph.cpp' else p
        make+=f'{obj}: {actual}\n\t@mkdir -p $(dir $@)\n\t$(CXX) $(FLAGS) -c $< -o $@\n'
    (out/'Makefile').write_text(make)
    with (out/'build.log').open('w') as log:
        subprocess.run(['make','-C',str(out),f'-j{v.jobs}'],stdout=log,stderr=subprocess.STDOUT,check=True)
    shutil.copyfile(seed,out/'sidbase.bin')
    manifest={'upstream_commit':PIN,'upstream_clean':True,'build_kind':'private Linux compatibility build; not official Windows release',
              'compiler_version':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
              'sidbase_original_sha256':SEED_SHA,'ctre_commit':CTRE_PIN,'ctre_sha256':CTRE_SHA,'graphviz_deb_sha256':GVD_SHA,
              'adapter_operations':['LP64 literal-suffix parameter type normalization in copied header',
                'force standard-library includes','GetModuleFileNameW Linux shim for SID-base discovery',
                'private Graphviz 2.42 rendering compatibility; graphs not used','private TRUE/FALSE macro isolation'],
              'upstream_source_sha256':{str(p.relative_to(vendor)):sha(p) for p in sources},
              'executables':{t:sha(out/t) for t in drivers},'runtime_game_tested':False}
    (out/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest['executables'],indent=2))
if __name__=='__main__':main()
