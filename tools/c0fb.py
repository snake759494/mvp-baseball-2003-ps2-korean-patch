"""EA C0FB 묶음(3바이트 오프셋/크기, 빅엔디언) 읽기/쓰기

헤더: C0FB, u16 (헤더 길이 - 4), u16 개수, [u24 오프셋, u24 크기, 이름\0]...
데이터는 4바이트 정렬.
"""


def read(b):
    assert b[:2] == b'\xc0\xfb'
    n = int.from_bytes(b[4:6], 'big')
    p = 6; ents = []
    for _ in range(n):
        o = int.from_bytes(b[p:p+3], 'big'); s = int.from_bytes(b[p+3:p+6], 'big'); p += 6
        e = b.index(b'\0', p); ents.append((b[p:e].decode('latin1'), o, s)); p = e + 1
    return ents


def files(b):
    return [(n, b[o:o+s]) for n, o, s in read(b)]


def write(ents):
    hl = 6 + sum(6 + len(n) + 1 for n, _ in ents)
    pos = (hl + 3) & ~3
    out = bytearray(b'\xc0\xfb') + (hl - 4).to_bytes(2, 'big') + len(ents).to_bytes(2, 'big')
    data = bytearray()
    for n, d in ents:
        out += pos.to_bytes(3, 'big') + len(d).to_bytes(3, 'big') + n.encode('latin1') + b'\0'
        data += d; pos += len(d)
        while pos % 4: data += b'\0'; pos += 1
    out += bytes(((hl + 3) & ~3) - hl)
    return bytes(out + data)
