#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# build.sh <src-root> <out-dir> -- build the Symbian host tools the user-side build runs, from the 2010 source,
# unmodified: rcomp (the resource compiler, oss.FCL.sftools.dev.build/bintools/rcomp) and uidcrc (uidcrc.c here).
# Adapted from Phorepoc's toolchain hosttools/build.sh (Copyright The Phorepoc Authors, Apache-2.0).
# rcomp uses the source's own Linux switches (__LINUX__, __TOOLS2__); it is 1990s code that is not 64-bit clean, so
# it is built 32-bit (-m32).
set -eu
SRC=$1
OUT=$2
mkdir -p "$OUT"
R=$SRC/oss.FCL.sftools.dev.build/bintools/rcomp
srcs=""
for f in main.cpp ARRAY.CPP ASTRING.CPP CCODES.CPP CTABLE.CPP DATATYPE.CPP ERRORHAN.CPP FILEACC.CPP FILELINE.CPP \
	INDEXTAB.CPP LINKLIST.CPP MEM.CPP NAMEIDMA.CPP NUMVAL.CPP RCBINSTR.CPP RCOSTRM.CPP RCSCAN.CPP RCSTACK.CPP \
	RESOURCE.CPP STACK.CPP STRINGAR.CPP STRUCTST.CPP UNICODE_COMPRESSOR.CPP localise.cpp QUALIFAR.CPP messages.cpp \
	rcompl.cpp rcomp.cpp; do
	srcs="$srcs $R/src/$f"
done
# shellcheck disable=SC2086
g++ -m32 -O2 -w -fpermissive -D__LINUX__ -D__TOOLS2__ -I"$R/inc" -I"$R/src" -o "$OUT/rcomp" $srcs
gcc -O2 -w -o "$OUT/uidcrc" "$(dirname "$0")/uidcrc.c"
echo "rcomp, uidcrc built"
