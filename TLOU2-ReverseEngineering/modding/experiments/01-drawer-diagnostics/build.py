#!/usr/bin/env python3
"""Compile independently authored observer tracks and weave a private drawer copy.
Never invokes the corpus batch analyzer, game install, package loader, or deployment.
"""
import argparse, hashlib, json, re, struct, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT / 'tools' / 'analysis'))
sys.path.append(str(ROOT / 'tools' / 'sid'))
from corpus import DC
from fnv import fnv1a64
HERE = Path(__file__).resolve().parent
PIN = '583b38d8b25b2f0b2cd079db70d8caac0a69f3a7'
ORIGINAL_SHA256 = 'b69fb082a493a76a97405b052542047e530ae4d6da33ca15787114a487e3a0a5'
DEFAULT_ACTOR = 'drawer-wat-kitchen-apartment-1'
DIAG_VARS = ['drawer-diag-enabled', 'drawer-diag-key-latch']
STATES = ['wait-interact', 'interact', 'scavenge-move-to', 'scavenge-enter',
          'scavenge-pickup', 'scavenge-exit', 'scavenge-early-exit', 'spawned-open',
          'wait-pickup', 'melee-abort', 'complete']
APIS = '''
using #get-self-id as far () -> u64;
using #keyboard-button-pressed? as far (u64) -> bool;
using #get-boolean as far (u64, u64) -> bool;
using #set-boolean as far (u64, bool, u64) -> u0;
using #get-float as far (u64, u64) -> f32;
using #get-symbol as far (u64, u64) -> u64;
using #entity-exists? as far (u64) -> bool;
using #player-is-crouched? as far () -> bool;
using #get-animation-playing? as far (u64, u64, i32) -> bool;
using #get-animation-phase as far (u64, i32, u64) -> f32;
using #string-debug as far (u64) -> string;
using #get-bound-frame as far (u64, u64) -> u8*;
using #get-object-locator as far (u64) -> u8*;
using #get-locator-distance-xz as far (u8*, u8*) -> f32;
using #angle-in-between-locators as near (u8*, u8*, i32) -> f32;
using #alloc-point as far (f32, f32, f32, i32) -> u8*;
using #debug-draw-string-2d as far (u8*, string, i32, f32, f32, i32, i32, i32, f32) -> u0;
'''
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(args, log):
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    log.write_text(r.stdout + r.stderr)
    if r.returncode: raise RuntimeError(f'{args[0]} failed ({r.returncode}); see {log}')
def dictionary(source):
    names = set(STATES + DIAG_VARS + ['state-script', 'script-lambda', 'ss-openable-drawer', 'drawer-diag-observer', 'drawer-diag-template'])
    names.update(re.findall(r'#([A-Za-z_][A-Za-z0-9_?:/.-]*)', source + APIS))
    return {fnv1a64(n): n for n in names}

class Image:
    """Append structures, then rebuild strings/relocation bitmap once."""
    def __init__(self, original, template):
        self.o, self.t = original, template
        self.b = bytearray(original.b[:original.strings])
        self.ptrs = {p: self.oldptr(original.q(p)) for p in range(0, original.strings, 8) if original.ptr(p)}
        self.base = self.append(template.b[32:template.strings]) - 32
        for p in range(32, template.strings, 8):
            if template.ptr(p):
                v = template.q(p)
                self.ptrs[self.base + p] = ('t', v-template.strings) if v >= template.strings else (self.base+v if v else 0)
    def oldptr(self, v):
        return ('o', v-self.o.strings) if v >= self.o.strings else v
    def append(self, b):
        self.b.extend(b'\0' * ((-len(self.b)) % 8)); p = len(self.b); self.b.extend(b); return p
    def copy(self, p, n):
        out = self.append(bytes(self.b[p:p+n]))
        for slot in range(p, p+n, 8):
            if slot in self.ptrs: self.ptrs[out+slot-p] = self.ptrs[slot]
        return out
    def q(self, p, v): struct.pack_into('<Q', self.b, p, v)
    def ptr(self, p, v): self.ptrs[p] = v; self.q(p, v if isinstance(v,int) else 0)
    def finish(self):
        self.b.extend(b'\0' * ((-len(self.b)) % 8)); strings = len(self.b)
        oldstrings = self.o.b[self.o.strings:self.o.text]
        newstrings = self.t.b[self.t.strings:self.t.text]
        self.b.extend(oldstrings + newstrings)
        text = len(self.b)
        for slot, value in self.ptrs.items():
            if isinstance(value,tuple):
                origin, offset = value
                value = strings + (len(oldstrings) if origin=='t' else 0) + offset
            if value and not 32 <= value < text: raise ValueError(f'Invalid relocated target at {slot:x}: {value:x}')
            self.q(slot,value)
        bitmap = bytearray((text+63)//64)
        for slot in self.ptrs:
            assert slot % 8 == 0
            bitmap[slot//64] |= 1 << ((slot//8)%8)
        struct.pack_into('<II', self.b, 8, text, strings)
        self.b.extend(struct.pack('<I',len(bitmap)) + bitmap)
        return bytes(self.b)

def weave(original, template, output, db):
    o,t = DC(original,'original',db),DC(template,'template',db)
    os,oc=o.states();ts,tc=t.states()
    assert len(os)==len(ts)==1
    assert os[0]['name']=='ss-openable-drawer'
    assert set(s['name'] for s in os[0]['states'])==set(STATES)
    assert set(s['name'] for s in ts[0]['states'])==set(STATES)
    image = Image(o,t); changes=[]
    next_counter = 1 + max(o.q(o.q(tr['offset']+16)+i*16+8) for st in os[0]['states'] for bl in st['blocks'] for tr in bl['tracks'] for i in range(len(tr['lambdas'])))
    templates={s['name']:s for s in ts[0]['states']}
    for state in os[0]['states']:
        blocks=state['blocks']; target=templates[state['name']]['blocks'][0]
        assert target['kind']=='update' and len(target['tracks'])==1
        added_track=target['tracks'][0]['offset']+image.base
        sl=t.q(target['tracks'][0]['offset']+16)+image.base
        image.q(sl+8,next_counter); next_counter+=1
        original_bt=o.q(state['offset']+16)
        new_bt=image.copy(original_bt,len(blocks)*80)
        updates=[(i,b) for i,b in enumerate(blocks) if b['kind']=='update']
        assert len(updates)<=1
        if updates:
            i,block=updates[0]; bp=new_bt+i*80
            nt=len(block['tracks']); oldtracks=o.q(block['offset']+40)
            new_tt=image.copy(oldtracks,nt*24)
            added=image.copy(added_track,24); assert added==new_tt+nt*24
            struct.pack_into('<H',image.b,added+8,nt)
            struct.pack_into('<HH',image.b,bp+32,o.short(block['offset']+32)+1,nt+1)
            image.ptr(bp+40,new_tt)
            new_count=len(blocks)
        else:
            # The new update block must immediately follow the copied old block array.
            added_block=image.copy(target['offset']+image.base,80)
            assert added_block==new_bt+len(blocks)*80
            new_count=len(blocks)+1
        image.q(state['offset']+8,new_count); image.ptr(state['offset']+16,new_bt)
        changes.append({'state':state['name'],'original_block_count':len(blocks),
                        'patched_block_count':new_count,'added_update_tracks':1})
    # Append diagnostic declarations; preserve every original variable offset/default.
    op=os[0]['offset'];tp=ts[0]['offset'];od=o.q(op+8);td=t.q(tp+8)
    on=o.u32(od+4);tn=t.u32(td+4);assert tn==2
    decls=image.copy(o.q(od+8),on*48)
    added=image.copy(t.q(td+8)+image.base,tn*48);assert added==decls+on*48
    oldtotal=o.u32(od)
    for i,name in enumerate(DIAG_VARS):
        p=added+i*48
        raw=t.q(t.q(td+8)+i*48)
        # Pinned compiler hashes the '#'-prefixed declaration spelling; getters hash unprefixed names.
        assert raw in (fnv1a64(name),fnv1a64('#'+name))
        image.q(p,fnv1a64(name))
        size=t.short(t.q(td+8)+i*48+24)
        assert oldtotal+size<65536
        struct.pack_into('<H',image.b,p+24,oldtotal+size)
    newdecl=image.append(struct.pack('<IIQ',oldtotal+t.u32(td),on+tn,0))
    image.ptr(newdecl+8,decls);image.ptr(op+8,newdecl)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(image.finish())
    return changes

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--original',type=Path,required=True)
    a.add_argument('--modules',type=Path,required=True)
    a.add_argument('--compiler',type=Path,required=True,help='compile_core, built with pinned upstream core')
    a.add_argument('--dconstruct',type=Path,required=True)
    a.add_argument('--vendor',type=Path,required=True)
    a.add_argument('--output',type=Path,required=True,help='must reside under research .private/')
    a.add_argument('--actor',default=DEFAULT_ACTOR)
    v=a.parse_args();out=v.output.resolve();private=(ROOT/'.private').resolve()
    if not out.is_relative_to(private): a.error('outputs must be in ignored .private/ workspace')
    if any(p.resolve().is_relative_to(out) for p in (v.original,v.modules)): a.error('original inputs must be outside output directory')
    if sha(v.original)!=ORIGINAL_SHA256: a.error('drawer does not match analyzed 1.6 source hash')
    commit=subprocess.check_output(['git','-C',str(v.vendor),'rev-parse','HEAD'],text=True).strip()
    dirty=subprocess.check_output(['git','-C',str(v.vendor),'status','--porcelain'],text=True).strip()
    if commit!=PIN or dirty: a.error('dconstruct checkout must match pin and be clean')
    out.mkdir(parents=True,exist_ok=True);before=sha(v.original)
    body=(HERE/'src/observer_body.dcpl').read_text();source=APIS+'\nstatescript #drawer-diag-template {\n options {}\n declarations { bool #drawer-diag-enabled = false; bool #drawer-diag-key-latch = false; }\n'
    for state in STATES:
        logic=body.replace('@TARGET@','0x'+format(fnv1a64(v.actor),'016X')).replace('@STATE@','#'+state)
        for name in DIAG_VARS: logic = logic.replace('#'+name, '0x'+format(fnv1a64(name),'016X'))
        source+=f' state #{state} {{ block update {{ track #drawer-diag-observer {{ lambda {{\n{logic}\n}} }} }} }}\n'
    source+='}\n';(out/'observer.dcpl').write_text(source)
    run([v.compiler,out/'observer.dcpl',out/'observer.bin'],out/'compile.log')
    run([v.dconstruct,'-i',out/'observer.bin','-o',out/'observer.asm'],out/'decompile.log')
    db=dictionary(source)
    result=out/'mod'/'bin'/'dc1'/'ss-t2'/'ss-openable-drawer.bin'
    changes=weave(v.original,out/'observer.bin',result,db)
    assert sha(v.original)==before
    md=DC(v.modules,'modules',db);assert len(md.entries)==1
    mp=md.entries[0]['offset']; count=md.q(mp); table=md.q(mp+8)
    hits=[table+i*40 for i in range(count) if md.string(md.q(table+i*40))=='ss-t2/ss-openable-drawer']
    assert len(hits)==1
    size_slot=hits[0]+16; assert md.q(size_slot)==v.original.stat().st_size
    patched_modules=bytearray(md.b);struct.pack_into('<Q',patched_modules,size_slot,result.stat().st_size)
    mod_registry=result.parents[1]/'modules.bin';mod_registry.write_bytes(patched_modules)
    run([v.dconstruct,'-i',result,'-o',out/'patched-drawer.asm'],out/'patched-decompile.log')
    summary={'schema_version':1,'dconstruct_commit':commit,'compiler_sha256':sha(v.compiler),
             'decompiler_sha256':sha(v.dconstruct),'actor':v.actor,'actor_sid':format(fnv1a64(v.actor),'016X'),
             'actor_binding_runtime_verified':False,'original_sha256':before,'patched_sha256':sha(result),
             'original_bytes':v.original.stat().st_size,'patched_bytes':result.stat().st_size,
             'template_sha256':sha(out/'observer.bin'),'states':changes,'runtime_status':'NOT RUN',
             'output_relative':'mod/bin/dc1/ss-t2/ss-openable-drawer.bin',
             'modules_original_sha256':sha(v.modules),'modules_patched_sha256':sha(mod_registry),
             'modules_size_slot':size_slot,'modules_change':'one existing module size field only'}
    (out/'build.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'symbols.json').write_text(json.dumps({format(k,'016X'):val for k,val in db.items()},indent=2)+'\n')
    print(json.dumps(summary,indent=2))
