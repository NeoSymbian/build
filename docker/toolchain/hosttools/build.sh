#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# build.sh <src-root> <out-dir> -- build the Symbian host tools the user-side build runs, from the 2010 source,
# unmodified: rcomp (the resource compiler, oss.FCL.sftools.dev.build/bintools/rcomp), uidcrc (uidcrc.c here), and
# the image tools rofsbuild + readimage (imgtools/romtools; docs/filesystem.md FS4).
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

# rofsbuild and readimage (imgtools/romtools/group/*.mmp source lists), 32-bit like rcomp. They include the e32/f32
# headers (the kernel checkout, hosttools/sources.lock) and boost 1.39: its bundled binaries were built against
# STLport with GCC 4.1, so the four libraries they use are compiled here from the 1.39 release (the Dockerfile fetches
# it, checksum-verified). imgtools-pre.h stands in for Symbian's gcc.h; -D__EABI__ makes the E32 header check expect
# our images' ABI; -D_GLIBCXX__PTHREADS lets boost 1.39's config see the threads.
I=$SRC/oss.FCL.sftools.dev.build/imgtools
L=$I/imglib
RB=$I/romtools/rofsbuild
RI=$I/romtools/readimage
K=$SRC/kernel
B=$SRC/boost_1_39_0
FL="-include $(dirname "$0")/imgtools-pre.h -m32 -O2 -w -fpermissive -std=gnu++98 -D_GLIBCXX_USE_CXX11_ABI=0 \
	-D_GLIBCXX__PTHREADS -D__LINUX__ -D__TOOLS2__ -D__TOOLS__ -D__TOOLS2_LINUX__ -D_STLP_LITTLE_ENDIAN \
	-D__SUPPORT_CPP_EXCEPTIONS__ -D__SUPPORT_ELF_FILES__ -D__EABI__ -DBOOST_ALL_NO_LIB -pthread"
INC="-I$RI/inc -I$I/sisutils/inc -I$L/inc -I$L/compress -I$L/symbolutil -I$L/patchdataprocessor/include \
	-I$L/parameterfileprocessor/include -I$L/memmap/include -I$L/uniconv/include -I$RB/inc -I$RB -I$I/romtools/rombuild \
	-I$B -I$B/boost -I$K/kernel/eka/include -I$K/kernel/eka/include/nkern -I$K/userlibandfileserver/fileserver/inc"
OBJ=$(mktemp -d)
cc() {	# cc <prefix> <sources...>: compile into $OBJ/<prefix>_<name>.o
	p=$1; shift
	for f in "$@"; do
		# shellcheck disable=SC2086
		g++ $FL $INC -c "$f" -o "$OBJ/${p}_$(basename "$f" .cpp).o"
	done
}
cc boost $B/libs/filesystem/src/operations.cpp $B/libs/filesystem/src/path.cpp $B/libs/filesystem/src/portability.cpp \
	$B/libs/system/src/error_code.cpp $B/libs/regex/src/*.cpp $B/libs/thread/src/pthread/*.cpp
COMMON="$L/e32uid/e32uid.cpp $L/host/h_file.cpp $L/host/h_mem.cpp $L/host/h_utl.cpp $L/host/utf16string.cpp \
	$RB/r_build.cpp $RB/r_coreimage.cpp $RB/src/cache/*.cpp $L/e32image/e32image.cpp $L/e32image/deflate/*.cpp \
	$L/compress/byte_pair.cpp $L/compress/pagedcompress.cpp $L/patchdataprocessor/source/patchdataprocessor.cpp \
	$L/uniconv/source/uniconv.cpp"
# shellcheck disable=SC2086
cc common $COMMON
# shellcheck disable=SC2086
cc rofs $RB/r_obey.cpp $RB/r_rofs.cpp $RB/r_driveimage.cpp $RB/r_driveutl.cpp $RB/rofsbuild.cpp $RB/r_smrimage.cpp \
	$RB/fatcluster.cpp $RB/fsnode.cpp $RB/fatimagegenerator.cpp $L/symbolutil/*.cpp \
	$L/parameterfileprocessor/source/*.cpp $L/memmap/source/*.cpp
# shellcheck disable=SC2086
cc ri $RI/src/*.cpp $I/romtools/rombuild/r_global.cpp $I/sisutils/src/*.cpp
g++ -m32 -pthread -o "$OUT/rofsbuild" "$OBJ"/boost_*.o "$OBJ"/common_*.o "$OBJ"/rofs_*.o
g++ -m32 -pthread -o "$OUT/readimage" "$OBJ"/boost_*.o "$OBJ"/common_*.o "$OBJ"/ri_*.o
rm -rf "$OBJ"
echo "rofsbuild, readimage built"
