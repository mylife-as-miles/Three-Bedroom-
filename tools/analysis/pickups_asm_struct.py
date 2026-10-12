"""pickups: generic parser for dconstruct .asm data dumps (nested struct/array/map blocks) -> python objects.
Library + CLI:  python3 -I tools/analysis/pickups_asm_struct.py <file.bin.asm> [entry-symbol]  (prints JSON)"""
import re, sys, json
HDR = re.compile(r'^\s*(?:\[(0x[0-9A-Fa-f]+|\d+)\]\s+)?(?:(sid|int|float|string|bool|u8|u16|u32|u64|i8|i16|i64|f32|symbol):\s*(.*)|([A-Za-z0-9_*?-]+(?: struct)?|array|map)\s*\[0x[0-9A-Fa-f]+\]\s*(\{size: \d+\})?\s*\{)\s*$')
ENTRY = re.compile(r'^(\*?[A-Za-z0-9_?*-]+\*?) = (.*?)\s*\[0x[0-9A-Fa-f]+\]\s*\{\s*$')

def _val(t, v):
    if t == 'int':
        try: return int(v)
        except ValueError: return v
    if t == 'float':
        try: return float(v)
        except ValueError: return v
    if t == 'string': return v.strip('"')
    return v

def parse_block(lines, i):
    """lines[i-1] opened a block; returns (obj, next_index). obj = {'_type':..., fields...} or list."""
    fields = {}
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s == '}':
            return fields, i + 1
        m = HDR.match(ln)
        if m:
            key, t, v, typ = m.group(1), m.group(2), m.group(3), m.group(4)
            if t:
                fields[key or f'_{len(fields)}'] = _val(t, v)
                i += 1; continue
            sub, i = parse_block(lines, i + 1)
            sub['_type'] = typ
            fields[key or f'_{len(fields)}'] = sub
            continue
        m2 = re.match(r'^\s*keys: \[0x[0-9A-F]+\], values: \[0x[0-9A-F]+\]', ln)
        if m2: i += 1; continue
        m3 = re.match(r'^\s*(keys|values) array \[0x[0-9a-fA-F]+\] \{size: \d+\} \{', ln)
        if m3:
            sub, i = parse_block(lines, i + 1)
            fields[m3.group(1)] = sub
            continue
        i += 1
    return fields, i

def parse_file(path):
    lines = open(path, errors='replace').read().splitlines()
    out, i = {}, 0
    while i < len(lines):
        m = ENTRY.match(lines[i])
        if m:
            obj, i = parse_block(lines, i + 1)
            obj['_type'] = m.group(2)
            out[m.group(1)] = obj
        else:
            i += 1
    return out

def map_items(m):
    """turn a parsed map into list of (key, value)"""
    ks = [m['keys'][k] for k in sorted(m['keys'], key=lambda x: int(x, 0)) if not k.startswith('_type')] if 'keys' in m else []
    vs = [m['values'][k] for k in sorted(m['values'], key=lambda x: int(x, 0)) if not k.startswith('_type')] if 'values' in m else []
    return list(zip(ks, vs))

if __name__ == '__main__':
    d = parse_file(sys.argv[1])
    if len(sys.argv) > 2: d = d[sys.argv[2]]
    print(json.dumps(d, indent=1)[:200000])
