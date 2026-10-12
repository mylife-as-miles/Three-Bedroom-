"""Exact byte-wise FNV-1a 64; do not lowercase or normalize game symbols."""
def fnv1a64(value):
    h=0xcbf29ce484222325
    for b in value.encode('utf-8') if isinstance(value,str) else value:
        h=((h^b)*0x100000001b3)&0xffffffffffffffff
    return h
