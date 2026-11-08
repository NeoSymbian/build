#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Show the Syborg emulator running on ZimaOS (container neosymbian-live, started by `neo live` there) on this Mac:
# SSH tunnels for VNC (127.0.0.1:5900: open vnc://127.0.0.1:5900 in Screen Sharing or any VNC viewer, password
# symbian unless neo live had VNC_PASSWORD; it shows the screen and takes keys and touches) and the QEMU
# monitor (127.0.0.1:4444, for mon.sh), and a ~3 fps mirror of the screen dump and serial log.
OUT="$(cd "$(dirname "$0")/../.." && pwd)/out"	# this checkout's out/ (gitignored)
LIVE=${LIVE:-/DATA/AppData/symbian-build/build/out/live}
CTL="$HOME/.ssh/neosymbian-live-%C"
ssh -o BatchMode=yes -o ControlMaster=yes -o ControlPath="$CTL" -o ControlPersist=no -N \
	-L 127.0.0.1:4444:127.0.0.1:4444 -L 127.0.0.1:5900:127.0.0.1:5900 zimaos &
tunnel=$!
trap 'kill $tunnel 2>/dev/null' EXIT INT TERM
sleep 2
while kill -0 $tunnel 2>/dev/null; do
	ssh -o ControlPath="$CTL" zimaos "cat $LIVE/fb.ppm" > "$OUT/fb.ppm.tmp" 2>/dev/null &&
		[ -s "$OUT/fb.ppm.tmp" ] && mv -f "$OUT/fb.ppm.tmp" "$OUT/fb.ppm"
	ssh -o ControlPath="$CTL" zimaos "cat $LIVE/serial.log" > "$OUT/serial.log.tmp" 2>/dev/null &&
		mv -f "$OUT/serial.log.tmp" "$OUT/serial.log"
	sleep 0.3
done
