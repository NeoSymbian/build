"""build_rust_exe -- NeoSymbian R0: a Symbian EXE whose logic is a Rust staticlib (NeoSymbian/e32-rs).

toolchain/rust/neo_glue.cpp holds E32Main and neo_debug_print (RDebug); the Rust library (RUST_LIB, default
rust/librust_hello.a, built for armv5te-none-eabi) provides rust_hello. Same runtime, two-pass link, import
veneers and E32Image writer as build_eshell_exe.py, which this is a copy of. uid3 0xE0001001 (test range).

Run from repo root:  RUST_LIB=rust/librust_hello.a python3 emitter/build_rust_exe.py [out.exe]
"""

from __future__ import annotations

import os
import subprocess
import sys

import build_euser_dll as BE
import devlink
from e32image import build_dll
from elf import extract
from refcheck import check_image, format_result

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LD_SCRIPT = os.path.join(HERE, "efile.ld")

SRC = os.path.join(REPO, "src", "oss.FCL.sf.os.kernelhwsrv")
UID2, UID3 = 0, 0xE0001001
STACK_SIZE, HEAP_MIN, HEAP_MAX = 0x8000, 0x1000, 0x100000

ENTRY_NAME = "_E32Startup"
EE = os.path.join(REPO, "toolchain", "efile_exe")

ESHELL_SOURCES = [os.path.join(REPO, "toolchain", "rust", "neo_glue.cpp")]
RUST_LIB = os.path.abspath(
    os.environ.get("RUST_LIB", os.path.join(REPO, "rust", "librust_hello.a"))
)
RUNTIME_SOURCES = [
    os.path.join(BE.B, "euser", "epoc", "arm", "uc_exe.cia"),
    os.path.join(EE, "dev_exe_startup.cpp"),
    os.path.join(BE.B, "common", "gcchelp.cpp"),
    os.path.join(EE, "crt_shim.cpp"),
]

ESHELL_FLAGS = [f"-I{os.path.join(SRC, 'kernel', 'eka', 'include')}"]


def _compile(workdir: str) -> list[str]:
    env = dict(os.environ, SYMCC_ARM="1")
    objs = []
    for src in ESHELL_SOURCES:
        obj = os.path.join(workdir, "rust_" + os.path.basename(src) + ".o")
        subprocess.run(
            ["bash", BE.SYMCC, src, "-O2", *ESHELL_FLAGS, "-o", obj],
            check=True,
            env=env,
            cwd=REPO,
        )
        objs.append(obj)
    for src in RUNTIME_SOURCES:
        obj = os.path.join(workdir, "rustrt_" + os.path.basename(src) + ".o")
        subprocess.run(
            ["bash", BE.SYMCC, src, "-O2", "-o", obj], check=True, env=env, cwd=REPO
        )
        objs.append(obj)
    return objs


def _link(objs: list[str], out_elf: str, ignore_unresolved: bool) -> None:
    args = [
        BE.GCC,
        "-nostdlib",
        "-Wl,-q",
        "-Wl,--gc-sections",
        "-Wl,--no-demangle",
        f"-Wl,-u,{ENTRY_NAME}",
        f"-Wl,-T,{LD_SCRIPT}",
        "-march=armv5te",
        "-marm",
        "-Wl,-u,rust_hello",
        *objs,
        RUST_LIB,
        BE._libgcc(),
        "-o",
        out_elf,
    ]
    if ignore_unresolved:
        args.insert(1, "-Wl,--unresolved-symbols=ignore-all")
    subprocess.run(args, check=True)


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "neohello.exe")
    workdir = BE.workdir("neohello")

    objs = _compile(workdir)

    elf1 = os.path.join(workdir, "neohello.pass1.elf")
    _link(objs, elf1, ignore_unresolved=True)
    undefined = sorted(BE._nm("--undefined-only", elf1) - {""})

    imports, unmapped = devlink.split_missing(undefined, own_dll="neohello.exe")
    if unmapped:
        sys.exit("imports with NO ordinal provider:\n  " + "\n  ".join(unmapped))

    veneer_obj = devlink.make_veneers(workdir, imports, "neohello")
    elf2 = os.path.join(workdir, "neohello.elf")
    _link(objs + [veneer_obj], elf2, ignore_unresolved=False)
    with open(elf2, "rb") as fh:
        ext = extract(fh.read())

    if ENTRY_NAME not in ext.symbols:
        sys.exit(f"required symbol {ENTRY_NAME!r} not in ELF")

    import_list = devlink.import_blocks(ext, imports)
    n_imp = sum(len(e) for _, e in import_list)
    print(f"NEOHELLO.EXE (C++ glue + Rust staticlib {RUST_LIB})")
    print(
        f"code: {len(ext.code)} B @0x{ext.code_base:X}   "
        f"data: {len(ext.data)} B   bss: {ext.bss_size} B"
    )
    print(
        f"imports: {n_imp} across {len(import_list)} DLLs  ("
        + ", ".join(f"{dll} {len(e)}" for dll, e in import_list)
        + ")"
    )

    img = build_dll(
        ext.code,
        [],
        exe=True,
        uid2=UID2,
        uid3=UID3,
        entry_point=ext.symbols[ENTRY_NAME] - ext.code_base,
        stack_size=STACK_SIZE,
        heap_min=HEAP_MIN,
        heap_max=HEAP_MAX,
        imports=import_list,
        code_relocs=ext.code_relocs,
        code_base=ext.code_base,
        data=ext.data,
        data_base=ext.data_base,
        bss_size=ext.bss_size,
        data_relocs=ext.data_relocs,
        code_reloc_types=ext.code_reloc_types,
        data_reloc_types=ext.data_reloc_types,
    )
    with open(out_path, "wb") as fh:
        fh.write(img)
    print(f"\nWrote {out_path} ({len(img)} bytes)")
    result = check_image(img)
    print(format_result(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
