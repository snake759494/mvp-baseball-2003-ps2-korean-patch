"""MVP 베이스볼 2003 (북미판) 한글 패치 빌드

python tools/build.py  ->  'MVP Baseball 2003 (Korean).iso' (원본과 같은 폴더)
번역: translation/ko*.txt  (색인|번역, 없는 색인은 원문 유지, \n = 줄바꿈). 원문 목록은 work/en_loc.txt
"""
import os, sys, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loc, kfont, isobuild, isofs, c0fb, refpack

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
P = lambda *a: os.path.join(ROOT, *a)
SRC = P('MVP Baseball 2003 (USA).iso')
LITE = bool(os.environ.get('LITE'))   # 저메모리판: 실행 파일 무수정, 선수 이름 영문, 폰트 텍스처 축소
DST = P('MVP Baseball 2003 (Korean Lite).iso' if LITE else 'MVP Baseball 2003 (Korean).iso')
FONTS = list(kfont.CFG)
# 공유 문자열을 따로 번역해야 하는 곳: 게임이 쓰지 않는 시험용 문자열(색인 3, 2185~2189)의 ID를 빌려 쓴다
# (새 ID를 LOCI에 추가하면 화면에 나오지 않음)  {색인: (ID, 번역)}
REUSE = {3: (11, '좌'), 2185: (14982, '좌중'), 2187: (14984, '중'), 2188: (14985, '우중'), 2189: (14986, '우')}
# (FEL 파일, 요소 이름[@원래 ID]) -> id(바꿀 ID), dx(가로 이동), w(폭 증감)
FEL_EDIT = {
    ('fes_stadium.fel', 'LF'): dict(id=11, dx=-6), ('fes_stadium.fel', 'LC'): dict(id=14982, dx=-14, w=12),
    ('fes_stadium.fel', 'C'): dict(id=14984, dx=-6), ('fes_stadium.fel', 'RC'): dict(id=14985, dx=-14, w=12),
    ('fes_stadium.fel', 'RF'): dict(id=14986, dx=-6),
    # 경기 중 주자 표시: 2B/3B가 기록용 '2루타/3루타'를 써서 '2루/3루'로
    ('fes_ingameoverlay.fel', 'B2'): dict(id=3703), ('fes_ingameoverlay.fel', 'B3'): dict(id=3704),
    # 경기 결과 창 승·패·세: 한글 이름(키가 큼)이 아래 성적 줄과 겹쳐 이름은 위로, 성적 줄은 아래로 (dy: 세로 이동)
    ('fes_ingameendofgamemenu.fel', 'NAME'): dict(dy=-3),
    # 감독 평점 자리표시가 수비 기록 A(보살, 색인 716)를 같이 써서 '보살'로 보여, 번역하지 않은 'A'(색인 368, ID 3030)로
    **{(f_, n): dict(id=3030) for f_, ns in (('fes_fsplash_b.fel', ('MGRRATINGVAL', 'MGRRATINGVAL1')), ('fes_fteamgoals.fel', ('MGRRATINGVAL1', 'MGRRATINGVAL2'))) for n in ns},
    # 프랜차이즈 구단 운영 메뉴 '팀 목표' 그림자: 폭 115 가운데 정렬이라 '목표'가 오른쪽에 따로 찍혀, 본문(TB)과 같은 폭·왼쪽 정렬로 (al: 정렬)
    ('fes_fmanagerdecision.fel', 'TX1@6880'): dict(w=54, al=0),
    **{('fes_ingameendofgamemenu.fel', n): dict(dy=4) for n in ('STATS', 'STAT1', 'STAT', 'DASH', 'PARA1', 'PARA2')},
}
# 목록 항목(TE:ID) 바꾸기: 자유계약·드래프트 포지션 필터의 2B/3B가 기록용 '2루타/3루타'(8202/8203)를 써서 '2루/3루'(3703/3704)로
# 박스 스코어: 숫자 칸(폭 23)이 좁아 한글 머리글(타수·득점·안타…)이 붙어 보여, 이름 칸(210)을 150으로 줄이고
# 숫자 칸을 폭 31, 간격 38로 다시 배치한다. 메뉴 화면 두 벌과 경기 중 화면(이름 칸 x 55·63)  {원래 x: 새 x}
_bx = [0, 39, 71, 103, 135, 175, 207, 239]
BOX_X = {}
for _b in (279, 266):
    for _k, _o in enumerate(_bx): BOX_X[_b + _o] = _b - 46 + 38 * _k
# 투수 소개 창(STATS5: 승·패·세이브·삼진·ERA): 44px 간격이라 '세이브삼진'이 붙어 보여 52px 간격으로  {원래 x: 새 x}
OV_X = {139 + 44 * k: 139 + 52 * k for k in range(5)}
FEL_TE = {'fes_fdraftplayer.fel': {'8202': '3703', '8203': '3704'}}
# 라인 스코어 R/H/E 머리글은 영문 유지(칸이 좁음). 기록표·박스 스코어는 statids.py가 화면별 문자열로 바꾼다
# INGAME.BIG은 크기가 크게 늘면 경기 로딩이 멈출 수 있어 숫자만 바꾸는 최소 수정만 한다


def reader():
    f = open(SRC, 'rb'); ents = {e[0]: e for e in isofs.walk(f)}
    def get(n):
        _, lba, size, _ = ents[n]; f.seek(lba * 2048); return f.read(size)
    return get


def fmt(t):
    num = sorted(re.findall(r'%%?\d', t))   # %1~%9 는 순서 바꿔도 됨
    pf = re.findall(r'%[-+ #0]*\d*(?:\.\d+)?[hl]*[diouxXeEfgGcsp]', re.sub(r'%%?\d', '', t))
    return num, pf


def load_tr():
    """translation/ko*.txt: 색인|번역 (\\n = 줄바꿈)"""
    import glob
    tr = {}
    for fn in sorted(glob.glob(P('translation', 'ko*.txt'))):
        for line in open(fn, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line or line.startswith('#'): continue
            k, t = line.split('|', 1)
            assert int(k) not in tr, k
            tr[int(k)] = t.replace('\\n', '\n')
    return tr


def main():
    get = reader(); out = {}; errs = 0
    d = get('DATA/ENGLISH.LOC')
    pre, lh, strs = loc.read(d); en_strs = list(strs)
    tr = load_tr()
    for i, ko in tr.items():
        en = strs[i]
        if fmt(en) != fmt(ko):
            print(f'  [서식 불일치] {i}: {en!r} -> {ko!r}'); errs += 1
        strs[i] = ko
    for i, (_, t) in REUSE.items(): strs[i] = t
    import names
    nchars = ''.join(names.load(P('translation', 'names.txt')).values())
    ko = lambda ss: {c for s in ss for c in s if ord(c) >= 0xac00 or 0x3131 <= ord(c) <= 0x318e or c in '·→↔…'}
    chars = sorted(ko(strs + [nchars]))   # UI 문자열 + 선수 이름
    chars_ui = sorted(ko(strs))
    if LITE: chars = chars_ui; kfont.MAXW, kfont.MAXH = 512, int(os.environ.get('LITE_H', 256))
    if os.environ.get('TINY'): chars = chars_ui = sorted(set(os.environ['TINY']))   # AU20B(기울임 제목·메뉴체)는 선수 이름을 쓰지 않아 UI 글자만
    print(f'번역 {len(tr)}/{len(strs)}, 한글 {len(chars)}자')
    out['DATA/ENGLISH.LOC'] = loc.write(pre, lh, strs)
    # 화면 레이아웃(FEL): 공유 문자열 분리(새 ID), 위치 보정
    for big in ('FE_FRONTEND', 'FE_INGAME'):
        fn = f'DATA/FRONTEND/{big[3:]}.BIG'
        ents = c0fb.files(get(fn)); changed = False
        for k, (nm, dat) in enumerate(ents):
            eds = {e: v for (f_, e), v in FEL_EDIT.items() if f_ == nm}
            te = FEL_TE.get(nm, {})
            box = nm in ('fes_boxscores.fel', 'fes_ingameboxscore.fel')
            if not eds and not te and not box: continue
            lines = refpack.unpack(dat).decode('latin1').split('\r\n')
            bd = (0, 0)
            for li, l in enumerate(lines):
                s = l.lstrip(' ')
                if s[:3] == 'TE:' and s[3:] in te:
                    lines[li] = l[:len(l) - len(s)] + 'TE:' + te[s[3:]]; continue
                if s[:3] not in ('TX:', 'TB:', 'GR:'): continue
                p = s[3:].split(',')
                if nm == 'fes_ingameoverlay.fel' and s[:3] == 'TX:' and p[4] in ('374', '390') and p[5] == '46' and int(p[3]) in OV_X:
                    p[3] = str(OV_X[int(p[3])]); lines[li] = l[:len(l) - len(s)] + s[:3] + ','.join(p); continue
                if nm == 'fes_ingameoverlay.fel' and s.startswith('GR:STATS5,'):
                    p[5] = str(int(p[5]) + 32); lines[li] = l[:len(l) - len(s)] + s[:3] + ','.join(p); continue
                if box and p[0][:1] == 'X' and s[:3] == 'GR:':
                    x, w = int(p[3]), int(p[5])   # 칸(GR)을 옮기고, 바로 안의 글자(TB)도 같은 만큼 옮긴다
                    bd = (0, -60) if w == 210 else (BOX_X[x] - x, max(w, 31) - w) if x in BOX_X else (0, 0)
                if box and p[0][:1] == 'X' and s[:3] == 'GR:' or box and s[:3] == 'TB:' and p[0] in ('NAME', 'NUM'):
                    p[3] = str(int(p[3]) + bd[0]); p[5] = str(int(p[5]) + bd[1])
                    lines[li] = l[:len(l) - len(s)] + s[:3] + ','.join(p); continue
                fi = [i for i, x in enumerate(p) if x.endswith('.sfn')]
                v = (fi and eds.get(f'{p[0]}@{p[fi[0] + 1]}')) or eds.get(p[0])
                if not v: continue
                if 'id' in v: p[fi[0] + 1] = str(v['id'])
                if 'dy' in v: p[4] = str(int(p[4]) + v['dy'])
                if 'dx' in v: p[3] = str(int(p[3]) + v['dx'])
                if 'w' in v: p[5] = str(int(p[5]) + v['w'])
                if 'al' in v: p[fi[0] + 2] = str(v['al'])
                lines[li] = l[:len(l) - len(s)] + s[:3] + ','.join(p)
            ents[k] = (nm, refpack.compress('\r\n'.join(lines).encode('latin1'))); changed = True
        if changed: out[fn] = c0fb.write(ents)
    # 폰트: 낱개 SFN과 FONTS.BIG 양쪽
    os.makedirs(P('work', 'preview'), exist_ok=True)
    from PIL import Image
    newf = {}
    for n in FONTS:
        b, img = kfont.build(n, get('DATA/FONTS/' + n), chars)
        newf[n.lower()] = b; out['DATA/FONTS/' + n] = b
        Image.fromarray(img * 17).save(P('work', 'preview', n + '.png'))
        print(f'  {n}: 텍스처 {img.shape[1]}x{img.shape[0]}, 한글 {kfont.INFO[n][0]}->{kfont.INFO[n][1]}px')
    fb = get('DATA/FONTS/FONTS.BIG')
    n = struct.unpack('>I', fb[8:12])[0]; p = 16; ents = []
    for _ in range(n):
        o, s = struct.unpack('>II', fb[p:p + 8]); p += 8; e = fb.index(b'\0', p)
        nm = fb[p:e].decode(); p = e + 1; ents.append((nm, fb[o:o + s]))
    ents = [(nm, refpack.compress(newf[nm.lower()]) if nm.lower() in newf else dat) for nm, dat in ents]
    hl = 16 + sum(8 + len(nm) + 1 for nm, _ in ents) - 1
    hdr = (hl + 4) & ~3
    body = bytearray(); h = bytearray(b'BIGF') + struct.pack('>III', 0, len(ents), hl)
    pos = hdr
    for nm, dat in ents:
        h += struct.pack('>II', pos, len(dat)) + nm.encode() + b'\0'; body += dat; pos += len(dat)
    h += bytes(hdr - len(h)); fbn = h + body; struct.pack_into('>I', fbn, 4, len(fbn))
    out['DATA/FONTS/FONTS.BIG'] = bytes(fbn)
    # 로딩 화면(조작법·팁 그림) 15장
    import loadko
    for k in range(1, 16):
        out[f'DATA/FRONTEND/LOAD{k}.BIG'], img = loadko.convert(k, get(f'DATA/FRONTEND/LOAD{k}.BIG'))
        img.save(P('work', 'preview', f'LOAD{k}.png'))
    out['DATA/FRONTEND/SUSHARED.BIG'], img = loadko.license(get('DATA/FRONTEND/SUSHARED.BIG'))
    img.save(P('work', 'preview', 'LICENSE.png'))
    # 선수 이름: ELF에 2바이트 한글 해석 패치 + DATABASE.BIG 이름 변환
    if LITE:
        isobuild.build(SRC, DST, out); print('완료:', DST); return
    import fontmem, statids
    out['SLUS_206.50'] = statids.elf_patch(fontmem.elf_patch(names.elf_patch(get('SLUS_206.50'))))
    tb = names.load(P('translation', 'names.txt')); miss = set()
    ents = [(nm, refpack.compress(names.convert_dat(refpack.unpack(dat), tb, miss)))
            for nm, dat in c0fb.files(get('DATA/DATABASE.BIG'))]
    # 팀 별칭(순위표·박스 스코어 등): LOC 별칭 번역(색인 287~316)으로 team.dat의 2번 필드를 바꾼다
    teams = {en_strs[i]: strs[i] for i in range(287, 317)}
    ents = [(nm, refpack.compress(re.sub(r',2 ([^,]*),', lambda m: ',2 %s,' % names.enc(teams.get(m.group(1), m.group(1))).decode('latin1'),
                                         refpack.unpack(dat).decode('latin1')).encode('latin1')) if nm == 'team.dat' else dat) for nm, dat in ents]
    out['DATA/DATABASE.BIG'] = c0fb.write(ents)
    ents = [(nm, names.convert_csv(dat, tb, miss) if nm == 'names.csv' else dat)
            for nm, dat in c0fb.files(get('DATA/ROOKIE.BIG'))]
    out['DATA/ROOKIE.BIG'] = c0fb.write(ents)
    print(f'이름표 {len(tb)}개, 미번역 {len(miss)}개')
    if errs: print(f'오류 {errs}건')
    isobuild.build(SRC, DST, out)
    print('완료:', DST)


if __name__ == '__main__':
    main()
