#!/bin/sh
# boot.sh -- boot out/minigui.rom on QEMU Syborg (ghcr.io/phorepoc/qemu-syborg), type `dir` into ESHELL, and write
# out/fb.png (the screen) and out/serial.log (the kernel's serial output).
#   SECS     how long the emulator runs (default 90)   DELAY   seconds to wait before typing (default 55)
#   RUN      the commands typed into ESHELL, comma-separated, GAP seconds apart (default `dir`; lower-case letters
#            and digits only, e.g. RUN=neohello,neor1). SECS defaults to 90 + GAP per extra command.
set -eu
cd "$(dirname "$0")"
[ -f out/minigui.rom ] || { echo "out/minigui.rom is missing: run ./build.sh first" >&2; exit 1; }
QEMU_IMAGE="${QEMU_IMAGE:-ghcr.io/phorepoc/qemu-syborg:latest}"
BUILD_IMAGE="${BUILD_IMAGE:-ghcr.io/phorepoc/base:latest}"
RUN="${RUN:-dir}"; GAP="${GAP:-8}"
case $RUN in *[!a-z0-9,]*|""|,*|*,|*,,*) echo "RUN: comma-separated words of a-z and 0-9" >&2; exit 2 ;; esac
NCMD=$(echo "$RUN" | tr ',' '\n' | wc -l | tr -d ' ')
SECS="${SECS:-$((90 + GAP * (NCMD - 1)))}"; DELAY="${DELAY:-55}"
REST=$((SECS - DELAY - 3 - GAP * (NCMD - 1)))
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
  sleep "$REST"
} | docker run --rm -i $USER_ARGS -v "$PWD/out:/work" \
	-e SERIAL=/work/serial.log -e FB=/work/fb.ppm -e C_DRIVE=/work/c_drive.img \
	"$QEMU_IMAGE" run-syborg /work/minigui.rom "$SECS" > out/qemu-monitor.log 2>&1 || true
[ -s out/fb.ppm ] || { echo "no framebuffer dump: see out/qemu-monitor.log" >&2; exit 1; }
# shellcheck disable=SC2086
docker run --rm $USER_ARGS -v "$PWD:/work" -w /work "$BUILD_IMAGE" python3 tools/ppm2png.py out/fb.ppm out/fb.png
echo "out/fb.png, out/serial.log"
