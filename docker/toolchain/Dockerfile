# SPDX-License-Identifier: Apache-2.0
# toolchain -- the NeoSymbian build image, for both halves of the system:
#  - the AArch64 kernel (NeoSymbian/kernel, baseport/arm64/tools): aarch64 GCC 14 (-mabi=ilp32), QEMU (virt),
#    Python with PIL and the DejaVu fonts (the phone console's font)
#  - the 2010 ARMv5TE user side (this repo's build.sh): the Arm GNU Toolchain 14.2.rel1 (arm-none-eabi, checksum-
#    verified; its binutils also assemble the kernel's AArch32 test program), host gcc/cpp, perl, python3, and the
#    Symbian host tools rcomp and uidcrc, built from source in the first stage
# Build context = this folder:  docker build -t neosymbian-toolchain docker/toolchain
# Published by .github/workflows/toolchain.yml as ghcr.io/neosymbian/toolchain; build.sh pins it by digest.

FROM debian:trixie-slim AS hosttools
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git g++ g++-multilib \
    && rm -rf /var/lib/apt/lists/*
COPY hosttools/ /hosttools/
RUN set -eu; grep -v '^#' /hosttools/sources.lock | while IFS="$(printf '\t')" read -r pkg commit; do \
        git init -q "/src/$pkg"; \
        git -C "/src/$pkg" fetch -q --depth 1 "https://github.com/NeoSymbian/$pkg.git" "$commit"; \
        git -C "/src/$pkg" checkout -q FETCH_HEAD; \
    done \
    && sh /hosttools/build.sh /src /opt/symbian-hosttools

FROM debian:trixie-slim
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y --no-install-recommends \
        gcc-14-aarch64-linux-gnu g++-14-aarch64-linux-gnu binutils-aarch64-linux-gnu qemu-system-arm \
        build-essential libc6:i386 libstdc++6:i386 \
        python3 python3-pil fonts-dejavu-core perl file xxd gzip zip ca-certificates curl xz-utils git \
    && rm -rf /var/lib/apt/lists/*
ARG ARM_GNU=arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi
ARG ARM_GNU_SHA256=62a63b981fe391a9cbad7ef51b17e49aeaa3e7b0d029b36ca1e9c3b2a9b78823
RUN curl -fsSL -o /tmp/arm.tar.xz \
        "https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/${ARM_GNU}.tar.xz" \
    && echo "${ARM_GNU_SHA256}  /tmp/arm.tar.xz" | sha256sum -c - \
    && mkdir -p /opt/arm-gnu && tar -xJf /tmp/arm.tar.xz -C /opt/arm-gnu --strip-components=1 \
    && rm -rf /tmp/arm.tar.xz /opt/arm-gnu/share/doc
COPY --from=hosttools /opt/symbian-hosttools /opt/symbian-hosttools
ENV PATH=/opt/arm-gnu/bin:/opt/symbian-hosttools:$PATH \
    CROSS=aarch64-linux-gnu-
LABEL org.opencontainers.image.source=https://github.com/NeoSymbian/build \
      org.opencontainers.image.description="NeoSymbian build image: AArch64 kernel + 2010 ARM user side" \
      org.opencontainers.image.licenses=Apache-2.0
WORKDIR /work
