#!/usr/bin/env python3
"""Read-only DSAR/LZ4 and PSAR/zlib extractor. Never falls back on failed decoding.
Format reference: rm-NoobInCoding/UnPSARC (MIT), DirectStorage and Core.
"""
import argparse, hashlib, json, struct, zlib
from pathlib import Path, PurePosixPath
import lz4.block

def extract(src, dest):
    data=src.read_bytes()
    if data[:4]==b'DSAR':
        n=struct.unpack_from('<I',data,8)[0]
        assert 32+n*32<=len(data)
        chunks=[]
        for i in range(n):
            off,coff,usize,csize,kind=struct.unpack_from('<QQIIB',data,32+i*32)
            assert off==sum(map(len,chunks)), (i,'noncontiguous block')
            assert coff+csize<=len(data)
            raw=data[coff:coff+csize]
            if csize==0: raw=bytes(usize)
            elif kind==0: pass
            elif kind==3: raw=lz4.block.decompress(raw,uncompressed_size=usize)
            else: raise ValueError(f'Unsupported DSAR compression {kind}')
            assert len(raw)==usize
            chunks.append(raw)
        data=b''.join(chunks)
    assert data[:4]==b'PSAR', data[:32]
    _,version,compression,tocsize,entrysize,count,blocksize,flags=struct.unpack_from('>4sI4sIIIII',data)
    assert entrysize==30
    assert compression==b'zlib', 'Oodle requires a decoder from the owned game'
    entries=[]
    for i in range(count):
        p=32+i*entrysize
        entries.append((data[p:p+16],int.from_bytes(data[p+16:p+20],'big'),int.from_bytes(data[p+20:p+25],'big'),int.from_bytes(data[p+25:p+30],'big')))
    width=((blocksize-1).bit_length()+7)//8
    sizes=[int.from_bytes(data[p:p+width],'big') for p in range(32+entrysize*count,tocsize,width)]
    def payload(entry):
        _,idx,length,offset=entry
        pieces=[]
        while length:
            n=min(length,blocksize); c=sizes[idx] or blocksize; idx+=1
            raw=data[offset:offset+c]; offset+=c
            if c!=n:
                raw=zlib.decompress(raw)
            assert len(raw)==n, (len(raw),n)
            pieces.append(raw); length-=n
        return b''.join(pieces)
    names=payload(entries[0]).decode('utf-8').replace('\0','\n').splitlines()
    lookup={hashlib.md5(s.encode()).digest():s for name in names for s in (name,name.lower(),name.upper())}
    manifest=[]
    for i,e in enumerate(entries[1:],1):
        name=lookup[e[0]].lstrip('/')
        p=PurePosixPath(name)
        assert not p.is_absolute() and '..' not in p.parts
        raw=payload(e); out=dest/name; out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(raw)
        manifest.append({'path':name,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'archive_entry':i,'magic':raw[:4].hex()})
    return {'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'psar_version':version,'compression':compression.decode(),'entry_count':count,'files':manifest}
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('archive',type=Path);a.add_argument('output',type=Path);a.add_argument('--manifest',type=Path,required=True);v=a.parse_args()
    result=extract(v.archive,v.output); v.manifest.write_text(json.dumps(result,indent=2)+'\n');print(f"Extracted {len(result['files'])} files")
