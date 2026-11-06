"""build_rust_exe -- NeoSymbian: Symbian EXEs whose logic is a Rust staticlib (NeoSymbian/e32-rs).

Builds every EXE listed in rust/exes.txt, one per line (blank lines and # comments ignored):

    <NAME.EXE> <uid3> <lib.a> [glue.cpp] [drive=c]

<lib.a> is relative to rust/, built for armv5te-none-eabi. Without a glue file the Rust library defines E32Main
itself (e32-rs `e32::main!`); with one (R0's toolchain/rust/neo_glue.cpp) the C++ glue does. Each is linked with the
EXE start-up runtime (uc_exe.cia, dev_exe_startup.cpp, gcchelp.cpp, crt_shim.cpp), import veneers from the frozen
.def files and the E32Image writer, as in build_eshell_exe.py. Writes emitter/<name>, emitter/rust_rom.args (the
--xip lines kernel/build_rom.sh adds to the ROM) and emitter/rust_cdrive.args (the drive=c EXEs, for the C: drive
image: Sys/Bin/<NAME>=emitter/<name>.exe per line).

Run from repo root:  python3 emitter/build_rust_exe.py [manifest]
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
RUST_DIR = os.path.join(REPO, "rust")
ROM_ARGS = os.path.join(HERE, "rust_rom.args")
CDRIVE_ARGS = os.path.join(HERE, "rust_cdrive.args")

SRC = os.path.join(REPO, "src", "oss.FCL.sf.os.kernelhwsrv")
UID2 = 0
STACK_SIZE, HEAP_MIN, HEAP_MAX = 0x8000, 0x1000, 0x100000

ENTRY_NAME = "_E32Startup"
EE = os.path.join(REPO, "toolchain", "efile_exe")

RUNTIME_SOURCES = [
    os.path.join(BE.B, "euser", "epoc", "arm", "uc_exe.cia"),
    os.path.join(EE, "dev_exe_startup.cpp"),
    os.path.join(BE.B, "common", "gcchelp.cpp"),
    os.path.join(EE, "crt_shim.cpp"),
]
GLUE_FLAGS = [f"-I{os.path.join(SRC, 'kernel', 'eka', 'include')}"]


def _symcc(src: str, obj: str, flags: list[str]) -> str:
    env = dict(os.environ, SYMCC_ARM="1")
    subprocess.run(
        ["bash", BE.SYMCC, src, "-O2", *flags, "-o", obj], check=True, env=env, cwd=REPO
    )
    return obj


def _link(objs: list[str], lib: str, out_elf: str, ignore_unresolved: bool) -> None:
    args = [
        BE.GCC,
        "-nostdlib",
        "-Wl,-q",
        "-Wl,--gc-sections",
        "-Wl,--no-demangle",
        # Rust objects say 4-byte wchar_t (Tag_ABI_PCS_wchar_t); no wchar_t crosses into Symbian code
        "-Wl,--no-wchar-size-warning",
        f"-Wl,-u,{ENTRY_NAME}",
        f"-Wl,-T,{LD_SCRIPT}",
        "-march=armv5te",
        "-marm",
        *objs,
        lib,
        BE._libgcc(),
        "-o",
        out_elf,
    ]
    if ignore_unresolved:
        args.insert(1, "-Wl,--unresolved-symbols=ignore-all")
    subprocess.run(args, check=True)


def parse_manifest(path: str) -> list[tuple[str, int, str, str | None, str]]:
    exes = []
    with open(path) as fh:
        lines = fh.read().splitlines()
    for n, line in enumerate(lines, 1):
        f = line.split("#", 1)[0].split()
        if not f:
            continue
        opts = dict(t.split("=", 1) for t in f[3:] if "=" in t)
        rest = [t for t in f[3:] if "=" not in t]
        drive = opts.pop("drive", "z").lower()
        if len(f) < 3 or len(rest) > 1 or opts or drive not in ("z", "c"):
            sys.exit(f"{path}:{n}: want <NAME.EXE> <uid3> <lib.a> [glue.cpp] [drive=c]")
        name, uid3, lib = f[0], int(f[1], 0), os.path.join(RUST_DIR, f[2])
        stem, _, ext = name.partition(".")
        if not (0 < len(stem) <= 8 and ext.upper() == "EXE"):
            sys.exit(f"{path}:{n}: {name}: want an 8.3 .EXE name")
        if not os.path.isfile(lib):
            sys.exit(f"{path}:{n}: {lib} missing")
        glue = os.path.join(REPO, rest[0]) if rest else None
        exes.append((name.upper(), uid3, lib, glue, drive))
    if len({e[1] for e in exes}) != len(exes):
        sys.exit(f"{path}: duplicate uid3")
    return exes


def build_one(
    name: str, uid3: int, lib: str, glue: str | None, runtime: list[str]
) -> bool:
    stem = name.split(".")[0].lower()
    workdir = BE.workdir("rust_" + stem)
    objs = list(runtime)
    if glue:
        objs.append(
            _symcc(
                glue, os.path.join(workdir, os.path.basename(glue) + ".o"), GLUE_FLAGS
            )
        )

    elf1 = os.path.join(workdir, stem + ".pass1.elf")
    _link(objs, lib, elf1, ignore_unresolved=True)
    undefined = sorted(BE._nm("--undefined-only", elf1) - {""})
    imports, unmapped = devlink.split_missing(undefined, own_dll=stem + ".exe")
    if unmapped:
        sys.exit(
            f"{name}: imports with NO ordinal provider:\n  " + "\n  ".join(unmapped)
        )

    veneer_obj = devlink.make_veneers(workdir, imports, stem)
    elf2 = os.path.join(workdir, stem + ".elf")
    _link(objs + [veneer_obj], lib, elf2, ignore_unresolved=False)
    with open(elf2, "rb") as fh:
        ext = extract(fh.read())
    if ENTRY_NAME not in ext.symbols:
        sys.exit(f"{name}: required symbol {ENTRY_NAME!r} not in ELF")

    import_list = devlink.import_blocks(ext, imports)
    n_imp = sum(len(e) for _, e in import_list)
    print(
        f"{name} uid3=0x{uid3:08X} ({'C++ glue + ' if glue else ''}Rust {os.path.basename(lib)})"
    )
    print(
        f"  code: {len(ext.code)} B @0x{ext.code_base:X}   data: {len(ext.data)} B   bss: {ext.bss_size} B"
    )
    print(
        f"  imports: {n_imp} across {len(import_list)} DLLs  ("
        + ", ".join(f"{dll} {len(e)}" for dll, e in import_list)
        + ")"
    )

    img = build_dll(
        ext.code,
        [],
        exe=True,
        uid2=UID2,
        uid3=uid3,
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
    out_path = os.path.join(HERE, stem + ".exe")
    with open(out_path, "wb") as fh:
        fh.write(img)
    result = check_image(img)
    print(f"  wrote {out_path} ({len(img)} bytes)  {format_result(result)}")
    return result.ok


def main() -> int:
    manifest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RUST_DIR, "exes.txt")
    exes = parse_manifest(manifest)
    rtdir = BE.workdir("rust_runtime")
    runtime = [
        _symcc(s, os.path.join(rtdir, os.path.basename(s) + ".o"), [])
        for s in RUNTIME_SOURCES
    ]
    results = [  # build every EXE even when one fails its check
        build_one(name, uid3, lib, glue, runtime) for name, uid3, lib, glue, _ in exes
    ]
    ok = all(results)

    def img(name: str) -> str:
        return f"emitter/{name.split('.')[0].lower()}.exe"

    rom = [n for n, *_, d in exes if d == "z"]
    cdrive = [n for n, *_, d in exes if d == "c"]
    with open(ROM_ARGS, "w") as fh:
        fh.writelines(f"--xip\nSys\\Bin\\{n}={img(n)}\n" for n in rom)
    with open(CDRIVE_ARGS, "w") as fh:
        fh.writelines(f"Sys/Bin/{n}={img(n)}\n" for n in cdrive)
    print(f"{ROM_ARGS}: {len(rom)} EXEs in the ROM; {CDRIVE_ARGS}: {len(cdrive)} on C:")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
