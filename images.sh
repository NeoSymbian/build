# SPDX-License-Identifier: Apache-2.0
# images.sh -- the Docker images every NeoSymbian build runs in, pinned by digest (sourced by build.sh, boot.sh, neo).
# docker/toolchain -> .github/workflows/toolchain.yml publishes; NeoSymbian/qemu-syborg publishes its own.
# To move a pin: run the workflow, take the digest from its summary, change it here.
BUILD_IMAGE="${BUILD_IMAGE:-ghcr.io/neosymbian/toolchain@sha256:bac4fb83afdfad083138c48365974df9256b29901ea56798c78a4f955ce8d3b2}"
QEMU_IMAGE="${QEMU_IMAGE:-ghcr.io/neosymbian/qemu-syborg@sha256:72a0ee417a1c908f87d33590d0ec12b99cf63d67df2dea875895a589012adbaa}"
