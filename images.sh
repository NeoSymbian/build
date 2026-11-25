# SPDX-License-Identifier: Apache-2.0
# images.sh -- the Docker image every NeoSymbian build runs in, pinned by digest (sourced by build.sh, neo).
# docker/toolchain -> .github/workflows/toolchain.yml publishes.
# To move a pin: run the workflow, take the digest from its summary, change it here.
BUILD_IMAGE="${BUILD_IMAGE:-ghcr.io/neosymbian/toolchain@sha256:f3d5b92390d5968915a56c10e6ab239a50299ba5658bd3cff52339b0d68f59e6}"
