"""EA SHPS(.ssh) 이미지: 형식 1(4bpp)/2(8bpp)/5(32bpp), 팔레트 0x21(32비트, PS2 CSM 순서)"""
import struct
import numpy as np


def csm(idx):  # 8bpp 팔레트 순서 섞기(8~15 <-> 16~23 블록)
    return (idx & ~0x18) | ((idx & 8) << 1) | ((idx & 16) >> 1)


class Img:
    pass


def parse(d):
    assert d[:4] == b'SHPS'
    n, = struct.unpack_from('<I', d, 8)
    out = []
    for i in range(n):
        name = d[16 + i * 8:20 + i * 8]
        off, = struct.unpack_from('<I', d, 20 + i * 8)
        im = Img(); im.name = name; im.off = off
        im.type = d[off]; im.size = int.from_bytes(d[off + 1:off + 4], 'little')
        im.w, im.h = struct.unpack_from('<HH', d, off + 4)
        im.hdr = d[off:off + 16]
        px = off + 16
        if im.type == 2:
            im.idx = np.frombuffer(d, np.uint8, im.w * im.h, px).reshape(im.h, im.w).copy()
        elif im.type == 1:
            b = np.frombuffer(d, np.uint8, im.w * im.h // 2, px)
            a = np.zeros(im.w * im.h, np.uint8); a[0::2] = b & 15; a[1::2] = b >> 4
            im.idx = a.reshape(im.h, im.w)
        elif im.type == 5:
            im.rgba = np.frombuffer(d, np.uint8, im.w * im.h * 4, px).reshape(im.h, im.w, 4).copy()
        po = off + im.size if im.size else None
        im.pal = None; im.palhdr = None; im.palpos = po
        if po and im.type in (1, 2) and d[po] == 0x21:
            pw, ph = struct.unpack_from('<HH', d, po + 4)
            im.palhdr = d[po:po + 16]
            p = np.frombuffer(d, np.uint8, pw * ph * 4, po + 16).reshape(-1, 4).copy()
            if im.type == 2 and len(p) == 256:
                p = p[[csm(i) for i in range(256)]]
            im.pal = p
        out.append(im)
    return out


def to_rgba(im):
    if im.type == 5: return im.rgba.copy()
    return im.pal[im.idx]


def write(d, im, new):
    """new: 같은 크기의 idx(8/4bpp) 또는 rgba(32bpp) 배열, 팔레트 im.pal 사용"""
    d = bytearray(d); px = im.off + 16
    if im.type == 2:
        d[px:px + im.w * im.h] = new.astype(np.uint8).tobytes()
    elif im.type == 1:
        f = new.reshape(-1).astype(np.uint8); d[px:px + len(f) // 2] = (f[0::2] | (f[1::2] << 4)).tobytes()
    elif im.type == 5:
        d[px:px + im.w * im.h * 4] = new.astype(np.uint8).tobytes()
    if im.pal is not None:
        p = im.pal
        if im.type == 2 and len(p) == 256:
            q = np.zeros_like(p)
            for i in range(256): q[csm(i)] = p[i]
            p = q
        d[im.palpos + 16:im.palpos + 16 + p.size] = p.astype(np.uint8).tobytes()
    return bytes(d)
