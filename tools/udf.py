"""UDF(ISO9660 브리지) 파일 엔트리 갱신

게임(IOP 리소스 모듈)은 UDF 로 파일 위치를 찾으므로, 파일을 옮기거나 크기를
바꾸면 ISO9660 레코드와 함께 UDF File Entry 의 할당 기술자/크기도 고쳐야 한다.
"""
import struct

SEC = 2048


def crc_itu(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xffff if crc & 0x8000 else (crc << 1) & 0xffff
    return crc


def fix_tag(buf, location=None):
    """디스크립터 태그의 CRC/체크섬 재계산 (buf 는 bytearray, 0 에서 태그 시작)"""
    if location is not None:
        struct.pack_into('<I', buf, 12, location)
    crclen = struct.unpack_from('<H', buf, 10)[0]
    struct.pack_into('<H', buf, 8, crc_itu(bytes(buf[16:16 + crclen])))
    s = sum(buf[0:4]) + sum(buf[5:16])
    buf[4] = s & 0xff


class UDF:
    def __init__(self, f):
        self.f = f
        a = self.read(256)
        assert struct.unpack_from('<H', a, 0)[0] == 2, 'UDF 앵커 없음'
        self.vds = [struct.unpack_from('<II', a, 16), struct.unpack_from('<II', a, 24)]
        self.pd = []          # (섹터) 파티션 디스크립터 위치들
        self.part_start = None
        fsd_lbn = None
        for ln, loc in self.vds:
            for s in range(loc, loc + ln // SEC):
                b = self.read(s); tag = struct.unpack_from('<H', b, 0)[0]
                if tag == 5:
                    self.pd.append(s)
                    self.part_start, self.part_len = struct.unpack_from('<II', b, 188)
                elif tag == 6 and fsd_lbn is None:
                    fsd_lbn = struct.unpack_from('<I', b, 248 + 4)[0]
                elif tag == 8:
                    break
        fsd = self.read(self.part_start + fsd_lbn)
        assert struct.unpack_from('<H', fsd, 0)[0] == 256
        root_lbn = struct.unpack_from('<I', fsd, 400 + 4)[0]
        self.files = {}
        self._walk(root_lbn, '')

    def read(self, sector, n=1):
        self.f.seek(sector * SEC)
        return bytearray(self.f.read(SEC * n))

    def _fe(self, lbn):
        b = self.read(self.part_start + lbn)
        tag = struct.unpack_from('<H', b, 0)[0]
        assert tag in (261, 266), tag
        if tag == 261:
            l_ea, l_ad = struct.unpack_from('<II', b, 168); ad0 = 176 + l_ea
        else:
            l_ea, l_ad = struct.unpack_from('<II', b, 208); ad0 = 216 + l_ea
        adtype = struct.unpack_from('<H', b, 16 + 18)[0] & 7
        return b, tag, ad0, l_ad, adtype

    def _extents(self, b, ad0, l_ad, adtype):
        out = []
        step = 8 if adtype == 0 else 16
        for p in range(ad0, ad0 + l_ad, step):
            ln, pos = struct.unpack_from('<II', b, p)
            out.append((ln & 0x3fffffff, pos))
        return out

    def _walk(self, lbn, path):
        b, tag, ad0, l_ad, adtype = self._fe(lbn)
        size = struct.unpack_from('<Q', b, 56)[0]
        data = bytearray()
        for ln, pos in self._extents(b, ad0, l_ad, adtype):
            data += self.read(self.part_start + pos, (ln + SEC - 1) // SEC)[:ln]
        data = data[:size]
        p = 0
        while p + 38 <= len(data):
            if struct.unpack_from('<H', data, p)[0] != 257:
                break
            fc = data[p + 18]; lfi = data[p + 19]
            icb_lbn = struct.unpack_from('<I', data, p + 20 + 4)[0]
            liu = struct.unpack_from('<H', data, p + 36)[0]
            name = bytes(data[p + 38 + liu:p + 38 + liu + lfi])
            if lfi and not fc & 8:
                nm = name[1:].decode('latin-1') if name[0] == 8 else name[1:].decode('utf-16-be')
                full = path + '/' + nm
                if fc & 2:
                    self._walk(icb_lbn, full)
                else:
                    self.files[full.upper()] = icb_lbn
            p += (38 + liu + lfi + 3) & ~3

    def set_file(self, path, sector, size):
        """path(대소문자 무시)의 파일을 절대 섹터 sector, 크기 size 로 지정"""
        lbn = self.files[path.upper()]
        b, tag, ad0, l_ad, adtype = self._fe(lbn)
        assert adtype in (0, 1) and l_ad in (8, 16), (path, adtype, l_ad)
        struct.pack_into('<Q', b, 56, size)
        struct.pack_into('<II', b, ad0, size, sector - self.part_start)
        # 기록된 블록 수(Logical Blocks Recorded)
        struct.pack_into('<Q', b, 64, (size + SEC - 1) // SEC)
        fix_tag(b)
        self.f.seek((self.part_start + lbn) * SEC); self.f.write(b)

    def grow(self, total_sectors):
        """파티션 길이를 이미지 끝까지 늘리고 마지막 섹터에 앵커를 둔다"""
        new_len = total_sectors - self.part_start
        for s in self.pd:
            b = self.read(s)
            if struct.unpack_from('<I', b, 192)[0] < new_len:
                struct.pack_into('<I', b, 192, new_len)
                fix_tag(b)
                self.f.seek(s * SEC); self.f.write(b)
        a = self.read(256)
        fix_tag(a, total_sectors - 1)
        self.f.seek((total_sectors - 1) * SEC); self.f.write(a)
