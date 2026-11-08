#!/usr/bin/env bash
# build-steps.sh -- the build proper, run from the repository root inside the build image (scripts/build-in-container.sh
# prepares it). Every step logs to out/log/NN-name.log and stops the build on failure.
set -u
cd "$(dirname "$0")/.."
mkdir -p out/log
LOG=out/log

N=0
step() {	# step <name> <command...> : run, log, stop on failure
	N=$((N+1)); local name="$1"; shift
	local log; log=$(printf '%s/%02d-%s.log' "$LOG" "$N" "$name")
	echo "[$N] $name"; local t0=$SECONDS
	if "$@" > "$log" 2>&1; then echo "    ok ($((SECONDS-t0)) s)"; else
		echo "    FAILED (see out/log/$(basename "$log")):"; tail -n 15 "$log" | cut -c1-220; exit 1; fi
}

# The components of Symbian's minigui configuration are listed in emitter/components.py.
KEYS=$(python3 -c "import sys; sys.path.insert(0, 'emitter'); import components; print(' '.join(components.COMPONENTS))")

step executive-headers bash toolchain/genexec.sh
step kernel-nanokernel bash kernel/build_nkern.sh
step kernel-ekern bash kernel/build_ekern.sh
step euser python3 emitter/build_euser_device.py
# the epoc32/include tree the userland mmps #include (abld export equivalent)
step epoc32-export python3 tools/epoc32_export.py
# the icon-ID headers (<x>.mbg) S60 sources include, which the mifconv build step emitted
step mbg python3 tools/mbg.py
# the S60 CDL client headers no bld.inf exports (mifheader.cdl.h ...): CdlCompiler from mw.uitools, built for the host
step cdl-headers python3 tools/cdl_headers.py
step casefix python3 tools/casefix.py
# the Feature Manager's ROM database (Z:\\private\\10205054\\features.dat): S60 features on iff the variant defines them
step features-dat python3 tools/features_dat.py emitter/features.dat
# Central Repository files for repositories that ship only as .crml (emitter/cenrep/<uid>.txt)
step cenrep-crml python3 tools/crml2txt.py
step fileserver-objects bash kernel/build_efile.sh
step efsrv python3 emitter/build_efsrv_device.py
step hal python3 emitter/build_hal_device.py
step efile python3 emitter/build_efile_exe.py
# the resources first (so every .rsg exists before the components that include them), then the components
step resources python3 emitter/build_mmp.py --rsc $KEYS
step components python3 emitter/build_mmp.py $KEYS
step estart python3 emitter/build_estart_exe.py
step elocal-fsy python3 emitter/build_elocal_fsy.py
# the ROFS and composite file systems: a composite Z: (the AArch64 kernel's core ROM + ROFS image, docs/filesystem.md FS4)
step erofs-fsy python3 emitter/build_elocal_fsy.py emitter/erofs.fsy --fs erofs
step ecomp-fsy python3 emitter/build_elocal_fsy.py emitter/ecomp.fsy --fs ecomp
step ekdata python3 emitter/build_ekdata_dll.py
step eshell python3 emitter/build_eshell_exe.py
# NeoSymbian: the Rust EXEs (NeoSymbian/e32-rs) listed in rust/exes.txt go into the ROM (Z:\sys\bin, through
# emitter/rust_rom.args) or, marked drive=c, onto C:\sys\bin (emitter/rust_cdrive.args); without the manifest the
# build is unchanged.
if [ -f rust/exes.txt ]; then
	step rust-exes python3 emitter/build_rust_exe.py rust/exes.txt
else
	rm -f emitter/rust_rom.args emitter/rust_cdrive.args
fi
step rom bash kernel/build_rom.sh
# C: carries the bitmap font: fntstore's XIP-ROM font path has an alignment bug real NAND phones never hit (they use the
# RAM path), so the font lives on a non-ROM drive
C_EXTRA=""
[ ! -f emitter/rust_cdrive.args ] || C_EXTRA=$(cat emitter/rust_cdrive.args)
# shellcheck disable=SC2086
step c-drive python3 tools/mkfat.py out/c_drive.img \
	"Resource/Fonts/ceurope.gdr=src/oss.FCL.sf.os.graphics/graphicstest/uibench/data/CEUROPE.GDR" $C_EXTRA
echo "done: out/minigui.rom out/c_drive.img"
