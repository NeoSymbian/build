# SPDX-License-Identifier: Apache-2.0
# images.sh -- the Docker images every NeoSymbian build runs in, pinned by digest (sourced by build.sh, boot.sh, neo).
# docker/toolchain -> .github/workflows/toolchain.yml publishes; NeoSymbian/symbian-qemu publishes its own (image.yml).
# To move a pin: run the workflow, take the digest from its summary, change it here.
BUILD_IMAGE="${BUILD_IMAGE:-ghcr.io/neosymbian/toolchain@sha256:71f91f8ca42c5456859c3477092bef4f69842f6521ba1a4b5554ac7835895b32}"
QEMU_IMAGE="${QEMU_IMAGE:-ghcr.io/neosymbian/symbian-qemu@sha256:96a35e14fc5fa0855f3cc37c87bc6c91520401dc1ecc24fb2b1d2acb5e601df5}"
