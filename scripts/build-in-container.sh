#!/usr/bin/env bash
# build-in-container.sh -- run inside the build image (docker/toolchain) with the checkout at /work and the build volume at /build:
# sync the checkout into the volume, run the build there (scripts/build-steps.sh), copy out/ back.
set -eu
[ -z "${FULL:-}" ] || find /build -mindepth 1 -maxdepth 1 -exec rm -rf {} +
mkdir -p /build
# the sources change only with sources.lock: copy each package once per commit (tar: one stream, not 30000 file opens)
mkdir -p /build/src /build/.stamp
grep -v '^#' /work/sources.lock | while IFS="$(printf '	')" read -r pkg commit; do
	[ -n "$pkg" ] || continue
	if [ "$(cat "/build/.stamp/$pkg" 2>/dev/null)" != "$commit" ]; then
		echo "syncing src/$pkg into the build volume ..."
		rm -rf "/build/src/$pkg"
		tar -C /work --exclude=.git -cf - "src/$pkg" | tar -C /build -xf -
		echo "$commit" > "/build/.stamp/$pkg"
	fi
done
# our own files: always (small)
tar -C /work -cf - emitter kernel toolchain tools scripts apps sis.lock | tar -C /build -xf -
# NeoSymbian: the Rust staticlib(s) dropped into rust/ (none = baseline build)
rm -rf /build/rust
[ ! -d /work/rust ] || tar -C /work -cf - rust | tar -C /build -xf -
cd /build
rc=0
bash scripts/build-steps.sh || rc=$?
# BASE_OUT=1 (CI on main): the built state without the sources, the Rust EXEs and out/ -> /work/base, the prebuilt base
# that lets a build of this same commit skip every step up to eshell (build-steps.sh)
if [ "$rc" = 0 ] && [ -n "${BASE_OUT:-}" ]; then
	echo "${NEO_BUILD_REV:-}" > /build/.base
	rm -rf /work/base && mkdir -p /work/base
	tar -C /build --exclude=./src --exclude=./rust --exclude=./out --exclude=./.stamp -cf - . | tar -C /work/base -xf -
fi
mkdir -p /work/out
rm -rf /work/out/log
cp -a /build/out/. /work/out/
chown -R "${HOST_UID:-0}:${HOST_GID:-0}" /work/out 2>/dev/null || true
exit $rc
