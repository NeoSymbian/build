# Copyright The Phorepoc Authors (Phorepoc/pdk tools/features_dat.py); adapted for NeoSymbian/build
# SPDX-License-Identifier: Apache-2.0

"""features_dat -- generate the Feature Manager ROM database Z:\\private\\10205054\\features.dat.

The real ROM build derives it from the feature database; we derive the same facts from
what the 2010 release ships:
  * s60_features.xml        FeatureName (the build macro) <-> UniqueRuntimeId
  * bldvariant.hrh          which of those macros the S60 product variant DEFINES
A feature is `supported` iff its macro is defined by the variant we compile with
(`cpp -dM` over .epoc32/include/bldvariant.hrh) -- so runtime FeatureManager
answers agree with the compile-time #ifdefs in the binaries.

File format (featmgrfeatureregistry.cpp ValidateHeaderL/ReadFileL):
  u32 'feat' | u16 version=1 | u16 flags=0 | u32 nEntries | u32 nDSRs
  nEntries x { u32 uid, u32 flags (bit0 = supported), u32 data }
  nDSRs    x { u32 lowUid, u32 highUid }     (default-supported ranges; >= 1 or the
                                              server panics EPanicNoDSR)

    python3 tools/features_dat.py <out>        (a build step: emitter/features.dat)
"""
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "emitter"))
import mmp as MMP  # noqa: E402

XML = os.path.join(MMP.BASE, "oss.FCL.sf.os.deviceplatformrelease", "foundation_system",
                   "sf_config", "config", "inc", "s60_features.xml")
DSR = [(0x10279806, 0x10281805)]      # the Symbian default supported range
# board facts that override the variant (uid: why)
BOARD_OFF = {
    1638: "KFeatureIdUiTransitionEffects: no transition-effects (TFX) engine here; on, CAknEnv opens the themes TFX settings",
    1718: "KFeatureIdTactileFeedback: no vibra / haptics actuator on Syborg (touchfeedback creates no client when off)",
}


def main(out: str) -> None:
    r = subprocess.run([MMP.CPP, "-undef", "-nostdinc", "-x", "c", "-w", "-dM", "-E",
                        "-I", os.path.join(MMP.EPOC32, "include"),
                        # the case-insensitive fallback the compiles use (tools/casefix.py): bldvariant.hrh includes
                        # "ProductVariant.hrh", exported as productvariant.hrh -- on Linux nothing was defined
                        "-idirafter", os.path.join(MMP.REPO, ".casefix"), MMP.S60_VARIANT_HRH],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        sys.exit("features_dat: the variant headers do not preprocess:\n" + r.stderr[-2000:])
    defined = set(re.findall(r"^#define\s+(\w+)", r.stdout, re.M))
    text = open(XML, encoding="utf-8", errors="replace").read()
    entries = {}
    for spec in re.findall(r"<FeatureSpecification>(.*?)</FeatureSpecification>", text, re.S):
        name = re.search(r"<FeatureName>\s*([^<\s]+)", spec)
        uid = re.search(r"<UniqueRuntimeId>\s*(\d+)", spec)
        if name and uid:
            entries[int(uid.group(1))] = 1 if name.group(1) in defined else 0
    for uid in BOARD_OFF:
        entries[uid] = 0
    blob = struct.pack("<IHHII", 0x74616566, 1, 0, len(entries), len(DSR))
    for uid in sorted(entries):
        blob += struct.pack("<III", uid, entries[uid], 0)
    for lo, hi in DSR:
        blob += struct.pack("<II", lo, hi)
    with open(out, "wb") as fh:
        fh.write(blob)
    print(f"features.dat: {len(entries)} features, {sum(entries.values())} supported, "
          f"{len(DSR)} DSR -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
