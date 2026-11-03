"""EA LOC(LOCH/LOCI/LOCL) 문자열 표: UTF-16LE"""
import struct

def read(d):
    assert d[:4] == b'LOCH'
    i = 0x14; assert d[i:i+4] == b'LOCI'
    isz, icnt = struct.unpack_from('<II', d, i+4)
    head = d[:0x14]; loci = d[i:i+isz] if False else None
    L = d.index(b'LOCL')
    hdr = d[0x14:L]
    n = struct.unpack_from('<I', d, L+0xc)[0]
    offs = struct.unpack_from('<%dI' % n, d, L+0x10)
    out = []
    for o in offs:
        p = L + o; e = p
        while d[e:e+2] != b'\0\0': e += 2
        out.append(d[p:e].decode('utf-16-le'))
    return d[:L], d[L:L+0x10], out

def write(pre, lhdr, strs):
    n = len(strs)
    body = bytearray(); offs = []
    base = 0x10 + 4 * n
    for s in strs:
        offs.append(base + len(body)); body += s.encode('utf-16-le') + b'\0\0'
    while len(body) % 4: body += b'\0'
    l = bytearray(lhdr)
    struct.pack_into('<I', l, 4, 0x10 + 4*n + len(body))
    return bytes(pre) + bytes(l) + struct.pack('<%dI' % n, *offs) + bytes(body)


def ids(d):
    """LOCI: [u32 0][(u16 id, u16 index) x n]"""
    n = struct.unpack_from('<I', d, 0x1c)[0]
    return {struct.unpack_from('<H', d, 0x24 + 4*i)[0]: struct.unpack_from('<H', d, 0x26 + 4*i)[0] for i in range(n)}


def add(pre, strs, extra):
    """새 (id, 문자열) 추가: LOCI 표(ID 오름차순)와 LOCH의 LOCL 오프셋 갱신"""
    m = ids(pre)
    for i, s in extra:
        assert i not in m and i < 0x10000
        m[i] = len(strs); strs.append(s)
    pairs = sorted(m.items())
    loci = b'LOCI' + struct.pack('<III', 0x10 + 4 * len(pairs), len(pairs), 0) + b''.join(struct.pack('<HH', a, b) for a, b in pairs)
    head = bytearray(pre[:0x14]); struct.pack_into('<I', head, 0x10, 0x14 + len(loci))
    return bytes(head) + loci
