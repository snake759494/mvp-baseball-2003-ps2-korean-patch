"""MVP 2003 SFN(FNTS v0x16e)에 한글 글리프 추가 (코드 = 유니코드 그대로)

헤더 0x80: 0x0a 글리프 수, 0x14 글리프표, 0x18 커닝, 0x1c 텍스처, 0x40/0x44 = 1/폭, 1/높이(float)
글리프 12바이트 [code u16, w, h, u u16, v u16, adv s8, xoff s8, yoff s8, 0], 코드 오름차순(이진 탐색)
텍스처: 16바이트 셰이프 헤더(type|next24, w, h) + 4bpp + 뒤 팔레트 블록(그대로 둠)
"""
import os, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
NANUM = {w: os.path.join(ROOT, f'NanumSquareNeo-{w}.ttf') for w in ('aLt', 'bRg', 'cBd', 'dEb', 'eHv')}
# 원본 폰트별 (서체, 한글 높이 = 원본 대문자 높이 대비 배율, 기울임)
CFG = {
    'AU20B_EN.SFN': ('eHv', 1.0, 0.22),
    'FRK12_EN.SFN': ('cBd', 1.0, 0.0),
    'TWC14_EN.SFN': ('cBd', 0.85, 0.0),
    'TWCNB_EN.SFN': ('cBd', 0.85, 0.0),
    'TWC16_EN.SFN': ('eHv', 0.85, 0.0),   # 팝업 본문: 줄 간격이 좁아 한글을 조금 작게
    'TWC18_EN.SFN': ('eHv', 1.0, 0.0),
}


LINE = {}
MAXW, MAXH = 512, 512
INFO = {}


def pack_shelf(rend, ow, oh, W, H):
    """높이순 선반 채우기. 원본 글리프 블록(ow x oh) 오른쪽 빈 곳부터. 넘치면 None"""
    order = sorted(rend, key=lambda r: -r[1].shape[0])
    x, y, rh = ow + 1, 0, 0; place = []
    for code, g, xo, yo in order:
        h, w = g.shape
        if x + w > W:
            y += rh + 1; rh = 0; x = ow + 1 if y < oh + 1 else 0
        if y + h > H: return None
        if y < oh + 1 and y + h >= oh + 1 and x <= ow:   # 원본 블록과 겹침 방지
            return None
        place.append((code, x, y, g, xo, yo)); x += w + 1; rh = max(rh, h)
    return W, max(y + rh, oh), place


def parse(b):
    n = struct.unpack_from('<H', b, 0xa)[0]
    goff, koff, toff = struct.unpack_from('<III', b, 0x14)
    gl = [list(struct.unpack_from('<HBBHHbbbB', b, goff + 12 * i)) for i in range(n)]
    kern = b[goff + 12 * n:toff]
    typ = b[toff]; nx = int.from_bytes(b[toff + 1:toff + 4], 'little')
    w, h = struct.unpack_from('<HH', b, toff + 4)
    assert typ == 1 and nx == 16 + w * h // 2
    px = np.frombuffer(b, np.uint8, w * h // 2, toff + 16)
    img = np.zeros(w * h, np.uint8); img[0::2] = px & 15; img[1::2] = px >> 4
    return dict(hdr=b[:goff], gl=gl, kern=kern, koff=koff, goff=goff, thdr=b[toff:toff + 16],
                img=img.reshape(h, w), tail=b[toff + nx:])


def render(font, ch, px, shear):
    S = px * 3
    im = Image.new('L', (S, S), 0)
    ImageDraw.Draw(im).text((px // 2, px * 2), ch, font=font, fill=255, anchor='ls')
    if shear:
        im = im.transform(im.size, Image.AFFINE, (1, shear, -shear * px * 2, 0, 1, 0), Image.BICUBIC)
    return np.array(im), px // 2, px * 2


def build(name, raw, chars):
    f = parse(raw)
    w8, scale, shear = CFG[name]
    H = [g for g in f['gl'] if g[0] == ord('H')][0]
    cap, cap_top = H[2], H[7]
    target = round(cap * scale)
    px = 6
    while True:
        bb = ImageFont.truetype(NANUM[w8], px + 1).getbbox('한', anchor='ls')
        if bb[3] - bb[1] > target + 1: break
        px += 1
    px0 = px; hb0 = ImageFont.truetype(NANUM[w8], px0).getbbox('한', anchor='ls')
    oh, ow = f['img'].shape
    # 텍스처는 512x512(4bpp 128KB) 이하여야 한다. 게임의 VRAM 텍스처 캐시 칸이 512블록이라
    # 더 크면 다음 칸으로 넘쳐 선수 사진 등에 덮여 글자가 깨진다(시즌 대진 화면). 안 들어가면 한 단계씩 줄인다.
    while True:
        font = ImageFont.truetype(NANUM[w8], px)
        hb = font.getbbox('한', anchor='ls')
        rend = []
        for ch in chars:
            a, ox, by = render(font, ch, px, shear)
            ys, xs = np.nonzero(a)
            if len(xs) == 0: continue
            if ch in '·→↔…' and font.getbbox(ch)[2] == 0: continue
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            g = np.clip((a[y0:y1, x0:x1].astype(np.int32) * 15 + 127) // 255, 0, 15).astype(np.uint8)
            rend.append((ord(ch), g, x0 - ox, y0 - by))
        best = pack_shelf(rend, ow, oh, MAXW, MAXH)
        if best: break
        px -= 1
    # 한글 세로 위치: 대문자 윗선(cap_top)에 '한'의 윗선을 맞추고, 줄인 만큼은 가운데로
    ytop = cap_top - hb[1] + ((hb0[3] - hb0[1]) - (hb[3] - hb[1])) // 2
    INFO[name] = (px0, px)
    W, Ht, place = best
    Hp = (Ht + 3) & ~3
    img = np.zeros((Hp, W), np.uint8); img[:oh, :ow] = f['img']
    gl = [list(g) for g in f['gl']]
    sp = 1
    for code, gx, gy, g, xo, yo in place:
        h, w = g.shape
        img[gy:gy + h, gx:gx + w] = g
        xoff = max(0, xo)
        gl.append([code, w, h, gx, gy, w + xoff + sp - round(shear * cap * 1.1), xoff, ytop + yo, 0])
    gl.sort(key=lambda g: g[0])
    hdr = bytearray(f['hdr'])
    hdr[0x12] += LINE.get(name, 0)   # 줄 간격(상승값) 보정: 한글은 글자 칸을 꽉 채워 영문보다 줄이 붙어 보임
    f['hdr'] = bytes(hdr)
    return pack(f, gl, img), img


def pack(f, gl, img):
    H, W = img.shape
    hdr = bytearray(f['hdr'])
    gt = b''.join(struct.pack('<HBBHHbbbB', *g) for g in gl)
    koff = f['goff'] + len(gt)
    toff = koff + len(f['kern'])
    pad = (-toff) % 16
    flat = img.reshape(-1)
    px = (flat[0::2] | (flat[1::2] << 4)).astype(np.uint8).tobytes()
    th = bytearray(f['thdr']); th[1:4] = (16 + len(px)).to_bytes(3, 'little'); struct.pack_into('<HH', th, 4, W, H)
    body = hdr + gt + f['kern'] + bytes(pad) + th + px + f['tail']
    struct.pack_into('<H', body, 0xa, len(gl))
    struct.pack_into('<III', body, 0x14, f['goff'], koff if f['koff'] else 0, toff + pad)
    struct.pack_into('<ff', body, 0x40, 1.0 / W, 1.0 / H)
    struct.pack_into('<I', body, 4, len(body))
    return bytes(body)
