#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# mon.sh "cmd;cmd;..."  -- send QEMU monitor commands to the live Syborg on ZimaOS (screen px: use tap X Y / swipe X1 Y X2)
# Then fetch the screen as $T/live.png (SCR=WxH: the screen size, default 768x640)
T="$(cd "$(dirname "$0")/../.." && pwd)/out/live"; mkdir -p "$T"
cmds=""
for c in $(echo "$1" | tr ';' ' ' | sed 's/ /_/g; s/__*/ /g'); do :; done
printf '%s\n' "$1" | tr ';' '\n' | python3 -c '
import sys
out=[]
for line in sys.stdin:
    p=line.split()
    if not p: continue
    import os
    W,H=map(int,os.environ.get("SCR","768x640").split("x")); sx=lambda v:int(int(v)*32768/W); sy=lambda v:int(int(v)*32768/H)
    if p[0]=="tap":
        out+= [f"mouse_move {sx(p[1])} {sy(p[2])}","mouse_button 1","mouse_button 0"]
    elif p[0]=="swipe":
        x1,y,x2=map(int,p[1:4]); out+=[f"mouse_move {sx(x1)} {sy(y)}","mouse_button 1"]
        for k in range(1,9): out.append(f"mouse_move {sx(x1+(x2-x1)*k//8)} {sy(y)}")
        out.append("mouse_button 0")
    elif p[0]=="vswipe":
        x,y1,y2=map(int,p[1:4]); out+=[f"mouse_move {sx(x)} {sy(y1)}","mouse_button 1"]
        for k in range(1,9): out.append(f"mouse_move {sx(x)} {sy(y1+(y2-y1)*k//8)}")
        out.append("mouse_button 0")
    elif p[0]=="wait": out.append("#wait "+p[1])
    else: out.append(line.strip())
print("\n".join(out))' > $T/mon.txt
ssh -o BatchMode=yes zimaos 'while read -r l; do case $l in "#wait "*) sleep ${l#\#wait };; *) printf "%s\n" "$l"; sleep 0.4;; esac; done | nc -q1 127.0.0.1 4444 >/dev/null 2>&1; sleep 1.5; cat ${LIVE:-/DATA/AppData/symbian-build/build/out/live}/fb.ppm' < $T/mon.txt > $T/live.ppm
python3 - "$T/live.ppm" "$T/live.png" <<'PY'
import sys,zlib,struct
d=open(sys.argv[1],'rb').read(); parts=d.split(b'\n',3); w,h=map(int,parts[1].split()); px=parts[3]
raw=b''.join(b'\0'+px[y*w*3:(y+1)*w*3] for y in range(h))
c=lambda t,b: struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
open(sys.argv[2],'wb').write(b'\x89PNG\r\n\x1a\n'+c(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+c(b'IDAT',zlib.compress(raw,6))+c(b'IEND',b''))
PY
ssh -o BatchMode=yes zimaos 'grep -a "neoui\|clock:\|EKERN\] \(exit\|panic\)\|Fault" ${LIVE:-/DATA/AppData/symbian-build/build/out/live}/serial.log | tail -12'
