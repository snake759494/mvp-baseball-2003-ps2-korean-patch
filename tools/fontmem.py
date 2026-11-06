"""한글 폰트를 게임이 쓰지 않는 RAM(0x90000~0x100000)에 올리는 ELF 패치

한글 글리프로 폰트(FONTS.BIG)가 원본보다 수백 KB 커지면, 시즌 경기처럼 메모리를 많이 쓰는 곳에서
힙이 모자라 로딩 중 멈춘다. 폰트는 0x2128b0에서 0x21f750(경로, 0x400)으로 힙에 올라간다.
이를 0x21f838(경로, 버퍼, 최대 크기)로 바꿔 ELF 아래 빈 구간에 차례로 올리고(폰트 번호 s3별 주소 기억),
자리가 모자라면 원래처럼 힙에 올린다. 폰트를 내릴 때(0x21e340, 0x21e3c0)는 힙 블록 크기 조회·memset·free를
하므로, 이 구간 주소면 건너뛴다.
코드는 0x4e2ae0의 nop 1KB 구간(대기용 nop 256개)에 넣고, 대기는 짧은 반복문으로 대신한다.
"""
import struct

VA, OFF = 0x100000, 0x1000
R = dict(zero=0, at=1, v0=2, v1=3, a0=4, a1=5, a2=6, a3=7, t0=8, t1=9, t2=10, t3=11,
         s0=16, s1=17, s2=18, s3=19, sp=29, ra=31)
BASE, END = 0x90000, 0x100000
SLED, SLED_END = 0x4e2ae0, 0x4e2ee0
CODE = 0x4e2b00
DATA = 0x4e2e00                     # BUMP(다음 빈 주소), TABLE[32](폰트 번호별 주소)
LOAD_CALL = 0x21299c                # jal 0x21f750 (지연 슬롯: addiu a1,zero,0x400)
FREE1, FREE1_SKIP = 0x21e364, 0x21e388
FREE2, FREE2_SKIP = 0x21e400, 0x21e424


def i_(op, rs, rt, im): return (op << 26) | (R[rs] << 21) | (R[rt] << 16) | (im & 0xffff)
def r_(rs, rt, rd, sa, fn): return (R[rs] << 21) | (R[rt] << 16) | (R[rd] << 11) | (sa << 6) | fn
def j_(op, t): return (op << 26) | ((t >> 2) & 0x3ffffff)


class Asm:
    def __init__(self, org): self.org = org; self.w = []; self.lab = {}; self.fix = []
    @property
    def pc(self): return self.org + 4 * len(self.w)
    def L(self, n): self.lab[n] = self.pc
    def e(self, w): self.w.append(w)
    def br(self, op, rs, rt, lab): self.fix.append((len(self.w), lab)); self.e(i_(op, rs, rt, 0))
    def done(self):
        for k, lab in self.fix:
            off = (self.lab[lab] - (self.org + 4 * k) - 4) >> 2
            self.w[k] = (self.w[k] & 0xffff0000) | (off & 0xffff)
        return self.w


def code():
    hi, lo = DATA >> 16, DATA & 0xffff
    a = Asm(CODE)
    # --- FLOAD(a0 = 경로), s3 = 폰트 번호 ---
    a.L('fload')
    a.e(i_(9, 'sp', 'sp', -0x30))
    a.e(i_(0x3f, 'sp', 'ra', 0x20)); a.e(i_(0x3f, 'sp', 's0', 0x10)); a.e(i_(0x3f, 'sp', 's1', 0x18))
    a.e(r_('a0', 'zero', 's1', 0, 0x21))                       # move s1,a0
    a.e(i_(0xf, 'zero', 'at', hi)); a.e(r_('zero', 's3', 't0', 2, 0)); a.e(r_('t0', 'at', 't0', 0, 0x21))
    a.e(i_(0x23, 't0', 's0', lo + 4))                          # s0 = TABLE[s3]
    a.br(5, 's0', 'zero', 'have'); a.e(0)
    a.e(i_(0x23, 'at', 's0', lo))                              # s0 = BUMP
    a.L('have')
    a.e(r_('s1', 'zero', 'a0', 0, 0x21)); a.e(r_('s0', 'zero', 'a1', 0, 0x21))
    a.e(i_(0xf, 'zero', 'a2', END >> 16))
    a.e(j_(3, 0x21f838)); a.e(r_('a2', 's0', 'a2', 0, 0x23))  # 0x21f838(경로, s0, END - s0)
    a.e(i_(0xf, 'zero', 't1', END >> 16)); a.e(r_('t1', 's0', 't1', 0, 0x23))
    a.br(6, 'v0', 'zero', 'heap'); a.e(0)                      # blez v0 -> 실패
    a.e(r_('v0', 't1', 't2', 0, 0x2b)); a.br(4, 't2', 'zero', 'heap'); a.e(0)   # 넘침(잘림) -> 힙
    a.e(i_(0xf, 'zero', 'at', hi)); a.e(r_('zero', 's3', 't0', 2, 0)); a.e(r_('t0', 'at', 't0', 0, 0x21))
    a.e(i_(0x23, 't0', 't3', lo + 4)); a.br(5, 't3', 'zero', 'ok'); a.e(0)
    a.e(i_(0x2b, 't0', 's0', lo + 4))                          # TABLE[s3] = s0
    a.e(r_('s0', 'v0', 't3', 0, 0x21)); a.e(i_(9, 't3', 't3', 0x3ff))
    a.e(r_('zero', 't3', 't3', 10, 2)); a.e(r_('zero', 't3', 't3', 10, 0))
    a.e(i_(0x2b, 'at', 't3', lo))                              # BUMP = align(s0 + 크기, 0x400)
    a.L('ok')
    a.br(4, 'zero', 'zero', 'ret'); a.e(r_('s0', 'zero', 'v0', 0, 0x21))
    a.L('heap')
    a.e(r_('s1', 'zero', 'a0', 0, 0x21)); a.e(j_(3, 0x21f750)); a.e(i_(9, 'zero', 'a1', 0x400))
    a.L('ret')
    a.e(i_(0x37, 'sp', 'ra', 0x20)); a.e(i_(0x37, 'sp', 's0', 0x10)); a.e(i_(0x37, 'sp', 's1', 0x18))
    a.e(r_('ra', 'zero', 'zero', 0, 8)); a.e(i_(9, 'sp', 'sp', 0x30))
    # --- 해제 검사: a0 < 0x100000이면 크기 조회·memset·free를 건너뛰고 skip 주소로 ---
    for name, skip in (('chk1', FREE1_SKIP), ('chk2', FREE2_SKIP)):
        a.L(name)
        a.e(i_(0xf, 'zero', 'at', END >> 16)); a.e(r_('a0', 'at', 'at', 0, 0x2b))
        a.br(4, 'at', 'zero', name + 'h'); a.e(0)
        a.e(i_(0xf, 'zero', 'ra', (skip + 0x8000) >> 16)); a.e(i_(9, 'ra', 'ra', skip & 0xffff))
        a.e(r_('ra', 'zero', 'zero', 0, 8)); a.e(0)
        a.L(name + 'h')
        a.e(j_(2, 0x502650)); a.e(0)
    w = a.done()
    assert a.pc <= DATA
    return w, a.lab


def elf_patch(elf):
    e = bytearray(elf)
    def put(addr, words):
        for k, w in enumerate(words): struct.pack_into('<I', e, addr - VA + OFF + 4 * k, w)
    def get(addr): return struct.unpack_from('<I', e, addr - VA + OFF)[0]
    assert all(get(x) == 0 for x in range(SLED, SLED_END, 4))
    assert get(LOAD_CALL) == j_(3, 0x21f750) and get(FREE1) == j_(3, 0x502650) and get(FREE2) == j_(3, 0x502650)
    # 대기: nop 256개 대신 반복문 후 원래 다음 위치로
    put(SLED, [i_(9, 'zero', 'at', 0x100), i_(9, 'at', 'at', -1), i_(5, 'at', 'zero', -2), 0,
               i_(4, 'zero', 'zero', (SLED_END - (SLED + 0x10) - 4) >> 2), 0])
    w, lab = code()
    put(CODE, w)
    put(DATA, [BASE] + [0] * 32)
    put(LOAD_CALL, [j_(3, lab['fload'])])
    put(FREE1, [j_(3, lab['chk1'])])
    put(FREE2, [j_(3, lab['chk2'])])
    return bytes(e)
