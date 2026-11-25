# SPDX-License-Identifier: Apache-2.0
# images.sh -- the Docker image every NeoSymbian build runs in, pinned by digest (sourced by build.sh, neo).
# docker/toolchain -> .github/workflows/toolchain.yml publishes.
# To move a pin: run the workflow, take the digest from its summary, change it here.
BUILD_IMAGE="${BUILD_IMAGE:-ghcr.io/neosymbian/toolchain@sha256:71f91f8ca42c5456859c3477092bef4f69842f6521ba1a4b5554ac7835895b32}"
