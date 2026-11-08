# SPDX-License-Identifier: Apache-2.0
# toolchain -- the NeoSymbian build image, for both halves of the system:
#  - the AArch64 kernel (NeoSymbian/kernel, baseport/arm64/tools): aarch64 GCC 14 (-mabi=ilp32), QEMU (virt),
#    Python with PIL and the DejaVu fonts (the phone console's font)
#  - the 2010 ARMv5TE user side (this repo's build.sh): the Arm GNU Toolchain 14.2.rel1 (arm-none-eabi, checksum-
#    verified; its binutils also assemble the kernel's AArch32 test program), host gcc/cpp, perl, python3, and the
#    Symbian host tools rcomp, uidcrc, rofsbuild and readimage, built from source in the first stage
# Build context = this folder:  docker build -t neosymbian-toolchain docker/toolchain
# Published by .github/workflows/toolchain.yml as ghcr.io/neosymbian/toolchain; build.sh pins it by digest.

FROM debian:trixie-slim AS hosttools
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git g++ g++-multilib curl bzip2 \
    && rm -rf /var/lib/apt/lists/*
# boost 1.39 sources for rofsbuild/readimage (hosttools/build.sh): the release tarball, checksum-verified
ARG BOOST_SHA256=44785eae8c6cce61a29a8a51f9b737e57b34d66baa7c0bcd4af188832b8018fd
RUN curl -fsSL -o /tmp/boost.tar.bz2 https://archives.boost.io/release/1.39.0/source/boost_1_39_0.tar.bz2 \
    && echo "${BOOST_SHA256}  /tmp/boost.tar.bz2" | sha256sum -c - \
    && mkdir -p /src && tar -xjf /tmp/boost.tar.bz2 -C /src boost_1_39_0/boost boost_1_39_0/libs/filesystem/src \
        boost_1_39_0/libs/system/src boost_1_39_0/libs/regex/src boost_1_39_0/libs/thread/src \
    && rm /tmp/boost.tar.bz2
COPY hosttools/ /hosttools/
RUN set -eu; grep -v '^#' /hosttools/sources.lock | while IFS="$(printf '\t')" read -r pkg commit; do \
        git init -q "/src/$pkg"; \
        git -C "/src/$pkg" fetch -q --depth 1 "https://github.com/NeoSymbian/$pkg.git" "$commit"; \
        git -C "/src/$pkg" checkout -q FETCH_HEAD; \
    done \
    && sh /hosttools/build.sh /src /opt/symbian-hosttools

FROM debian:trixie-slim
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y --no-install-recommends \
        gcc-14-aarch64-linux-gnu g++-14-aarch64-linux-gnu binutils-aarch64-linux-gnu \
        build-essential libc6:i386 libstdc++6:i386 \
        python3 python3-pil fonts-dejavu-core perl file xxd gzip zip ca-certificates curl xz-utils git \
        libglib2.0-0t64 libpixman-1-0 libfdt1 zlib1g \
    && rm -rf /var/lib/apt/lists/*
ARG ARM_GNU=arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi
ARG ARM_GNU_SHA256=62a63b981fe391a9cbad7ef51b17e49aeaa3e7b0d029b36ca1e9c3b2a9b78823
RUN curl -fsSL -o /tmp/arm.tar.xz \
        "https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/${ARM_GNU}.tar.xz" \
    && echo "${ARM_GNU_SHA256}  /tmp/arm.tar.xz" | sha256sum -c - \
    && mkdir -p /opt/arm-gnu && tar -xJf /tmp/arm.tar.xz -C /opt/arm-gnu --strip-components=1 \
    && rm -rf /tmp/arm.tar.xz /opt/arm-gnu/share/doc
COPY --from=hosttools /opt/symbian-hosttools /opt/symbian-hosttools
# QEMU (qemu-system-aarch64 for the kernel's virt runs, qemu-system-arm with the Syborg board): the same build as
# ghcr.io/neosymbian/symbian-qemu, pinned like images.sh's QEMU_IMAGE, so both streams use one QEMU.
COPY --from=ghcr.io/neosymbian/symbian-qemu@sha256:96a35e14fc5fa0855f3cc37c87bc6c91520401dc1ecc24fb2b1d2acb5e601df5 \
     /opt/symbian-qemu /opt/symbian-qemu
ENV PATH=/opt/arm-gnu/bin:/opt/symbian-hosttools:/opt/symbian-qemu/bin:$PATH \
    CROSS=aarch64-linux-gnu-
LABEL org.opencontainers.image.source=https://github.com/NeoSymbian/build \
      org.opencontainers.image.description="NeoSymbian build image: AArch64 kernel + 2010 ARM user side" \
      org.opencontainers.image.licenses=Apache-2.0
WORKDIR /work
