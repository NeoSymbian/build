#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# build-user-manifest.sh -- the user side's file list for the AArch64 kernel's ROM (kernel baseport/arm64/tools/
# build-userrom.sh reads it from the build volume) and NeoSymbian/legacy's ROM checks (sis.py romcheck):
# .ekern-build/rombuild.args (--xip/--data "<Z: path>=<file>" pairs) and the build info .ekern-build/build.txt.
# (It was the user half of kernel/build_rom.sh, which also linked the 2010 Syborg kernel into out/minigui.rom; Syborg
# is no longer a target, US5.)
set -eu
cd "$(dirname "$0")/.."
G=src/oss.FCL.sf.os.graphics
mkdir -p .ekern-build

# The userland: the file server (EFILE is the ROM's secondary process) and the libraries it needs, ESTART with a
# drive map (the kernel's packager puts its own estart.txt in its place), the FAT file system plug-in, the keymap, the shell, the 3-DLL locale,
# then every built registry component (graphical window server in the EWSRV.EXE slot, econswserv.dll in the ECONS.DLL
# slot -- the stock text console econs_twin.dll instead in a UI ROM with SYSSTART.EXE, see rom_args.py -- fbserv, the
# gdi/bitgdi/fntstore stack ...) and its resources.
ARGS=.ekern-build/rombuild.args
# NeoSymbian build info: the user-side ROM's build time and this repo's commit (build.sh), read by neoui's About phone
# and Dev tools; the phone keeps it in the core ROM (kernel build-userrom.sh)
printf '%srom %s build %s\n' "${NEO_BUILD_NAME:+$NEO_BUILD_NAME: }" "$(date -u +%Y-%m-%dT%H:%MZ)" "${NEO_BUILD_REV:-unknown}" > .ekern-build/build.txt
{
  printf '%s\n' \
    --xip 'Sys\Bin\euser.dll=emitter/euser_dev.dll' \
    --xip 'Sys\Bin\efsrv.dll=emitter/efsrv_dev.dll' \
    --xip 'Sys\Bin\hal.dll=emitter/hal_dev.dll' \
    --xip 'Sys\Bin\efile.exe=emitter/efile.exe' \
    --xip 'Sys\Bin\ESTART.EXE=emitter/estart.exe' \
    --xip 'Sys\Bin\ELOCAL.FSY=emitter/elocal.fsy' \
    --xip 'Sys\Bin\EROFS.FSY=emitter/erofs.fsy' \
    --xip 'Sys\Bin\ECOMP.FSY=emitter/ecomp.fsy' \
    --xip 'Sys\Bin\EKDATA.DLL=emitter/ekdata.dll' \
    --xip 'Sys\Bin\ESHELL.EXE=emitter/eshell.exe' \
    --data 'Sys\Data\estart.txt=src/symbian-qemu/baseport/syborg/estart.txt' \
    --data 'System\Data\wsini.ini='$G'/windowing/windowserver/minigui/group/wsini_minigui-stripped.ini' \
    --data 'Resource\NeoSymbian\build.txt=.ekern-build/build.txt' \
    --xinfo 'databss=0x00400000,cap1=0xFFFFFFFF,cap2=0xFFFFFFFF'
  # NeoSymbian: the Rust EXEs of rust/exes.txt (emitter/build_rust_exe.py writes their --xip lines)
  [ ! -f emitter/rust_rom.args ] || cat emitter/rust_rom.args
  # NeoSymbian: the files of old .sis packages (SIS=..., NeoSymbian/legacy tools/sis.py), as plain files on Z:
  [ ! -f emitter/sis_rom.args ] || cat emitter/sis_rom.args
  python3 kernel/rom_args.py
} > "$ARGS"
# every file it names must exist (the kernel's packager would only fail later, after a prebuilt base was exported)
python3 - "$ARGS" <<'PY'
import os, sys
words = [w.rstrip("\n") for w in open(sys.argv[1]) if w.strip()]
missing = [v for o, v in zip(words[0::2], words[1::2]) if o in ("--xip", "--data") and not os.path.isfile(v.partition("=")[2])]
sys.exit("rombuild.args names missing files:\n  " + "\n  ".join(missing) if missing else 0)
PY
