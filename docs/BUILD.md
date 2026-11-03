# 재빌드

## 준비
- Python 3, `pip install numpy Pillow opencv-python`
- 저장소 최상위에 원본 `MVP Baseball 2003 (USA).iso`(MD5 `e7827b06876466832f6528cbecd455d4`)와 나눔스퀘어 네오 TTF 5종
- xdelta3 (`xdelta.exe`)

## 빌드
```powershell
python tools/build.py
```
최상위에 `MVP Baseball 2003 (Korean).iso`가 만들어진다. 번역 작업용 원문 목록 `work/en_loc.txt`(EA 저작물)는 저장소에 넣지 않았다.

## 차분 파일
```powershell
.\xdelta.exe -e -0 -S none -A -s "MVP Baseball 2003 (USA).iso" "MVP Baseball 2003 (Korean).iso" MVP_Baseball_2003_PS2_KO_v1.3.xdelta
```

## 파일
- `translation/ko1~5.txt`: `문자열ID|번역` (ENGLISH.LOC)
- `translation/names.txt`: `영문 이름|한글 표기` (선수 DB·신인 이름 풀)
- `tools/build.py`: 전체 빌드, `loc.py` LOC 표, `kfont.py` SFN 글꼴, `loadko.py` 로딩 화면, `names.py` 이름·ELF, `isobuild.py`·`isofs.py`·`udf.py` 디스크
- `tools/emu.ps1`, `tools/k.sh`: 검증용 PCSX2 조작 스크립트(개인 환경용)
- `SLUS-20650_20A53021.pnach`: 16:9 와이드 패치
