#!/bin/bash
# 사용: k.sh 출력이름 키... (W/A/S/D 방향, K=X, L=O, I=세모, J=네모, R=START, Q=L1, E=R1, 숫자=대기초)
E="powershell -ExecutionPolicy Bypass -File $(dirname $0)/emu.ps1"
out=$1; shift
declare -A V=([W]=26 [A]=25 [S]=28 [D]=27 [K]=4B [L]=4C [I]=49 [J]=4A [R]=0D [B]=08 [Q]=51 [E]=45)
for k in "$@"; do
  if [[ $k =~ ^[0-9]+$ ]]; then sleep $k; else $E kpost ${V[$k]},150 >/dev/null; sleep 1.5; fi
done
mkdir -p "$(dirname $0)/../work/shots"
$E pshot "D:/ps2/MVP베이스볼2003/work/shots/${out}.png" >/dev/null
