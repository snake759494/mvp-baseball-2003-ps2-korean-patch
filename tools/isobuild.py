"""원본 ISO 복사 후 수정 파일 기록 (ISO9660 + UDF 브리지 갱신)

크기가 원래 섹터 안에 들어가면 제자리, 넘치면 이미지 끝에 추가한다.
"""
import os, shutil, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isofs, udf

SEC = 2048


def build(src, dst, files, log=print):
    """files: {'DATA/SHELL/SHELL.VIV': bytes}"""
    if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
        shutil.copyfile(src, dst)
    else:
        # 이전 빌드 재사용: 원본에서 수정 대상만 되돌릴 필요 없음(덮어씀). 단 끝에 붙은 것은 잘라낸다
        pass
    with open(src, 'rb') as fs:
        ents = {e[0]: e for e in isofs.walk(fs)}
        fs.seek(16 * SEC); pvd = fs.read(SEC)
    total = struct.unpack_from('<I', pvd, 80)[0]
    f = open(dst, 'r+b')
    f.truncate(total * SEC)
    # 원본 디렉터리/UDF 메타데이터 복원(이전 빌드 흔적 제거): 레코드와 FE 섹터만 원본에서 복사
    with open(src, 'rb') as fs:
        for name, (_, lba, size, roff) in ents.items():
            fs.seek(roff); rec = fs.read(34); f.seek(roff); f.write(rec)
        u0 = udf.UDF(fs)
        for path, lbn in u0.files.items():
            s = u0.part_start + lbn
            fs.seek(s * SEC); b = fs.read(SEC); f.seek(s * SEC); f.write(b)
        for s in u0.pd + [16, 256]:
            fs.seek(s * SEC); b = fs.read(SEC); f.seek(s * SEC); f.write(b)
    end = total
    u = udf.UDF(f)
    for name, data in files.items():
        _, lba, size, roff = ents[name]
        old_secs = (size + SEC - 1) // SEC
        new_secs = (len(data) + SEC - 1) // SEC
        if new_secs <= old_secs:
            pos = lba
        else:
            pos = end; end += new_secs
        f.seek(pos * SEC); f.write(data)
        pad = new_secs * SEC - len(data)
        if pad: f.write(bytes(pad))
        # ISO9660
        f.seek(roff); rec = bytearray(f.read(34))
        struct.pack_into('<I', rec, 2, pos); struct.pack_into('>I', rec, 6, pos)
        struct.pack_into('<I', rec, 10, len(data)); struct.pack_into('>I', rec, 14, len(data))
        f.seek(roff); f.write(rec)
        u.set_file('/' + name, pos, len(data))
        log(f'  {name}: {size} -> {len(data)} @ {pos}{" (moved)" if pos != lba else ""}')
    if end != total:
        end += 1   # UDF 앵커
        f.seek((end - 1) * SEC); f.write(bytes(SEC))
        f.seek(16 * SEC); p = bytearray(f.read(SEC))
        struct.pack_into('<I', p, 80, end); struct.pack_into('>I', p, 84, end)
        f.seek(16 * SEC); f.write(p)
        u.grow(end)
    f.truncate(end * SEC)
    f.close()
