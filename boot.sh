#!/bin/sh
# boot.sh -- boot out/minigui.rom on QEMU Syborg (ghcr.io/phorepoc/qemu-syborg), type `dir` into ESHELL, and write
# out/fb.png (the screen) and out/serial.log (the kernel's serial output).
#   SECS     how long the emulator runs (default 90)   DELAY   seconds to wait before typing (default 55)
#   RUN      the commands typed into ESHELL, comma-separated, GAP seconds apart (default `dir`; lower-case letters
#            and digits only, e.g. RUN=neohello,neor1). SECS defaults to 90 + GAP per extra command.
#   MONITOR  raw QEMU monitor commands sent after RUN, `;`-separated, MON_GAP seconds apart (default 1; drags need
#            ~0.3) (e.g. a tap on the absolute pointer: MONITOR="mouse_move 3285 27904;mouse_button 1;mouse_button 0";
#            0..0x7FFF covers the screen; `info status` is a harmless filler to wait).
set -eu
cd "$(dirname "$0")"
[ -f out/minigui.rom ] || { echo "out/minigui.rom is missing: run ./build.sh first" >&2; exit 1; }
QEMU_IMAGE="${QEMU_IMAGE:-ghcr.io/phorepoc/qemu-syborg:latest}"
BUILD_IMAGE="${BUILD_IMAGE:-ghcr.io/phorepoc/base:latest}"
RUN="${RUN:-dir}"; GAP="${GAP:-8}"
case $RUN in *[!a-z0-9,]*|""|,*|*,|*,,*) echo "RUN: comma-separated words of a-z and 0-9" >&2; exit 2 ;; esac
MONITOR="${MONITOR:-}"
case $MONITOR in *[!a-z0-9_\ \;-]*) echo "MONITOR: monitor commands of a-z, 0-9, _ - and spaces, ;-separated" >&2; exit 2 ;; esac
MON_GAP="${MON_GAP:-1}"
case $MON_GAP in *[!0-9.]*|"") echo "MON_GAP: seconds, e.g. 0.3" >&2; exit 2 ;; esac
NMON=0; [ -n "$MONITOR" ] && NMON=$(echo "$MONITOR" | tr ';' '\n' | wc -l | tr -d ' ')
MONSECS=$(awk "BEGIN { print int($NMON * $MON_GAP + 0.999) }")
NCMD=$(echo "$RUN" | tr ',' '\n' | wc -l | tr -d ' ')
SECS="${SECS:-$((90 + GAP * (NCMD - 1)))}"; DELAY="${DELAY:-55}"
REST=$((SECS - DELAY - 3 - GAP * (NCMD - 1) - MONSECS))
[ "$REST" -ge 0 ] || { echo "SECS too short for $NCMD commands" >&2; exit 2; }
rm -f out/fb.ppm out/fb.png out/serial.log
USER_ARGS=""
[ "$(uname -s)" = Linux ] && USER_ARGS="--user $(id -u):$(id -g)"
# The QEMU monitor is the container's stdin: `sendkey` types into the emulated keyboard. ESHELL needs a while to come up.
# shellcheck disable=SC2086
{ sleep "$DELAY"
  first=1
  for cmd in $(echo "$RUN" | tr ',' ' '); do
    [ "$first" = 1 ] || sleep "$GAP"; first=0
    for k in $(echo "$cmd" | sed 's/./& /g') ret; do echo "sendkey $k"; sleep 0.5; done
  done
  [ -z "$MONITOR" ] || echo "$MONITOR" | tr ';' '\n' | while read -r m; do sleep "$MON_GAP"; echo "$m"; done
  sleep "$REST"
} | docker run --rm -i $USER_ARGS -v "$PWD/out:/work" \
	-e SERIAL=/work/serial.log -e FB=/work/fb.ppm -e C_DRIVE=/work/c_drive.img \
	"$QEMU_IMAGE" run-syborg /work/minigui.rom "$SECS" > out/qemu-monitor.log 2>&1 || true
[ -s out/fb.ppm ] || { echo "no framebuffer dump: see out/qemu-monitor.log" >&2; exit 1; }
# shellcheck disable=SC2086
docker run --rm $USER_ARGS -v "$PWD:/work" -w /work "$BUILD_IMAGE" python3 tools/ppm2png.py out/fb.ppm out/fb.png
echo "out/fb.png, out/serial.log"
