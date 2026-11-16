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


def elf_patch(elf):
    e = bytearray(elf)
    o = lambda a: a - VA + OFF
    for a, (old, new) in WORDS.items():
        assert struct.unpack_from('<I', e, o(a))[0] == old, hex(a)
        struct.pack_into('<I', e, o(a), new)
    for a, (old, new) in IMMS.items():
        w = struct.unpack_from('<I', e, o(a))[0]
        assert w == 0x24050000 | old, hex(a)
        struct.pack_into('<I', e, o(a), 0x24050000 | new)
    return bytes(e)
