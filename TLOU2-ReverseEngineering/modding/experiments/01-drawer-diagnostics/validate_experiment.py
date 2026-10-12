#!/usr/bin/env python3
"""Exact static preservation checks on two files; this is not runtime testing."""
import argparse, collections, hashlib, json, struct, sys
from pathlib import Path
from build import ROOT, STATES, DIAG_VARS, dictionary, sha, DEFAULT_ACTOR
sys.path.insert(0,str(ROOT/'tools/analysis'))
from corpus import DC
from fnv import fnv1a64

def analyze(original, patched, modules, patched_modules, symbols, report):
    db={int(k,16):v for k,v in json.loads(symbols.read_text()).items()}
    # Original symbol metadata is optional; resolution affects names, never equivalence checks.
    db.update({fnv1a64(s):s for s in ['main','main-move-to','global','function','boolean','symbol','float','int32','uint64','bound-frame','timer','vector']})
    o=DC(original,'drawer',db);p=DC(patched,'drawer',db)
    os,oc=o.states();ps,pc=p.states();of,oe=o.lambdas(oc);pf,pe=p.lambdas(pc)
    assert not oe and not pe, (oe,pe)
    assert o.entries==p.entries, 'Exports/entry pointers changed'
    assert os[0]['initial_state']==ps[0]['initial_state']
    assert [s['name'] for s in os[0]['states']]==[s['name'] for s in ps[0]['states']]
    assert p.short(ps[0]['offset']+48)==o.short(os[0]['offset']+48)==11
    # Normalize only relocated string pointers, then restore precisely authorized header/state fields.
    prefix=bytearray(p.b[:o.strings]);changes=[]
    ranges=[(8,8,'DC header string/relocation offsets'),(os[0]['offset']+8,8,'declaration-list pointer')]
    for s in os[0]['states']:
        ranges.extend([(s['offset']+8,8,f"{s['name']}: block count"),
                       (s['offset']+16,8,f"{s['name']}: block table")])
    for at,n,label in ranges:
        if prefix[at:at+n]!=o.b[at:at+n]:
            changes.append({'offset':at,'length':n,'field':label,'before_hex':o.b[at:at+n].hex(),'after_hex':prefix[at:at+n].hex()})
        prefix[at:at+n]=o.b[at:at+n]
    moved_strings=0
    for at in range(0,o.strings,8):
        assert o.ptr(at)==p.ptr(at), f'Original relocation bit changed {at:x}'
        if o.ptr(at) and o.strings<=o.q(at)<o.text:
            assert p.q(at)==p.strings+o.q(at)-o.strings
            assert o.string(o.q(at))==p.string(p.q(at))
            prefix[at:at+8]=o.b[at:at+8];moved_strings+=1
    assert prefix==o.b[:o.strings], 'Original data changed outside explicit observer wiring'
    assert p.b[p.strings:p.strings+o.text-o.strings]==o.b[o.strings:o.text], 'Original strings changed'
    op=os[0]['offset'];pp=ps[0]['offset'];od=o.q(op+8);pd=p.q(pp+8)
    on=o.u32(od+4);pn=p.u32(pd+4);assert pn==on+2
    ot=o.q(od+8);pt=p.q(pd+8)
    for i in range(on):
        a,b=ot+48*i,pt+48*i
        assert o.b[a:a+48]==p.b[b:b+48], 'Original declaration moved with altered bytes'
    assert p.u32(pd)==o.u32(od)+2
    for i,name in enumerate(DIAG_VARS):
        a=pt+(on+i)*48
        assert p.q(a)==fnv1a64(name) and p.q(a+16)==fnv1a64('boolean')
        assert p.short(a+24)==o.u32(od)+i+1
        assert p.q(p.q(a+32))==0, 'Diagnostic default must be disabled'
    byoffset={f['offset']:(f,cs,raw) for f,cs,raw in pf};fn_evidence=[]
    for f,cs,raw in of:
        new,ncs,nraw=byoffset[f['offset']];ip=f['instruction_offset'];n=f['instruction_count']*8
        assert new['instruction_offset']==ip and new['instruction_count']==f['instruction_count']
        assert o.b[ip:ip+n]==p.b[ip:ip+n], 'Original instructions changed'
        assert cs==ncs, 'Original call/argument/context evidence changed'
        assert f['symbols']==new['symbols'], 'Original symbols changed semantically'
        fn_evidence.append({'offset':f['offset'],'instruction_offset':ip,'instruction_count':f['instruction_count'],
                            'before_instruction_sha256':hashlib.sha256(o.b[ip:ip+n]).hexdigest(),
                            'after_instruction_sha256':hashlib.sha256(p.b[ip:ip+n]).hexdigest(),
                            'call_count':len(cs)})
    oldcounters=[];newcounters=[];added_offsets=[]
    for old,new in zip(os[0]['states'],ps[0]['states']):
        oldblocks=old['blocks'];newblocks=new['blocks'];assert len(newblocks) in (len(oldblocks),len(oldblocks)+1)
        for i,block in enumerate(oldblocks):
            nb=newblocks[i];assert (block['kind'],block['event'])==(nb['kind'],nb['event'])
            if block['kind']!='update': assert block['tracks']==[dict(t,offset=block['tracks'][j]['offset']) for j,t in enumerate(nb['tracks'])]
            else: assert len(nb['tracks'])==len(block['tracks'])+1
            for tr,ntr in zip(block['tracks'],nb['tracks']):
                assert tr['name']==ntr['name'] and tr['lambdas']==ntr['lambdas']
                assert o.short(tr['offset']+8)==p.short(ntr['offset']+8)
                count=len(tr['lambdas']);a=o.q(tr['offset']+16);b=p.q(ntr['offset']+16)
                assert o.b[a:a+count*16]==p.b[b:b+count*16]
                oldcounters.extend(o.q(a+j*16+8) for j in range(count))
        additions=[tr for bl in newblocks for tr in bl['tracks'] if tr['name']=='drawer-diag-observer']
        assert len(additions)==1 and len(additions[0]['lambdas'])==1
        tr=additions[0];added_offsets+=tr['lambdas'];a=p.q(tr['offset']+16);newcounters.append(p.q(a+8))
    assert len(newcounters)==len(set(newcounters))==11 and min(newcounters)>max(oldcounters)
    allowed={'get-self-id','keyboard-button-pressed?','get-boolean','set-boolean','get-float','get-symbol',
             'entity-exists?','player-is-crouched?','get-animation-playing?','get-animation-phase','string-debug',
             'alloc-point','debug-draw-string-2d','dc:format','get-bound-frame','get-object-locator',
             'get-locator-distance-xz','angle-in-between-locators'}
    added_calls=[]
    for pos in added_offsets:
        f,cs,raw=byoffset[pos]
        for c in cs:
            assert c['target'][0]=='sid' and c['target'][1] in allowed, c
            if c['target'][1]=='set-boolean':
                assert c['arguments'][0][0]=='sid' and c['arguments'][0][1] in DIAG_VARS, c
            if c['target'][1]=='get-animation-phase':assert c['arguments'][0:2]==[('sid','player'),('int',2)]
            if c['target'][1]=='angle-in-between-locators':assert c['opcode']=='Call'
            else: assert c['opcode']=='CallFf'
            added_calls.append(c)
        # A mismatch takes an early Return before keyboard, getters, or renderer.
        assert raw[0]['opcode'] in ('LookupPointer',), raw[0]
        first_key=min(c['instruction_index'] for c in cs if c['target']==('sid','keyboard-button-pressed?'))
        assert raw[1]['call']['target']==('sid','get-self-id')
        assert raw[2]['opcode']=='LoadStaticU64Imm' and raw[3]['opcode']=='INotEqual'
        assert raw[4]['opcode']=='BranchIfNot' and raw[5]['opcode']=='Branch'
        assert raw[5]['branch_target']==len(raw)-1 and raw[-1]['opcode']=='Return'
        assert raw[4]['branch_target']<first_key
    m=DC(modules,'m',db);pm=DC(patched_modules,'pm',db)
    mp=m.entries[0]['offset'];mt=m.q(mp+8);matches=[mt+i*40 for i in range(m.q(mp)) if m.string(m.q(mt+i*40))=='ss-t2/ss-openable-drawer'];assert len(matches)==1
    slot=matches[0]+16;assert m.q(slot)==len(o.b) and pm.q(slot)==len(p.b)
    normalized=bytearray(pm.b);normalized[slot:slot+8]=m.b[slot:slot+8];assert normalized==m.b
    summary={'validation':'PASS','validation_kind':'STATIC ONLY','runtime_status':'NOT RUN',
             'original_sha256':sha(original),'patched_sha256':sha(patched),
             'original_bytes':len(o.b),'patched_bytes':len(p.b),
             'original_export_count':len(o.entries),'preserved_state_count':11,
             'original_declaration_count':on,'added_diagnostic_declarations':2,
             'preserved_lambda_count':len(of),'preserved_call_sites':sum(len(cs) for f,cs,raw in of),
             'added_observer_lambdas':len(added_offsets),'added_call_sites':len(added_calls),
             'added_call_counts':dict(sorted(collections.Counter(c['target'][1] for c in added_calls).items())),
             'new_scheduler_counters':newcounters,'original_string_pointer_relocations':moved_strings,
             'original_metadata_changes':changes,'modules_size_change':{'offset':slot,'before':len(o.b),'after':len(p.b)},
             'checks':['original instruction bytes unchanged','original call/argument/context evidence unchanged',
                       'original declarations and initial state unchanged','original block/track order, lambda IDs/counters retained',
                       'one appended update observer per state; unique new counters',
                       'added native/DC call allowlist verified; writes only two diagnostic booleans',
                       'original data unchanged outside enumerated metadata/string relocations',
                       'module registry changed only at target size field'],
             'limits':['native scheduling/input/render/ABI/save behavior untested','actor-to-script binding untested',
                       'observer may miss transient states within one frame','added observers impose some scheduling overhead'],
             'per_original_lambda':fn_evidence}
    report.write_text(json.dumps(summary,indent=2)+'\n');return summary

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--original',type=Path,required=True);a.add_argument('--modules',type=Path,required=True);a.add_argument('--build',type=Path,required=True);a.add_argument('--report',type=Path,required=True);v=a.parse_args()
    summary=analyze(v.original,v.build/'mod/bin/dc1/ss-t2/ss-openable-drawer.bin',v.modules,v.build/'mod/bin/dc1/modules.bin',v.build/'symbols.json',v.report)
    print(json.dumps({k:val for k,val in summary.items() if k not in ('per_original_lambda','original_metadata_changes')},indent=2))
