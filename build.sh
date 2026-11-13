#!/bin/sh
# build.sh -- build out/minigui.rom (and out/c_drive.img) from src/ inside the NeoSymbian build image (docker/toolchain).
# Needs only Docker and a populated src/ (./fetch.sh).
#
# The build runs in a Docker volume (BUILD_VOLUME, default neosymbian-build) rather than on the bind-mounted checkout: the sources are
# ~1 GB in tens of thousands of small files, and a bind mount from a Windows or macOS host is far too slow for a
# compiler. The volume also keeps the objects between runs (incremental builds); FULL=1 starts from scratch.
# Results are copied back to out/.
set -eu
cd "$(dirname "$0")"
. ./images.sh
IMAGE=$BUILD_IMAGE
[ -d src/oss.FCL.sf.os.kernelhwsrv ] || { echo "src/ is empty: run ./fetch.sh first" >&2; exit 1; }
mkdir -p out
# build info (the ROM's \Resource\NeoSymbian\build.txt): this checkout's commit, +dirty if it differs from it
REV=$(git rev-parse --short HEAD 2>/dev/null) || REV=unknown
[ "$REV" = unknown ] || git diff --quiet HEAD -- 2>/dev/null || REV="$REV+dirty"
exec docker run --rm -e FULL="${FULL:-}" -e SIS="${SIS:-}" -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" -e NEO_BUILD_REV="$REV" \
	-v "$PWD:/work" -v "${BUILD_VOLUME:-neosymbian-build}:/build" -w /work "$IMAGE" bash scripts/build-in-container.sh
