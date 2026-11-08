# SPDX-License-Identifier: Apache-2.0
# images.sh -- the Docker images every NeoSymbian build runs in, pinned by digest (sourced by build.sh, boot.sh, neo).
# docker/toolchain -> .github/workflows/toolchain.yml publishes; NeoSymbian/symbian-qemu publishes its own (image.yml).
# To move a pin: run the workflow, take the digest from its summary, change it here.
BUILD_IMAGE="${BUILD_IMAGE:-ghcr.io/neosymbian/toolchain@sha256:bac4fb83afdfad083138c48365974df9256b29901ea56798c78a4f955ce8d3b2}"
QEMU_IMAGE="${QEMU_IMAGE:-ghcr.io/neosymbian/symbian-qemu@sha256:0650a1151f4e5e8e27b01809ed2bd78590468a4b5cfe35ae0918979d5ad0b4cc}"
