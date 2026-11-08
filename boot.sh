#!/bin/sh
# boot.sh -- boot out/minigui.rom on QEMU's Syborg board (ghcr.io/neosymbian/symbian-qemu), type RUN into ESHELL,
# send MONITOR, and write out/fb.png (the screen) and out/serial.log (the kernel's serial output).
# The runner (run-syborg in the image) is event-driven: it types once ESHELL or neoui is up, moves to the next
# command when the last one's process started and the serial log went quiet, and stops when the script is done.
#   RUN      commands typed into ESHELL, comma-separated (default `dir`; lower-case letters and digits only,
#            e.g. RUN=neohello,neor1)
#   MONITOR  raw QEMU monitor commands sent after RUN, `;`-separated, MON_GAP seconds apart (default 1; drags need
#            ~0.3) (e.g. a tap on the absolute pointer: MONITOR="mouse_move 3285 27904;mouse_button 1;mouse_button 0";
#            0..0x7FFF covers the screen). Two more commands: `expect TEXT` waits until TEXT appears in the serial
#            log (after the previous expect's match; EXPECT_MAX seconds, default 30) and `wait N` sleeps N seconds.
#   SCREEN   the screen size, e.g. SCREEN=1080x2160 (the Pixel 3a XL); default the board's 768x640
#   SECS     the most the whole run may take (default 600)
#   SNAPSHOT=1  keep the booted machine in out/snap/ and start later runs of the same ROM and C: from it
set -eu
cd "$(dirname "$0")"
[ -f out/minigui.rom ] || { echo "out/minigui.rom is missing: run ./build.sh first" >&2; exit 1; }
. ./images.sh
RUN="${RUN:-dir}"
case $RUN in *[!a-z0-9,]*|""|,*|*,|*,,*) echo "RUN: comma-separated words of a-z and 0-9" >&2; exit 2 ;; esac
MONITOR="${MONITOR:-}"
case $MONITOR in *[!A-Za-z0-9_\ \;:,.\(\)\|-]*) echo "MONITOR: commands of letters, digits, spaces and _ : , . ( ) | -, ;-separated" >&2; exit 2 ;; esac
MON_GAP="${MON_GAP:-1}"
case $MON_GAP in *[!0-9.]*|"") echo "MON_GAP: seconds, e.g. 0.3" >&2; exit 2 ;; esac
case ${EXPECT_MAX:-30} in *[!0-9.]*) echo "EXPECT_MAX: seconds" >&2; exit 2 ;; esac
SCREEN="${SCREEN:-768x640}"
case $SCREEN in *[!0-9x]*|x*|*x|*x*x*) echo "SCREEN: WIDTHxHEIGHT, e.g. 1080x2160" >&2; exit 2 ;; esac
SECS="${SECS:-600}"
rm -f out/fb.ppm out/fb.png out/serial.log
USER_ARGS=""
[ "$(uname -s)" = Linux ] && USER_ARGS="--user $(id -u):$(id -g)"
SNAP_ARGS=""
[ "${SNAPSHOT:-0}" = 1 ] && SNAP_ARGS="-e SNAPSHOT=/work/snap"
rc=0
# shellcheck disable=SC2086
docker run --rm $USER_ARGS -v "$PWD/out:/work" -e SERIAL=/work/serial.log -e FB=/work/fb.ppm \
	-e C_DRIVE=/work/c_drive.img -e RUN="$RUN" -e MONITOR="$MONITOR" -e MON_GAP="$MON_GAP" ${EXPECT_MAX:+-e EXPECT_MAX="$EXPECT_MAX"} -e SCREEN="$SCREEN" \
	$SNAP_ARGS "$QEMU_IMAGE" run-syborg /work/minigui.rom "$SECS" > out/qemu-monitor.log 2>&1 || rc=$?
cat out/qemu-monitor.log
[ -s out/fb.ppm ] || { echo "no framebuffer dump: see out/qemu-monitor.log" >&2; exit 1; }
# shellcheck disable=SC2086
docker run --rm $USER_ARGS -v "$PWD:/work" -w /work "$BUILD_IMAGE" python3 tools/ppm2png.py out/fb.ppm out/fb.png
echo "out/fb.png, out/serial.log"
exit "$rc"
