#!/usr/bin/env python3
"""Tests of static preservation and diagnostic bytecode gating with mocked getters.
No test executes TLOU2 or validates native APIs, animations, or inventory behavior.
"""
import argparse, json, struct, sys, tempfile, unittest
from pathlib import Path
from build import ROOT, DEFAULT_ACTOR
from validate_experiment import analyze
from corpus import DC
from fnv import fnv1a64
BUILD=ROOT/'.private/experiments/drawer-diagnostics/build'
ORIGINAL=ROOT/'.private/extracted/dc1/ss-t2/ss-openable-drawer.bin'
MODULES=ROOT/'.private/extracted/dc1/modules.bin'
PATCHED=BUILD/'mod/bin/dc1/ss-t2/ss-openable-drawer.bin'
REGISTRY=BUILD/'mod/bin/dc1/modules.bin'

def number(name):
    if name.startswith('#'):return int(name[1:],16)
    return fnv1a64(name)

def prefix(raw,actor,pressed,flags):
    """Execute ONLY selector/toggle prefix with mocked engine calls; stop at sampling."""
    regs={};calls=[];ip=0
    for _ in range(300):
        r=raw[ip];op=r['opcode'];d,a,b=r['dst'],r['a'],r['b'];nxt=ip+1
        if op=='LookupPointer':regs[d]=r['value'][1]
        elif op=='LoadStaticU64Imm':regs[d]=number(r['value'][1])
        elif op=='LoadU16Imm':regs[d]=a+(b<<8)
        elif op in ('Move','MoveInt','MovePointer'):regs[d]=regs[a]
        elif op=='INotEqual':regs[d]=int(regs[a]!=regs[b])
        elif op=='OpLogNot':regs[d]=int(not regs[a])
        elif op=='BranchIfNot':
            if not regs[a]:nxt=r['branch_target']
        elif op=='Branch':nxt=r['branch_target']
        elif op=='Return':return 'disabled',calls
        elif op=='CallFf':
            target=regs[a];calls.append(target)
            if target=='get-symbol':return 'sampling',calls
            if target=='get-self-id':result=actor
            elif target=='keyboard-button-pressed?':result=int(pressed)
            elif target=='get-boolean':result=int(flags.get(regs[49],False))
            elif target=='set-boolean':flags[regs[49]]=bool(regs[50]);result=0
            else:raise AssertionError(f'Unexpected prefix native mock: {target}')
            regs[d]=result
        else:raise AssertionError(f'Unsupported diagnostic-prefix opcode {op}')
        ip=nxt
    raise AssertionError('Prefix did not terminate')

class StaticDiagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db={int(k,16):v for k,v in json.loads((BUILD/'symbols.json').read_text()).items()}
        cls.dc=DC(PATCHED,'drawer',cls.db);s,c=cls.dc.states();fs,err=cls.dc.lambdas(c);assert not err
        cls.observers=[raw for f,cs,raw in fs if any(x['track']=='drawer-diag-observer' for x in f['contexts'])]
        assert len(cls.observers)==11
    def validate(self,patched=PATCHED,registry=REGISTRY):
        with tempfile.TemporaryDirectory(dir=BUILD) as tmp:
            return analyze(ORIGINAL,patched,MODULES,registry,BUILD/'symbols.json',Path(tmp)/'report.json')
    def test_exact_static_preservation(self):
        result=self.validate();self.assertEqual(result['preserved_call_sites'],1159)
        self.assertEqual(result['preserved_lambda_count'],151)
    def test_other_actor_never_queries_input_or_data(self):
        for raw in self.observers:
            flags={};result,calls=prefix(raw,0,True,flags)
            self.assertEqual(result,'disabled');self.assertEqual(calls,['get-self-id']);self.assertEqual(flags,{})
    def test_target_defaults_disabled(self):
        for raw in self.observers:
            result,calls=prefix(raw,fnv1a64(json.loads((BUILD/'build.json').read_text())['actor']),False,{})
            self.assertEqual(result,'disabled');self.assertNotIn('get-symbol',calls)
    def test_toggle_latch_across_states(self):
        flags={};target=fnv1a64(json.loads((BUILD/'build.json').read_text())['actor'])
        result,_=prefix(self.observers[0],target,True,flags);self.assertEqual(result,'sampling')
        result,_=prefix(self.observers[1],target,True,flags);self.assertEqual(result,'sampling')
        result,_=prefix(self.observers[2],target,False,flags);self.assertEqual(result,'sampling')
        result,_=prefix(self.observers[3],target,True,flags);self.assertEqual(result,'disabled')
        self.assertFalse(flags[fnv1a64('drawer-diag-enabled')])
        self.assertEqual(set(flags),{fnv1a64('drawer-diag-enabled'),fnv1a64('drawer-diag-key-latch')})
    def test_validator_rejects_gameplay_instruction_corruption(self):
        dc=DC(ORIGINAL,'drawer',self.db);s,c=dc.states();fs,err=dc.lambdas(c)
        b=bytearray(PATCHED.read_bytes());b[fs[0][0]['instruction_offset']+4]^=1
        with tempfile.TemporaryDirectory(dir=BUILD) as tmp:
            path=Path(tmp)/'corrupt.bin';path.write_bytes(b)
            with self.assertRaises(AssertionError):self.validate(patched=path)
    def test_validator_rejects_unrelated_registry_change(self):
        b=bytearray(REGISTRY.read_bytes());b[-1]^=1
        with tempfile.TemporaryDirectory(dir=BUILD) as tmp:
            path=Path(tmp)/'corrupt-modules.bin';path.write_bytes(b)
            with self.assertRaises(AssertionError):self.validate(registry=path)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',type=Path,default=BUILD);parser.add_argument('--original',type=Path,default=ORIGINAL);parser.add_argument('--modules',type=Path,default=MODULES);args,remaining=parser.parse_known_args()
    BUILD,ORIGINAL,MODULES=args.build,args.original,args.modules
    PATCHED=BUILD/'mod/bin/dc1/ss-t2/ss-openable-drawer.bin';REGISTRY=BUILD/'mod/bin/dc1/modules.bin'
    unittest.main(argv=[sys.argv[0]]+remaining,verbosity=2)
