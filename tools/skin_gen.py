# SPDX-License-Identifier: Apache-2.0
"""skin_gen -- compile the S60 default skin package (series60skin, PID 101f84b9) for the skin server.

Avkon cannot run without a skin: the skin server (aknskinsrv) merges one at start-up, and with none on Z: it fails
("Skin not found") and the UI server with it. The release builds the default skin from the descriptor
skins/AknSkinContent/srcdata/scalableseries60skin/scalableseries60skin.txt with Nokia's skin descriptor compiler; we
build that compiler for the host from its 2010 source (skins/AknSkins/sdcsrc, under the S60 variant flags, as the
Windows build was) and run it the same way.

Artwork: the descriptor names ~2400 SVGs from the platform icon delivery, which is NOT in the open release. The
compiler drops an item whose file is missing, so the skin keeps its colours, frames' layout and the rest. ART (our own
drawn artwork, named as the descriptor's items) is staged in their place as it is made.

    python3 tools/skin_gen.py       (a build step) -> emitter/skin/series60skin.skn
"""

import os
import re
import shutil
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKINS = os.path.join(REPO, "src", "oss.FCL.sf.mw.uiresources", "skins")
SRC = os.path.join(
    SKINS,
    "AknSkinContent",
    "srcdata",
    "scalableseries60skin",
    "scalableseries60skin.txt",
)
SDC = os.path.join(SKINS, "AknSkins")
COMPILER = os.path.join(REPO, ".host", "akn_skin_desc_compiler")
ART = os.path.join(
    REPO, "toolchain", "skin-art"
)  # ours: <item>.bmp / .svg named as the descriptor's items
WORK = os.path.join(REPO, ".skin-gen")
OUT = os.path.join(REPO, "emitter", "skin")
INC = os.path.join(REPO, ".epoc32", "include")


def build_compiler() -> None:
    if os.path.isfile(COMPILER):
        return
    os.makedirs(os.path.dirname(COMPILER), exist_ok=True)
    srcs = sorted(
        os.path.join(SDC, "sdcsrc", f)
        for f in os.listdir(os.path.join(SDC, "sdcsrc"))
        if f.endswith(".cpp")
    )
    forced = [
        a for h in ("cstring", "ctime", "cstdlib", "cstdio") for a in ("-include", h)
    ]
    subprocess.run(
        [
            "g++",
            "-std=gnu++98",
            "-fpermissive",
            "-w",
            "-O1",
            *forced,
            "-I",
            INC,
            "-idirafter",
            os.path.join(REPO, ".casefix"),
            "-include",
            os.path.join(INC, "bldvariant.hrh"),  # RD_ENHANCED_SKINNING, RD_SCALABLE_UI
            "-I",
            os.path.join(SDC, "sdcinc"),
            "-I",
            os.path.join(SDC, "inc"),
            "-I",
            os.path.join(INC, "mw"),
            "-o",
            COMPILER,
            *srcs,
        ],
        check=True,
    )
    print(f"skin_gen: built {os.path.relpath(COMPILER, REPO)}")


def main() -> None:
    build_compiler()
    shutil.rmtree(WORK, ignore_errors=True)
    icons = os.path.join(WORK, "src", "icons")
    os.makedirs(icons)
    for d in ("list", "out"):
        os.makedirs(os.path.join(WORK, d))
    if os.path.isdir(ART):
        for f in os.listdir(ART):
            shutil.copy(os.path.join(ART, f), icons)
    with open(SRC, "rb") as fh:
        text = fh.read().decode("utf-16")
    # every BITMAPPATH (Windows paths into the icon delivery) -> the staged artwork
    text = re.sub(r"(?im)^(\s*BITMAPPATH\s+)\S+", r"\g<1>icons/", text)
    with open(os.path.join(WORK, "src", "skin.txt"), "wb") as fh:
        fh.write(b"\xff\xfe" + text.encode("utf-16-le"))
    r = subprocess.run(
        [COMPILER, "-m../list/", "-t../out/", "skin.txt", "series60skin"],
        cwd=os.path.join(WORK, "src"),
        capture_output=True,
        check=False,
        text=True,
        errors="replace",
    )
    dropped = r.stdout.count("not add")
    if r.returncode or not os.path.isfile(
        os.path.join(WORK, "out", "series60skin.skn")
    ):
        raise SystemExit(
            "skin_gen: the skin compiler failed:\n" + r.stdout[-2000:] + r.stderr[-500:]
        )
    os.makedirs(OUT, exist_ok=True)
    shutil.copy(os.path.join(WORK, "out", "series60skin.skn"), OUT)
    print(
        f"skin_gen: series60skin.skn {os.path.getsize(os.path.join(OUT, 'series60skin.skn'))} B, "
        f"{dropped} items without artwork"
    )


if __name__ == "__main__":
    main()
