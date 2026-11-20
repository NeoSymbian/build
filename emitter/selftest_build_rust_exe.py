#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""exes.txt caps= parsing: python3 emitter/selftest_build_rust_exe.py (no ARM tools)."""
import build_rust_exe as R

assert R.parse_caps("") == 0
assert R.parse_caps("NetworkServices") == 1 << 13
assert R.parse_caps("networkservices,ReadUserData") == (1 << 13) | (1 << 15)
assert R.CAPABILITIES[0] == "TCB" and R.CAPABILITIES[19] == "UserEnvironment"
try:
    R.parse_caps("Bogus")
    raise SystemExit("unknown capability accepted")
except ValueError:
    pass
print("selftest ok: caps=")
