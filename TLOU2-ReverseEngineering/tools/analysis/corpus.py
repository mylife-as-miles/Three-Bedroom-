#!/usr/bin/env python3
"""Read-only DC00 structural indexer and conservative bytecode constant propagation.
No game source reconstruction is published. Raw strings and instruction listings are private.
See tools/analysis/FORMAT_NOTES.md for boundaries and upstream format references.
"""
import argparse, collections, hashlib, json, re, struct, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sid'))
from fnv import fnv1a64
ID_RE=re.compile(r'^[A-Za-z_*][A-Za-z0-9_*/?.:!+<>=$%-]{0,240}$')
TOKEN_RE=re.compile(r'[A-Za-z][A-Za-z0-9_/?*.-]{2,100}')
FLAGS=struct.pack('<Q',0xDEADBEEF1337F00D)
BLOCKS=['start','end','event','update','virtual']
UNKNOWN=('unknown',)

def dump(p,data):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def load_seed(path):
 b=path.read_bytes();n=struct.unpack_from('<Q',b)[0];db={};invalid=0
 for i in range(n):
  h,o=struct.unpack_from('<QQ',b,8+i*16)
  if not 8+n*16<=o<len(b): invalid+=1;continue
  s=b[o:b.index(0,o)].decode('utf-8',errors='replace'); db[h]=s
 return db,{'entries':n,'valid':len(db),'invalid_offsets':invalid,'sha256':hashlib.sha256(b).hexdigest()}

class DC:
 def __init__(self,path,rel,db):
  self.b=path.read_bytes(); self.path=rel;self.db=db
  magic,version,self.text,self.strings,_,count=struct.unpack_from('<6I',self.b)
  assert magic==0x44433030 and version==1
  assert 32<=self.strings<=self.text<len(self.b)
  size=self.u32(self.text);self.reloc=self.b[self.text+4:self.text+4+size]
  assert len(self.reloc)==size
  self.entries=[];p=self.q(24)
  self.check(p,count*24)
  for i in range(count):
   h,t,o=struct.unpack_from('<QQQ',self.b,p+i*24)
   self.entries.append({'sid':f'{h:016X}','name':self.name(h),'type':self.name(t),'offset':o})
 def check(self,p,n):
  if not 0<=p<=len(self.b)-n:raise ValueError(f'Invalid range {p:x}+{n:x}')
 def q(self,p):self.check(p,8);return struct.unpack_from('<Q',self.b,p)[0]
 def u32(self,p):self.check(p,4);return struct.unpack_from('<I',self.b,p)[0]
 def short(self,p):self.check(p,2);return struct.unpack_from('<h',self.b,p)[0]
 def ptr(self,p):
  return p%8==0 and p//64<len(self.reloc) and bool(self.reloc[p//64]&(1<<((p//8)%8)))
 def name(self,h):return self.db.get(h,f'#{h:016X}')
 def string(self,p):
  self.check(p,1);end=self.b.find(b'\0',p,self.text)
  return self.b[p:end if end>=0 else self.text].decode('utf-8',errors='replace')
 def value(self,p,kind=None):
  v=self.q(p)
  if kind=='global-ref':return ('global-ref',self.name(v))
  if self.ptr(p):
   if self.strings<=v<self.text:return ('string',self.string(v))
   return ('pointer',v)
  if kind=='float':return ('float',round(struct.unpack_from('<f',self.b,p)[0],7))
  if kind and kind.startswith('i'):return ('int',struct.unpack_from('<'+{'i8':'b','i16':'h','i32':'i','i64':'q'}[kind],self.b,p)[0])
  if kind and kind.startswith('u'):return ('int',struct.unpack_from('<'+{'u8':'B','u16':'H','u32':'I','u64':'Q'}[kind],self.b,p)[0])
  return ('sid',self.name(v))
 def decl_value(self,typ,p):
  if typ in ('vector','point','quat'):
   self.check(p,16);return (typ,[round(x,7) for x in struct.unpack_from('<4f',self.b,p)])
  if typ in ('float','int32','uint64','boolean','symbol'):
   return self.value(p,{'float':'float','int32':'i32','uint64':'u64','boolean':'u8','symbol':'sid'}[typ])
  if typ=='string' and self.ptr(p) and self.q(p):return ('string',self.string(self.q(p)))
  return ('opaque-declaration',typ,p)
 def states(self):
  scripts=[];contexts={}
  for entry in self.entries:
   if entry['type']!='state-script':continue
   p=entry['offset'];self.check(p,80)
   name=self.name(self.q(p)); initial=self.name(self.q(p+16));n=self.short(p+48); table=self.q(p+40)
   assert 0<=n<10000;self.check(table,n*24)
   ss={'id':self.path+'::'+name,'file':self.path,'name':name,'offset':p,'initial_state':initial,'debug_file':self.string(self.q(p+56)) if self.q(p+56) else None,'declarations':[],'states':[]}
   decl=self.q(p+8)
   if decl:
    dn=self.u32(decl+4);dt=self.q(decl+8);self.check(dt,dn*48)
    for j in range(dn):
     d=dt+j*48;typ=self.name(self.q(d+16));value=self.q(d+32)
     ss['declarations'].append({'name':self.name(self.q(d)),'type':typ,'offset':d,'value_offset':value,'is_variable':self.short(d+26)!=0,'variable_size_offset':self.short(d+24),'value':self.decl_value(typ,value) if value else None})
   for i in range(n):
    s=table+i*24;state=self.name(self.q(s));bn=self.q(s+8);bt=self.q(s+16);assert bn<10000;self.check(bt,bn*80)
    st={'name':state,'offset':s,'blocks':[]}
    for j in range(bn):
     b=bt+j*80;kind=self.u32(b);ev=self.name(self.q(b+8)) if kind==2 else None;tn=self.short(b+34);tt=self.q(b+40);assert 0<=tn<10000;self.check(tt,tn*24)
     block={'kind':BLOCKS[kind] if kind<len(BLOCKS) else str(kind),'event':ev,'offset':b,'tracks':[]}
     for k in range(tn):
      t=tt+k*24;track=self.name(self.q(t));ln=self.short(t+10);lt=self.q(t+16);assert 0<=ln<10000;self.check(lt,ln*16)
      offsets=[self.q(lt+x*16) for x in range(ln)]
      block['tracks'].append({'name':track,'offset':t,'lambdas':offsets})
      for index,o in enumerate(offsets):contexts.setdefault(o,[]).append({'script':name,'state':state,'block':block['kind'],'event':ev,'track':track,'index':index})
     # Include condition/event lambdas and the rare track-group lambda if present.
     for slot,label in [(b+16,'block-condition'),(b+72,'track-group')]:
      if self.ptr(slot) and self.q(slot):contexts.setdefault(self.q(slot),[]).append({'script':name,'state':state,'block':block['kind'],'event':ev,'track':label,'index':0})
     st['blocks'].append(block)
    ss['states'].append(st)
   scripts.append(ss)
  return scripts,contexts
 def lambdas(self,contexts):
  names={e['offset']:e['name'] for e in self.entries if e['type']=='script-lambda'}
  positions=set(contexts)|set(names); cursor=0
  while True:
   flag=self.b.find(FLAGS,cursor,self.strings)
   if flag<0:break
   if flag%8==0:positions.add(flag-40)
   cursor=flag+8
  result=[];errors=[]
  for p in sorted(positions):
   try:
    self.check(p,80);ip=self.q(p);sp=self.q(p+8);n=self.u32(p+52)
    assert self.q(p+40)==0xDEADBEEF1337F00D and 0<n<65536
    assert self.ptr(p) and self.ptr(p+8)
    self.check(ip,n*8)
    instructions=[tuple(self.b[ip+i*8:ip+i*8+4]) for i in range(n)]
    symmax=max([a for op,d,a,c in instructions if op in STATIC_OPS]+[-1]);self.check(sp,(symmax+1)*8)
    fn={'id':self.path+f'@{p:X}','file':self.path,'name':names.get(p,self.name(self.q(p+32)) if self.q(p+32) else f'lambda@{p:X}'),'offset':p,'instruction_offset':ip,'instruction_count':n,'symbol_table_offset':sp,'contexts':contexts.get(p,[]),'symbols':[]}
    used=collections.defaultdict(set)
    for op,d,a,c in instructions:
     if op in STATIC_OPS:used[a].add(STATIC_OPS[op])
    for a,kinds in used.items():fn['symbols'].append({'index':a,'offset':sp+a*8,'value':self.value(sp+a*8,next(iter(kinds)) if len(kinds)==1 else None)})
    calls,raw=self.calls(fn,instructions,sp)
    result.append((fn,calls,raw))
   except Exception as exc:errors.append({'file':self.path,'offset':p,'error':str(exc) or type(exc).__name__})
  return result,errors
 def calls(self,fn,ins,sp):
  # Forward dataflow: joins retain a constant only if identical on every incoming path.
  # Results are identities, not presumed values; no native effects are evaluated.
  n=len(ins);incoming={0:{r:('argument',r-49) for r in range(49,98)}};todo=collections.deque([0]);calls={};iterations=0
  while todo:
   i=todo.popleft();iterations+=1
   if iterations>n*100:raise ValueError('dataflow iteration limit')
   regs=incoming[i].copy();op,d,a,c=ins[i];target=d+(c<<8)
   if op in STATIC_OPS:regs[d]=self.value(sp+a*8,STATIC_OPS[op])
   elif op==12:regs[d]=('int',a+(c<<8))
   elif op in (22,23,24,67):regs[d]=regs.get(a,UNKNOWN)
   elif op in (27,28):
    callee=regs.get(a,UNKNOWN)
    if callee[0]=='global-ref':callee=('sid',callee[1])
    args=[regs.get(49+j,UNKNOWN) for j in range(c)]
    calls[i]={'id':fn['id']+f':{i}','caller':fn['id'],'file':self.path,'instruction_index':i,'offset':fn['instruction_offset']+i*8,'opcode':'Call' if op==27 else 'CallFf','target':callee,'arguments':args,'contexts':fn['contexts'],'confidence':'CONFIRMED' if callee[0]=='sid' and not re.fullmatch(r'#[0-9A-Fa-f]{16}',callee[1]) else 'UNKNOWN / NEEDS NATIVE RESEARCH'}
    # ABI argument registers are scratch; prevent reuse across calls.
    for r in range(49,98):regs.pop(r,None)
    regs[d]=('result',fn['id']+f':{i}')
   elif op in (0,45,46,47,44,43,16,17,18,82,83,84,85,86,87,88,89,92,94,95):pass
   else:regs.pop(d,None)
   if op==0:successors=[]
   elif op==45:successors=[target]
   elif op in (46,47):successors=[i+1,target]
   else:successors=[i+1]
   for nxt in successors:
    if nxt==n:continue
    if not 0<=nxt<n:raise ValueError(f'branch out of range {nxt}')
    if nxt not in incoming:incoming[nxt]=regs.copy();todo.append(nxt)
    else:
     old=incoming[nxt];merged={r:v for r,v in old.items() if regs.get(r,UNKNOWN)==v}
     if merged!=old:incoming[nxt]=merged;todo.append(nxt)
  raw=[]
  for i,(op,d,a,c) in enumerate(ins):
   row={'index':i,'offset':fn['instruction_offset']+i*8,'opcode':OP_NAMES[op] if op<len(OP_NAMES) else str(op),'dst':d,'a':a,'b':c}
   if op in STATIC_OPS:row['value']=self.value(sp+a*8,STATIC_OPS[op])
   if i in calls:row['call']=calls[i]
   if op in (45,46,47):row['branch_target']=d+(c<<8)
   raw.append(row)
  return [calls[i] for i in sorted(calls)],raw

STATIC_OPS={9:'i32',10:'float',11:'pointer',19:'global-ref',20:'global-ref',21:'global-ref',63:'i32',64:'float',65:'pointer',68:'u32',69:'i8',70:'u8',71:'i16',72:'u16',73:'i64',74:'sid'}
OP_NAMES='Return IAdd ISub IMul IDiv FAdd FSub FMul FDiv LoadStaticInt LoadStaticFloat LoadStaticPointer LoadU16Imm LoadU32 LoadFloat LoadPointer StoreInt StoreFloat StorePointer LookupInt LookupFloat LookupPointer MoveInt MoveFloat MovePointer CastInteger CastFloat Call CallFf IEqual IGreaterThan IGreaterThanEqual ILessThan ILessThanEqual FEqual FGreaterThan FGreaterThanEqual FLessThan FLessThanEqual IMod FMod IAbs FAbs GoTo Label Branch BranchIf BranchIfNot OpLogNot OpBitAnd OpBitNot OpBitOr OpBitXor OpBitNor OpLogAnd OpLogOr INeg FNeg LoadParamCnt IAddImm ISubImm IMulImm IDivImm LoadStaticI32Imm LoadStaticFloatImm LoadStaticPointerImm IntAsh Move LoadStaticU32Imm LoadStaticI8Imm LoadStaticU8Imm LoadStaticI16Imm LoadStaticU16Imm LoadStaticI64Imm LoadStaticU64Imm LoadI8 LoadU8 LoadI16 LoadU16 LoadI32 LoadI64 LoadU64 StoreI8 StoreU8 StoreI16 StoreU16 StoreI32 StoreU32 StoreI64 StoreU64 INotEqual FNotEqual StoreArray AssertPointer BreakFlag Breakpoint QEX_InRangeI'.split()

def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,default=Path('.'));v=a.parse_args();root=v.root.resolve();private=root/'.private';output=root/'databases';start=time.time()
 db,seed=load_seed(private/'vendor/dconstruct/test/fixtures/dc/sidbase_new_fixed.bin');print('Loaded seed',seed,flush=True)
 paths=sorted((private/'extracted').rglob('*.bin'));readable=collections.defaultdict(set);candidates=collections.defaultdict(set);rawfile=private/'raw_strings.jsonl'
 with rawfile.open('w') as f:
  for p in paths:
   b=p.read_bytes();rel=p.relative_to(private/'extracted').as_posix()
   if b[:4]!=b'00CD':continue
   text,strings=struct.unpack_from('<II',b,8)
   for chunk in b[strings:text].split(b'\0'):
    if not chunk:continue
    try:s=chunk.decode('utf-8')
    except UnicodeDecodeError:continue
    h=fnv1a64(chunk);readable[h].add(rel)
    # Exact game strings always override imported labels, because the source is known.
    if h not in db:db[h]=s
    f.write(json.dumps({'sid':f'{h:016X}','string':s,'file':rel},ensure_ascii=False)+'\n')
    # Debug strings expose state/track names; derived tokens are candidates until a binary match.
    for token in TOKEN_RE.findall(s):
     h=fnv1a64(token)
     if h not in db:db[h]=token
     candidates[h].add(rel)
   for symbol in (p.stem,rel,rel.removeprefix('dc1/').removesuffix('.bin')):
    h=fnv1a64(symbol)
    if h not in db:db[h]=symbol
    candidates[h].add(rel)
 print('Hashed readable strings',len(readable),'token candidates',len(candidates),flush=True)
 dump(private/'sid_dictionary.json',{f'{h:016X}':s for h,s in db.items()})
 scripts=[];functions=[];calls=[];entries=[];errors=[];siduses=collections.defaultdict(lambda:collections.Counter());parsed=0
 with (private/'bytecode.jsonl').open('w') as raw:
  for p in paths:
   rel=p.relative_to(private/'extracted').as_posix()
   try:
    dc=DC(p,rel,db);parsed+=1
    # Aligned word hits are references, not function calls or proven typed SIDs.
    for offset,(h,) in enumerate(struct.iter_unpack('<Q',dc.b[:dc.strings-(dc.strings%8)])):
     if not dc.ptr(offset*8) and h in db:siduses[h][rel]+=1
    entries.extend(dict(e,file=rel) for e in dc.entries)
    ss,ctx=dc.states();scripts.extend(ss);fns,err=dc.lambdas(ctx);errors.extend(err)
    for fn,cs,listing in fns:
     functions.append(fn);calls.extend(cs);raw.write(json.dumps({'function':fn['id'],'instructions':listing})+'\n')
   except Exception as exc:errors.append({'file':rel,'error':str(exc) or type(exc).__name__})
   if parsed%500==0:print('Indexed',parsed,'files;',len(scripts),'state scripts;',len(calls),'calls',flush=True)
 definitions=collections.defaultdict(list)
 for fn in functions:
  if not fn['name'].startswith('lambda@') and not fn['name'].startswith('#'):definitions[fn['name']].append(fn['id'])
 for c in calls:
  target=c['target'];c['definitions']=definitions.get(target[1],[]) if target[0]=='sid' else []
  c['target_kind']='script-definition' if c['definitions'] else 'unresolved-symbol-or-native' if target[0]=='sid' else 'dynamic-or-unresolved'
 events=[];transitions=[]
 for ss in scripts:
  for st in ss['states']:
   for block in st['blocks']:
    if block['kind']=='event':events.append({'kind':'listener','event':block['event'],'file':ss['file'],'script':ss['name'],'state':st['name'],'offset':block['offset'],'confidence':'CONFIRMED'})
 for c in calls:
  if c['target'][0]!='sid':continue
  name=c['target'][1]
  if re.search(r'(send|broadcast|listen|post|wait).*event',name):events.append({'kind':'call','function':name,'arguments':c['arguments'],'call_id':c['id'],'file':c['file'],'contexts':c['contexts'],'confidence':'CONFIRMED'})
  if name in ('goto','go','go-to','ss-goto','set-state','state-script-goto','goto-state') or re.search(r'(^|-)goto($|-)',name):transitions.append({'call_id':c['id'],'function':name,'arguments':c['arguments'],'contexts':c['contexts'],'file':c['file'],'confidence':'CONFIRMED','note':'Static call; branch and runtime reachability still require trace.'})
 public_sids=[]
 for h,uses in sorted(siduses.items()):
  s=db[h]
  if not ID_RE.fullmatch(s):continue
  public_sids.append({'sid':f'{h:016X}','string':s,'source_files':sorted(uses),'type':'aligned-word-reference','usage_count':sum(uses.values()),'uses_by_file':dict(uses),'resolution':'game-readable-fnv' if h in readable else 'derived-token-fnv' if h in candidates else 'imported-sidbase','hash_verified':fnv1a64(s)==h})
 dump(output/'sid_database.json',public_sids);dump(output/'functions.json',functions);dump(output/'state_scripts.json',scripts);dump(output/'calls.json',calls);dump(output/'events.json',events);dump(output/'entries.json',entries);dump(output/'call_graph.json',{'calls':'calls.json','state_scripts':'state_scripts.json','transitions':transitions,'edges': [{'source':c['caller'],'target':d,'kind':'static-call','call_id':c['id']} for c in calls for d in c['definitions']]});dump(output/'parse_errors.json',errors)
 coverage={'input_bin_files':len(paths),'parsed_dc_files':parsed,'state_scripts':len(scripts),'states':sum(len(s['states']) for s in scripts),'functions':len(functions),'calls':len(calls),'resolved_named_call_targets':sum(c['confidence']=='CONFIRMED' for c in calls),'errors':len(errors),'sid_symbols':len(public_sids),'readable_string_hashes':len(readable),'token_candidate_hashes':len(candidates),'seed':seed,'elapsed_seconds':round(time.time()-start,2),'limitations':['Static may-call graph; no runtime event delivery proof','Unknown memory loads, indirect calls, native effects and conditions','All strings and instruction listings kept private','Aligned SID matches are untyped until structural context confirms them']};dump(output/'coverage.json',coverage);print(json.dumps(coverage,indent=2),flush=True)
if __name__=='__main__':main()
