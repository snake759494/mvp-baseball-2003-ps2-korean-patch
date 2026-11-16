"""기록 머리글 문자열 분리 (ELF 패치)

게임은 R/H/E 같은 약어 문자열 하나를 타자·투수·수비 기록, 박스 스코어, 라인 스코어가 함께 쓴다.
번역 하나로는 '득점'(타자)과 '실점'(투수)을 동시에 맞출 수 없고, 좁은 라인 스코어 칸은 넘친다.
기록 열 표(0x5cda20~, [문자열 ID, 플래그] 쌍)와 박스 스코어 코드의 ID 즉값을, 이미 번역된 다른 문자열의
ID로 바꿔 화면별로 알맞은 말이 나오게 한다. 라인 스코어는 그대로 두어 R/H/E 영문 유지.
"""
import struct

VA, OFF = 0x100000, 0x1000
# 쓸 문자열 ID (색인: 번역)
RS, RA, ERR, HITS, HA = 6504, 6505, 3102, 9297, 6572   # 675 득점, 676 실점, 397 실책, 1103 안타, 742 피안타
R, H, E = 6550, 6551, 6552                              # 721 R, 722 H, 723 E
H_ = 6532                                               # 703 H (타자·투수 기록 공용)
# 표 항목(주소: (원래 ID, 새 ID))
WORDS = {
    0x5cda58: (R, RS),     # 타자 기록 R -> 득점
    0x5cdb28: (R, RA),     # 투수 기록 R -> 실점
    0x5cdb80: (H_, HA),    # 투수 기록 H -> 피안타
    0x5cdc10: (E, ERR),    # 수비 기록 E -> 실책
    0x5cdc50: (R, RS),     # 타자 소개 창 기록 R -> 득점
    0x5cdc54: (H, HITS),   # 타자 소개 창 기록 H -> 안타
}
# addiu a1, zero, ID 명령 (박스 스코어 등)
IMMS = {
    0x31d4f8: (R, RS),     # 박스 스코어 타자 R
    0x31d538: (H, HITS),   # 박스 스코어 타자 H
    0x31e02c: (E, ERR),    # 박스 스코어 실책
    0x31ea60: (H_, HITS),  # 박스 스코어 투수 H (칸이 좁아 피안타 대신 안타)
    0x31eaa0: (R, RA),     # 박스 스코어 투수 R
    0x46456c: (R, RS),     # 경기 중 타자 기록 창 R
}


# 0x500920(넓은 문자열 <- char*, "\xHH" 처리) 복사 경로에 2바이트 한글 해석 추가 (순위표·박스 스코어 팀 이름 등)
# 0x5009e0: addiu a1,a1,1 / sh v0,0(a0)  ->  j CAVE / nop
CONV_AT, CONV_BACK, CAVE = 0x5009e0, 0x5009e8, 0x4e2e90   # CAVE: fontmem 표 뒤 빈 nop 자리


def cave():
    i = lambda op, rs, rt, im: (op << 26) | (rs << 21) | (rt << 16) | (im & 0xffff)
    r = lambda rs, rt, rd, sa, fn: (rs << 21) | (rt << 16) | (rd << 11) | (sa << 6) | fn
    at, v0, v1, a0, a1 = 1, 2, 3, 4, 5
    return [
        i(0x0b, v0, at, 0x80),          # sltiu at,v0,0x80
        i(5, at, 0, 6),                 # bnez at,ST
        i(9, a1, a1, 1),                # addiu a1,a1,1
        i(0x24, a1, v1, 0),             # lbu v1,0(a1)
        i(9, a1, a1, 1),                # addiu a1,a1,1
        r(0, v0, v0, 7, 0),             # sll v0,v0,7
        r(v0, v1, v0, 0, 0x21),         # addu v0,v0,v1
        i(9, v0, v0, 0x6b80),           # addiu v0,v0,0x6b80
        (2 << 26) | (CONV_BACK >> 2),   # ST: j CONV_BACK
        i(0x29, a0, v0, 0),             # sh v0,0(a0)
    ]


# 0x500a00(넓은 문자열 -> char*)는 0x100 이상 문자를 "\xXXXX"로 바꾸는데, 승·패 표시가 붙은 투수 이름처럼
# 이 이스케이프를 풀지 않는 경로로 다시 그려지면 "\xc7ac..."가 그대로 보인다. 한글 음절은 2바이트 한글로 내보낸다.
# 0x500a64: lhu a2,0(s1) / addiu a1,s2,0x7f48  ->  j CAVE2 / nop   (v1 = 문자, s0 = 쓰기 위치)
ESC_AT, ESC_JAL, ESC_NEXT, CAVE2 = 0x500a64, 0x500a6c, 0x500a84, 0x4e2d00   # CAVE2: fontmem 코드 뒤 빈 자리


def cave2():
    i = lambda op, rs, rt, im: (op << 26) | (rs << 21) | (rt << 16) | (im & 0xffff)
    r = lambda rs, rt, rd, sa, fn: (rs << 21) | (rt << 16) | (rd << 11) | (sa << 6) | fn
    at, v0, v1, a1, a2, s0, s1, s2 = 1, 2, 3, 5, 6, 16, 17, 18
    return [
        i(0x0d, 0, at, 0xac00),         # ori at,zero,0xac00
        r(v1, at, v0, 0, 0x23),         # subu v0,v1,at
        i(0x0b, v0, at, 11172),         # sltiu at,v0,11172
        i(4, at, 0, 9),                 # beqz at,FB
        r(0, v0, at, 7, 2),             # srl at,v0,7
        i(9, at, at, 0x80),             # addiu at,at,0x80
        i(0x28, s0, at, 0),             # sb at,0(s0)
        i(0x0c, v0, v0, 0x7f),          # andi v0,v0,0x7f
        i(9, v0, v0, 0x80),             # addiu v0,v0,0x80
        i(0x28, s0, v0, 1),             # sb v0,1(s0)
        i(9, s0, s0, 2),                # addiu s0,s0,2
        (2 << 26) | (ESC_NEXT >> 2),    # j ESC_NEXT
        0,
        i(0x25, s1, a2, 0),             # FB: lhu a2,0(s1)   (원래 명령)
        i(9, s2, a1, 0x7f48),           # addiu a1,s2,0x7f48
        (2 << 26) | (ESC_JAL >> 2),     # j ESC_JAL (sprintf "\x%04x")
        0,
    ]


def elf_patch(elf):
    e = bytearray(elf)
    o = lambda a: a - VA + OFF
    w = lambda a: struct.unpack_from('<I', e, o(a))[0]
    assert w(CONV_AT) == 0x24a50001 and w(CONV_AT + 4) == 0xa4820000, hex(w(CONV_AT))
    code = cave()
    assert all(w(CAVE + 4 * k) == 0 for k in range(len(code)))
    for k, x in enumerate(code): struct.pack_into('<I', e, o(CAVE + 4 * k), x)
    struct.pack_into('<II', e, o(CONV_AT), (2 << 26) | (CAVE >> 2), 0)
    assert w(ESC_AT) == 0x96260000 and w(ESC_AT + 4) == 0x26457f48, hex(w(ESC_AT))
    code = cave2()
    assert all(w(CAVE2 + 4 * k) == 0 for k in range(len(code)))
    for k, x in enumerate(code): struct.pack_into('<I', e, o(CAVE2 + 4 * k), x)
    struct.pack_into('<II', e, o(ESC_AT), (2 << 26) | (CAVE2 >> 2), 0)
    for a, (old, new) in WORDS.items():
        assert struct.unpack_from('<I', e, o(a))[0] == old, hex(a)
        struct.pack_into('<I', e, o(a), new)
    for a, (old, new) in IMMS.items():
        w = struct.unpack_from('<I', e, o(a))[0]
        assert w == 0x24050000 | old, hex(a)
        struct.pack_into('<I', e, o(a), 0x24050000 | new)
    return bytes(e)
