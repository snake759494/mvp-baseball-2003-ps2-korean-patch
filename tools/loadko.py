"""로딩 화면(DATA/FRONTEND/LOADn.BIG, 1024x512 8bpp SSH) 한글화

영문 글자 영역을 지우고(inpaint) 한글을 그린 뒤 256색으로 다시 양자화한다.
글자 표기: [노랑] <빨강> {초록} 강조, \\n 줄바꿈
"""
import os, re
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import c0fb, refpack, ssh

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FONT = os.path.join(ROOT, 'NanumSquareNeo-eHv.ttf')
FONT_B = os.path.join(ROOT, 'NanumSquareNeo-dEb.ttf')
WHITE = (238, 238, 238); YEL = (236, 196, 52); RED = (230, 40, 40); GRN = (90, 220, 90); DARK = (24, 24, 24)
HL = {'[': YEL, '<': RED, '{': GRN}

# 블록: (지울 영역 x0,y0,x1,y1, 글자, 종류, 최대 크기, 정렬)
#  종류 L: 밝은 글자(흰/노랑, 그림자), Y: 노란 제목/안내, D: 은색 띠 위 어두운 글자
TITLE = (270, 36, 900, 74)
LOADING = (230, 448, 394, 478, '불러오는 중...', 'D', 22, 'l')
DYK = [(282, 68, 650, 150, '알고 계셨나요?', 'Y', 52, 'l')]
FOOT = lambda x0, x1: (x0, 366, x1, 428, '자세한 내용은 메인 메뉴의\n해럴드 레이놀즈의 MVP 팁을 참고하세요.', 'Y', 24, 'l')
FTIP = [(286, 80, 800, 122, '프랜차이즈 팁', 'Y', 40, 'l')]

SPEC = {
    1: [TITLE + ('타격 조작 - 조준', 'D', 32, 'l'),
        (205, 340, 266, 364, '조준', 'L', 20, 'c'), (325, 340, 398, 384, '번트\n(R3)', 'L', 20, 'c'),
        (452, 340, 528, 364, '스윙', 'L', 20, 'c'),
        (696, 126, 966, 168, '왼쪽 아날로그 스틱을 [위로 조준]\n하면 뜬공을 칩니다.', 'L', 20, 'l'),
        (696, 214, 966, 256, '[아래로 조준]하면\n땅볼을 칩니다.', 'L', 20, 'l'),
        (696, 305, 966, 366, '[왼쪽]이나 [오른쪽]으로 조준해\n공을 좌측·우측으로\n보냅니다.', 'L', 20, 'l')],
    2: [TITLE + ('수비 조작', 'D', 32, 'l'),
        (72, 174, 282, 199, '수비수 전환 (L1)', 'L', 20, 'c'), (355, 174, 492, 199, '중계 (R1)', 'L', 20, 'c'),
        (166, 375, 314, 400, '수비수 이동', 'L', 20, 'c'),
        (568, 90, 952, 130, '베이스로 송구하려면\n버튼을 [눌렀다 떼세요].', 'L', 20, 'l'),
        (684, 136, 736, 158, '2루', 'L', 18, 'c'), (606, 180, 652, 202, '3루', 'L', 18, 'c'),
        (761, 180, 806, 202, '1루', 'L', 18, 'c'), (672, 227, 746, 249, '홈', 'L', 18, 'c'),
        (566, 262, 846, 320, '버튼을 오래 누를수록\n더 세게 던집니다.', 'L', 20, 'l'),
        (566, 335, 846, 392, '<빨간> 구역에서 버튼을 떼면\n실책이 날 수 있습니다.', 'L', 20, 'l')],
    3: [TITLE + ('투구 조작', 'D', 32, 'l'),
        (348, 133, 502, 172, '수비 작전\n(R2)', 'L', 20, 'c'), (70, 174, 312, 199, '견제 / 피치아웃 (L1)', 'L', 20, 'c'),
        (204, 370, 260, 394, '조준', 'L', 20, 'c'), (362, 370, 498, 394, '구종', 'L', 20, 'c'),
        (718, 100, 960, 152, '왼쪽 아날로그 스틱으로\n투구 위치를 [조준]합니다.', 'L', 19, 'l'),
        (718, 175, 960, 212, '구종 버튼을\n[누르고 있으세요].', 'L', 19, 'l'),
        (718, 221, 960, 320, '게이지 꼭대기 근처에서\n버튼을 [떼면] 공의\n위력이 좋아집니다.', 'L', 19, 'l'),
        (718, 338, 960, 404, '{초록} 구역에서 버튼을\n[톡] 누르면 정확한\n공을 던집니다.', 'L', 19, 'l')],
    4: [TITLE + ('주루 - 도루와 진루', 'D', 32, 'l'),
        (156, 153, 306, 176, '리드 (L2)', 'L', 20, 'c'), (334, 153, 486, 176, '귀루 (R2)', 'L', 20, 'c'),
        (94, 175, 256, 215, '전체 진루\n도루 지시 (L1)', 'L', 20, 'c'), (358, 175, 554, 215, '전체 귀루\n도루 취소 (R1)', 'L', 20, 'c'),
        (466, 366, 534, 390, '슬라이딩', 'L', 18, 'c'), (86, 397, 256, 421, '베이스 선택', 'L', 20, 'c'),
        (350, 397, 546, 421, '주자 선택', 'L', 20, 'c'),
        (644, 208, 934, 267, '알맞은 버튼을 [눌러]\n주자를 고르세요.', 'L', 21, 'l'),
        (644, 273, 934, 332, '방향 버튼을 [밀어]\n갈 베이스를 고르세요.', 'L', 21, 'l'),
        (740, 333, 792, 354, '2루', 'L', 18, 'c'), (680, 366, 726, 389, '3루', 'L', 18, 'c'),
        (802, 366, 846, 389, '1루', 'L', 18, 'c'), (730, 398, 804, 420, '홈', 'L', 18, 'c')],
    5: DYK + [FOOT(96, 696), (96, 163, 694, 318, '타구 방향을 정하는 가장 큰 요소는\n타이밍이지만, 풀 스윙 컨트롤을\n쓰면 공이 들어온 곳으로\n쳐 보낼 수 있습니다.', 'L', 30, 'l')],
    6: DYK + [FOOT(96, 696), (96, 163, 604, 378, '게이지 꼭대기에서 투구\n버튼을 떼면 공의 위력이\n좋아집니다. 직구는\n더 빨라지고, 변화구는\n더 많이 휩니다.', 'L', 30, 'l')],
    7: DYK + [FOOT(288, 856), (400, 158, 916, 362, '투구할 때는 최대한\n정확하게 던지세요.\n\n타이밍이 어긋나면 타자가\n구종을 눈치채 치기 쉽습니다.', 'L', 30, 'l')],
    8: DYK + [FOOT(118, 684), (118, 173, 856, 318, '수비 송구 게이지는 송구의\n힘과 정확도를 함께 정합니다.\n\n빨간 구역에서 떼면 더 세게\n던지지만 실책이 날 수 있습니다.', 'L', 30, 'l')],
    9: DYK + [FOOT(96, 696), (96, 173, 786, 312, '공을 잡기 가장 좋은 위치로\n가도록 하세요.\n\n수비수가 다이빙도 하지만\n실책 위험이 훨씬 커집니다.', 'L', 30, 'l')],
    10: DYK + [FOOT(96, 696), (96, 163, 786, 368, 'CPU가 주자를 대신 움직이지만\n보수적으로 뜁니다.\n\n직접 조작해 한 베이스 더 가고,\n접전이면 슬라이딩 버튼을 쓰세요.', 'L', 30, 'l')],
    11: FTIP + [(458, 138, 898, 398, '팀 기세는 시뮬레이션\n경기 결과에 영향을 줍니다.\n\n중요도가 높은 경기를\n직접 해서 이겨 두면 시뮬\n전에 기세가 높아집니다.', 'L', 30, 'l')],
    12: FTIP + [(452, 136, 908, 394, '감독 평점은 팀 승률과\n팀 목표를 바탕으로\n매기는 등급입니다.\n\n좋은 등급을 받으면\n연간 예산이 늘어납니다.', 'L', 30, 'l')],
    13: FTIP + [(108, 176, 620, 348, '하루씩 시뮬레이션하는 중에도\n언제든 개입할 수 있습니다.\n\n직접 나서서 리드를 지키거나\n역전을 노리세요.', 'L', 30, 'l')],
    14: FTIP + [(428, 148, 932, 380, '홈 경기, 시즌 막판 경기,\n라이벌전은 경기 중요도가\n높습니다.\n\n이런 경기는 팀 기세에\n더 큰 영향을 줍니다.', 'L', 30, 'l')],
    15: [(280, 76, 502, 154, '구종', 'Y', 56, 'l'),
         (176, 168, 550, 424, '포심 패스트볼\n투심 패스트볼\n커트 패스트볼\n커브\n슬라이더\n체인지업\n싱커\n스플리터\n너클볼\n스크루볼', 'L', 22, 'l')],
}
# 구종 표 오른쪽 약어(게임 화면 표기와 같게)
ABBR15 = ['(포심)', '(투심)', '(커터)', '(커브)', '(슬라)', '(체인)', '(싱커)', '(스플)', '(너클)', '(스크)']


# 글자 뒤에 밝은 그림이 있는 곳: 이 영역에서는 아주 밝은(임계값 초과) 픽셀만 글자로 본다
STRICT = {6: [((488, 158, 670, 300), 236)]}


def erase(rgb, box, kind, strict=()):
    x0, y0, x1, y1 = box
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    m = np.zeros(g.shape, np.uint8)
    sub = g[y0:y1, x0:x1]
    if kind == 'D':   # 은색 띠: 행마다 좌우 바깥 색을 선형 보간해 채운다
        out = rgb.copy().astype(np.float32)
        a = out[y0:y1, x0 - 2].copy(); b = out[y0:y1, x1 + 2].copy()
        t = np.linspace(0, 1, x1 - x0)[None, :, None]
        out[y0:y1, x0:x1] = a[:, None] * (1 - t) + b[:, None] * t
        return out.clip(0, 255).astype(np.uint8)
    else:
        hsv = cv2.cvtColor(rgb[y0:y1, x0:x1], cv2.COLOR_RGB2HSV)
        mk = ((sub > 150) | ((hsv[..., 1] > 110) & (hsv[..., 2] > 140) & (hsv[..., 0] < 35))).astype(np.uint8); k = 4
    m[y0:y1, x0:x1] = mk
    for (a0, b0, a1, b1), thr in strict:   # 밝고, 오른쪽 아래 2~4픽셀에 검은 그림자가 있는 픽셀만
        dark = (g < 90).astype(np.uint8)
        sh = np.zeros_like(dark)
        for dy in range(2, 5):
            for dx in range(1, 5): sh[:-dy, :-dx] |= dark[dy:, dx:]
        t = ((g > 170) & (sh > 0)).astype(np.uint8)
        t = cv2.dilate(t, np.ones((3, 3), np.uint8))
        m[b0:b1, a0:a1] = (t[b0:b1, a0:a1] | dark[b0:b1, a0:a1] & cv2.dilate(t, np.ones((9, 9), np.uint8))[b0:b1, a0:a1])
    m = cv2.dilate(m, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
    return cv2.inpaint(rgb, m, 6, cv2.INPAINT_TELEA)


def runs(line, base):
    """강조 표기 -> [(글자, 색)]"""
    out = []; col = base
    for ch in line:
        if ch in HL: col = HL[ch]; continue
        if ch in ']>}': col = base; continue
        out.append((ch, col))
    return out


def draw(img, box, text, kind, maxpx, align, shear=0.18):
    x0, y0, x1, y1 = box
    lines = text.split('\n')
    base = {'L': WHITE, 'Y': YEL, 'D': DARK}[kind]
    plain = [re.sub(r'[\[\]<>{}]', '', l) for l in lines]
    px = maxpx
    while px > 10:
        f = ImageFont.truetype(FONT, px)
        lh = round(px * 1.18)
        gap = round(px * 0.45)
        w = max(f.getlength(l) for l in plain) + px * shear
        h = sum(gap if not l else lh for l in plain)
        if w <= x1 - x0 and h <= y1 - y0 + px * 0.2: break
        px -= 1
    out = img.convert('RGBA')
    y = y0 + max(0, (y1 - y0 - h) // 2)
    for l, pl in zip(lines, plain):
        if not l: y += gap; continue
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        shadow = Image.new('RGBA', img.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(shadow)
        lw = f.getlength(pl)
        x = x0 if align == 'l' else x0 + (x1 - x0 - lw) / 2
        for ch, col in runs(l, base):
            if kind != 'D': ds.text((x + 2, y + 2), ch, font=f, fill=(0, 0, 0, 200))
            d.text((x, y), ch, font=f, fill=col + (255,))
            x += f.getlength(ch)
        cy = y + px * 0.6   # 줄마다 가운데 높이를 축으로 기울임(원본 글꼴이 이탤릭)
        sh = lambda im: im.transform(im.size, Image.AFFINE, (1, shear, -shear * cy, 0, 1, 0), Image.BICUBIC)
        if kind != 'D':
            out = Image.alpha_composite(out, sh(shadow).filter(ImageFilter.GaussianBlur(1)))
        out = Image.alpha_composite(out, sh(layer))
        y += lh
    return out.convert('RGB'), f, lh, y0 + max(0, (y1 - y0 - h) // 2)


def convert(k, raw_big):
    name, dat = c0fb.files(raw_big)[0]
    u = refpack.unpack(dat); im = ssh.parse(u)[0]
    rgb = np.ascontiguousarray(ssh.to_rgba(im)[..., :3])
    blocks = SPEC[k] + [LOADING]
    for b in blocks: rgb = erase(rgb, b[:4], b[5], STRICT.get(k, ()))
    if k == 15: rgb = erase(rgb, (440, 168, 550, 424), 'L')
    img = Image.fromarray(rgb)
    for b in blocks:
        img, f, lh, ytop = draw(img, b[:4], b[4], b[5], b[6], b[7])
        if k == 15 and b[4].startswith('포심'):
            for i, a in enumerate(ABBR15):
                img, *_ = draw(img, (450, ytop + i * lh, 560, ytop + (i + 1) * lh), a, 'L', f.size, 'l')
    q = img.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[:768], np.uint8).reshape(-1, 3)
    p4 = np.zeros((256, 4), np.uint8); p4[:len(pal), :3] = pal; p4[:, 3] = 128
    im.pal = p4
    nu = ssh.write(u, im, np.array(q))
    return c0fb.write([(name, refpack.compress(nu))]), img


# 부팅 라이선스 화면(SUSHARED.BIG의 license.ssh): 진회색 글자
LICENSE = [
    (108, 96, 610, 210, '메이저리그 베이스볼의 상표와 저작권은\nMajor League Baseball Properties, Inc.의\n허락을 받아 사용합니다. 메이저리그\n베이스볼 공식 웹사이트 MLB.com을\n방문해 보세요.', 26),
    (104, 280, 640, 356, '© MLBPA. 메이저리그 선수 협회 공식 라이선스.\n플레이어스 초이스 웹사이트\nwww.bigleaguers.com을 방문해 보세요.', 26),
    (108, 424, 640, 450, '팀 로스터 기준일: 2003년 1월 23일', 26),
]
GRAY = (40, 40, 40)


def license(raw_big):
    ents = c0fb.files(raw_big)
    out = []
    for name, dat in ents:
        if name != 'license.ssh': out.append((name, dat)); continue
        u = refpack.unpack(dat); im = ssh.parse(u)[0]
        rgb = np.ascontiguousarray(ssh.to_rgba(im)[..., :3])
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        m = np.zeros(g.shape, np.uint8)
        for x0, y0, x1, y1, *_ in LICENSE:
            m[y0:y1, x0:x1] = (g[y0:y1, x0:x1] < 110)
        m = cv2.dilate(m, np.ones((5, 5), np.uint8))
        rgb = cv2.inpaint(rgb, m, 6, cv2.INPAINT_TELEA)
        img = Image.fromarray(rgb)
        for x0, y0, x1, y1, t, px in LICENSE:
            img, *_ = draw(img, (x0, y0, x1, y1), t, 'D', px, 'l', 0.0)
        q = img.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pal = np.array(q.getpalette()[:768], np.uint8).reshape(-1, 3)
        p4 = np.zeros((256, 4), np.uint8); p4[:len(pal), :3] = pal; p4[:, 3] = 128
        im.pal = p4
        out.append((name, refpack.compress(ssh.write(u, im, np.array(q)))))
        prev = img
    return c0fb.write(out), prev
