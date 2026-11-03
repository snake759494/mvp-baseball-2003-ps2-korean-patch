"""선수 이름 한글화

DB(DATA/DATABASE.BIG)의 이름은 1바이트 ASCII이고, 게임은 0x5007d8(char* -> UTF-16 복사)과
포맷터 0x500f30의 %s 경로로 넓은 문자열을 만든다. 이 두 곳을 고쳐 2바이트 한글을 해석하게 한다.
  한글 음절 c: i = c - 0xAC00 -> 앞 바이트 0x80 + (i >> 7), 뒤 바이트 0x80 + (i & 0x7f)
  복원: 앞*128 + 뒤 + 0x6B80
이름표: translation/names.txt (영문|한글, 성과 이름을 따로 등록)
"""
import os, re, struct

VA, OFF = 0x100000, 0x1000   # SLUS_206.50 .text 적재 주소와 파일 오프셋
R = dict(zero=0, v0=2, v1=3, a0=4, a1=5, a2=6, a3=7, s1=17, s2=18, s4=20, s5=21, sp=29, ra=31)


def _r(op, rs, rt, rd, sa, fn): return (op << 26) | (R[rs] << 21) | (R[rt] << 16) | (R[rd] << 11) | (sa << 6) | fn
def _i(op, rs, rt, im): return (op << 26) | (R[rs] << 21) | (R[rt] << 16) | (im & 0xffff)
def _b(op, rs, rt, pc, tgt): return _i(op, rs, rt, (tgt - pc - 4) >> 2)


def elf_patch(elf):
    e = bytearray(elf)
    def put(addr, words):
        for k, w in enumerate(words): struct.pack_into('<I', e, addr - VA + OFF + 4 * k, w)
    # 0x5007d8: v0 = 쓰기 위치, v1 = 문자, a2/a3 임시 (16칸, 원래 함수 + 뒤 nop 자리)
    A = 0x5007d8; L = A + 4; ST = A + 0x2c; END = A + 0x38
    put(A, [
        _r(0, 'a0', 'zero', 'v0', 0, 0x21),          # move v0,a0
        _i(0x24, 'a1', 'v1', 0),                     # L: lbu v1,0(a1)
        _b(4, 'v1', 'zero', A + 8, END),             # beqz v1,END
        _i(9, 'a1', 'a1', 1),                        # addiu a1,a1,1
        _i(0x0b, 'v1', 'a2', 0x80),                  # sltiu a2,v1,0x80
        _b(5, 'a2', 'zero', A + 0x14, ST),           # bnez a2,ST
        _i(0x24, 'a1', 'a3', 0),                     # lbu a3,0(a1)
        _i(9, 'a1', 'a1', 1),                        # addiu a1,a1,1
        _r(0, 'zero', 'v1', 'v1', 7, 0),             # sll v1,v1,7
        _r(0, 'v1', 'a3', 'v1', 0, 0x21),            # addu v1,v1,a3
        _i(9, 'v1', 'v1', 0x6b80),                   # addiu v1,v1,0x6b80
        _i(0x29, 'v0', 'v1', 0),                     # ST: sh v1,0(v0)
        _b(4, 'zero', 'zero', A + 0x30, L),          # b L
        _i(9, 'v0', 'v0', 2),                        # addiu v0,v0,2
        _r(0, 'ra', 'zero', 'zero', 0, 8),           # END: jr ra
        _i(0x29, 'v0', 'zero', 0),                   # sh zero,0(v0)
    ])
    # 포맷터 %s(char*): 위 함수를 불러 복사하고 길이(s5)·쓰기 위치(0x60(sp))를 갱신
    B = 0x5013d0
    put(B, [
        _r(0, 'v1', 'zero', 'a1', 0, 0x21),          # move a1,v1
        (3 << 26) | (A >> 2),                        # jal 0x5007d8
        _i(0x23, 'sp', 'a0', 0x60),                  # lw a0,0x60(sp)
        _r(0, 'v0', 'a0', 'v1', 0, 0x23),            # subu v1,v0,a0
        _r(0, 'zero', 'v1', 'v1', 1, 3),             # sra v1,v1,1
        _r(0, 's5', 'v1', 's5', 0, 0x21),            # addu s5,s5,v1
        _i(0x2b, 'sp', 'v0', 0x60),                  # sw v0,0x60(sp)
        _i(9, 's2', 'a1', 2),                        # addiu a1,s2,2
        _b(4, 'zero', 'zero', B + 0x20, 0x501490),   # b 0x501490
        _i(0x25, 's2', 's1', 0),                     # lhu s1,0(s2)
    ] + [0] * 4)
    # 0x2ffa90: 이름 머리글자("T. Glaus")는 이름을 1바이트에서 자른다. 한글이면 2바이트에서 자르게 한다.
    C = 0x2ffa90
    put(C, [
        _i(0x20, 'sp', 'v1', 0x80),                  # lb v1,0x80(sp)
        _b(4, 'v1', 'zero', C + 4, 0x2ffae0),        # beqz v1,0x2ffae0 (이름 없음: 성만 변환)
        _i(9, 'sp', 'a1', 0x60),                     # addiu a1,sp,0x60
        _b(4, 's4', 'zero', C + 0xc, 0x2ffab4),      # beqz s4,0x2ffab4 (약칭 안 함)
        _i(0x0a, 'v1', 'v1', 0),                     # slti v1,v1,0 (한글 앞 바이트면 1)
        _r(0, 'v1', 'sp', 'v1', 0, 0x21),            # addu v1,v1,sp
        _i(0x28, 'v1', 'zero', 0x81),                # sb zero,0x81(v1)
        0, 0,
    ])
    return bytes(e)


def enc(s):
    """한글 음절 -> 2바이트, 나머지는 latin1 그대로"""
    out = bytearray()
    for c in s:
        o = ord(c)
        if 0xac00 <= o <= 0xd7a3:
            i = o - 0xac00; out += bytes((0x80 + (i >> 7), 0x80 + (i & 0x7f)))
        else:
            out += c.encode('latin1')
    return bytes(out)


def load(path):
    tb = {}
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('#'): continue
        k, v = line.split('|', 1); tb[k] = v
    return tb


KOREAN = {('Chan Ho', 'Park'): '박찬호', ('Byung-Hyun', 'Kim'): '김병현', ('Sun-Woo', 'Kim'): '김선우',
          ('Hee Seop', 'Choi'): '최희섭', ('Jung', 'Bong'): '봉중근'}


def convert_dat(dat, tb, miss):
    """first_name/last_name 필드(0 , 1 )를 바꾼다"""
    t = dat.decode('latin1')
    if not t.startswith('0 first_name,1 last_name,'): return dat
    def rep(m):
        a, b = m.group(1), m.group(2)
        if (a, b) in KOREAN:   # 한국 선수: 이치로처럼 이름 칸을 비우고 성 칸에 성명 전체 ("찬. 박" 방지)
            return ',0 ,1 %s,' % enc(KOREAN[a, b]).decode('latin1')
        for x in (a, b):
            if x not in tb: miss.add(x)
        return ',0 %s,1 %s,' % (enc(tb.get(a, a)).decode('latin1'), enc(tb.get(b, b)).decode('latin1'))
    return re.sub(r',0 ([^,;\r\n]*),1 ([^,;\r\n]*),', rep, t).encode('latin1')


def convert_csv(dat, tb, miss):
    """ROOKIE.BIG names.csv (first_name,last_name,use fullname flag): 신인·드래프트 생성용 이름 풀"""
    lines = dat.decode('latin1').split(CRLF)
    for i, l in enumerate(lines[1:], 1):
        p = l.split(',')
        if len(p) != 3: continue
        for k in (0, 1):
            if p[k] not in tb: miss.add(p[k])
            p[k] = enc(tb.get(p[k], p[k])).decode('latin1')
        lines[i] = ','.join(p)
    return CRLF.join(lines).encode('latin1')


CRLF = chr(13) + chr(10)
