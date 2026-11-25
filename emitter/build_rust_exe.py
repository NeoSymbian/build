"""build_rust_exe -- NeoSymbian: Symbian EXEs whose logic is a Rust staticlib (NeoSymbian/e32-rs).

Builds every EXE listed in rust/exes.txt, one per line (blank lines and # comments ignored):

    <NAME.EXE> <uid3> <lib.a> [glue.cpp] [drive=c] [stack=BYTES] [heap=BYTES] [libs=libc,libpthread,...] [caps=A,B]

<lib.a> is relative to rust/, built for ARMv8-A AArch32 softfp (e32-rs targets/armv8a-neosymbian-eabi.json, or its std
twin armv8a-symbian-eabi.json; US4); `-` links no Rust at all (a C++-only test program that
needs its glue file, e.g. e32-rs's IPC client copied to rust/neocli.cpp). Without a glue file the Rust library
defines E32Main itself (e32-rs `e32::main!`); with one (R0's toolchain/rust/neo_glue.cpp) the C++ glue does. Each is linked with the
EXE start-up runtime (uc_exe.cia, dev_exe_startup.cpp, gcchelp.cpp, crt_shim.cpp), import veneers from the frozen
.def files and the E32Image writer, as in build_eshell_exe.py. Writes emitter/<name>, emitter/rust_rom.args (the
--xip lines scripts/build-user-manifest.sh adds to the ROM) and emitter/rust_cdrive.args (the drive=c EXEs, for the C: drive
image: Sys/Bin/<NAME>=emitter/<name>.exe per line). An optional rust/data.txt adds plain files to the ROM, one
`<Z: path>=<file under rust/>` per line (e.g. `Resource\\NeoWeb\\Fonts\\DejaVuSans.ttf=fonts/DejaVuSans.ttf`): the
browser's fonts and pages. `stack=` sets the main thread's stack (default 128 KB, for Slint;
both kernels take up to 1 MB: Syborg's multiple memory model refused more than 80 KB before kernel 9641bd04).
`libs=` names more DLLs to import from, as an mmp's LIBRARY (any registered component with a frozen .def, e.g. P.I.P.S.'s
libc, libpthread, libm: browser/wb2-std.md WB2); the glue then also sees P.I.P.S.'s headers (epoc32/include/stdapis).
`heap=` sets the most the EXE's own heap may grow to (default 1 MB). A Rust EXE with std needs it: std's allocator is
P.I.P.S.'s malloc on that heap (e32's chunk heap is off under std; docs browser/wb2-std.md, WB2c).
`caps=` gives a drive=c EXE capabilities by name (e.g. NetworkServices for sockets); ROM EXEs get all of them anyway.

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
# 128 KB stack: Slint builds and lays out a page recursively; SYSSTART overflowed 32 KB opening Settings -> Display
# (KERN-EXEC 3 on the phone, 2026-11-11)
STACK_SIZE, HEAP_MIN, HEAP_MAX = 0x20000, 0x1000, 0x100000

ENTRY_NAME = "_E32Startup"
EE = os.path.join(REPO, "toolchain", "efile_exe")

RUNTIME_SOURCES = [
    os.path.join(BE.B, "euser", "epoc", "arm", "uc_exe.cia"),
    os.path.join(EE, "dev_exe_startup.cpp"),
    os.path.join(BE.B, "common", "gcchelp.cpp"),
    os.path.join(EE, "crt_shim.cpp"),
]
GLUE_FLAGS = [f"-I{os.path.join(SRC, 'kernel', 'eka', 'include')}"]
# with libs=: P.I.P.S. (Open C) headers; they mark float functions __SOFTFP (RVCT's __softfp), ours is softfp already
STDAPIS = os.path.join(REPO, ".epoc32", "include", "stdapis")
PIPS_FLAGS = [f"-I{STDAPIS}", f"-I{os.path.join(REPO, '.epoc32', 'include')}", "-D__SOFTFP="]


def _symcc(src: str, obj: str, flags: list[str]) -> str:
    env = dict(os.environ, SYMCC_ARM="1")
    subprocess.run(
        ["bash", BE.SYMCC, src, "-O2", *flags, "-o", obj], check=True, env=env, cwd=REPO
    )
    return obj


def _registrations(lib: str | None) -> list[str]:
    """The inventory crate's constructor statics (`__CTOR`, global) defined in the Rust staticlib."""
    if not lib:
        return []
    return sorted(n for n in BE._nm("--defined-only", lib) if n.endswith("___CTOR") or n.endswith("__CTORE"))


def _link(
    objs: list[str], lib: str | None, out_elf: str, ignore_unresolved: bool
) -> None:
    args = [
        BE.GCC,
        "-nostdlib",
        "-Wl,-q",
        "-Wl,--gc-sections",
        # long-branch veneers PC-relative: a `bl` reaches +-32 MB, and ld's absolute veneers carry an address -q
        # never emits a relocation for (an EXE over 32 MB, NEOWEBE, jumped to its unrelocated ELF address)
        "-Wl,--pic-veneer",
        "-Wl,--no-demangle",
        # Rust objects say 4-byte wchar_t (Tag_ABI_PCS_wchar_t); no wchar_t crosses into Symbian code
        "-Wl,--no-wchar-size-warning",
        f"-Wl,-u,{ENTRY_NAME}",
        f"-Wl,-T,{LD_SCRIPT}",
        *BE.GNU_ARCH,
        *objs,
        # inventory's registrations (Servo's resource reader...): a constructor in .init_array whose object no symbol
        # pulls from the staticlib; rustc keeps such #[used] statics with its symbols.o, this link must name them
        *[f"-Wl,-u,{n}" for n in _registrations(lib)],
        *([lib] if lib else []),
        BE._libgcc(),
        "-o",
        out_elf,
    ]
    if ignore_unresolved:
        args.insert(1, "-Wl,--unresolved-symbols=ignore-all")
    subprocess.run(args, check=True)


def _weak_undefined(elf: str) -> set[str]:
    """The weak undefined symbols of `elf` (nm's `w`/`v`)."""
    out = subprocess.run([BE.NM, "--undefined-only", elf], check=True, capture_output=True, text=True).stdout
    return {p[-1] for p in (line.split() for line in out.splitlines()) if len(p) >= 2 and p[-2] in ("w", "v")}


# TCapability bit numbers (e32capability.h), for caps= of drive=c EXEs (ROM EXEs get every capability from rombuild)
CAPABILITIES = (
    "TCB CommDD PowerMgmt MultimediaDD ReadDeviceData WriteDeviceData DRM TrustedUI ProtServ DiskAdmin NetworkControl "
    "AllFiles SwEvent NetworkServices LocalServices ReadUserData WriteUserData Location SurroundingsDD UserEnvironment"
).split()


def parse_caps(text: str) -> int:
    """caps=NetworkServices,ReadUserData -> the image header's first capability word."""
    names = {c.lower(): i for i, c in enumerate(CAPABILITIES)}
    bits = 0
    for c in filter(None, text.split(",")):
        if c.lower() not in names:
            raise ValueError(f"unknown capability {c!r}")
        bits |= 1 << names[c.lower()]
    return bits


def parse_manifest(
    path: str,
) -> list[tuple[str, int, str | None, str | None, str, int, list[str], int, int]]:
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
        stack = int(opts.pop("stack", str(STACK_SIZE)), 0)
        libs = [x for x in opts.pop("libs", "").split(",") if x]
        heap = int(opts.pop("heap", str(HEAP_MAX)), 0)
        try:
            caps = parse_caps(opts.pop("caps", ""))
        except ValueError as e:
            sys.exit(f"{path}:{n}: {e}")
        if len(f) < 3 or len(rest) > 1 or opts or drive not in ("z", "c") or heap < HEAP_MIN:
            sys.exit(
                f"{path}:{n}: want <NAME.EXE> <uid3> <lib.a> [glue.cpp] [drive=c] [stack=BYTES] [heap=BYTES] [libs=a,b] [caps=A,B]"
            )
        name, uid3 = f[0], int(f[1], 0)
        lib = None if f[2] == "-" else os.path.join(RUST_DIR, f[2])
        stem, _, ext = name.partition(".")
        if not (0 < len(stem) <= 8 and ext.upper() == "EXE"):
            sys.exit(f"{path}:{n}: {name}: want an 8.3 .EXE name")
        if lib and not os.path.isfile(lib):
            sys.exit(f"{path}:{n}: {lib} missing")
        glue = os.path.join(REPO, rest[0]) if rest else None
        if not (lib or glue):
            sys.exit(f"{path}:{n}: {name}: no Rust library (-) needs a glue file")
        exes.append((name.upper(), uid3, lib, glue, drive, stack, libs, heap, caps))
    if len({e[1] for e in exes}) != len(exes):
        sys.exit(f"{path}: duplicate uid3")
    return exes


def build_one(
    name: str,
    uid3: int,
    lib: str | None,
    glue: str | None,
    runtime: list[str],
    stack: int = STACK_SIZE,
    libs: list[str] | None = None,
    heap: int = HEAP_MAX,
    caps: int = 0,
) -> bool:
    stem = name.split(".")[0].lower()
    workdir = BE.workdir("rust_" + stem)
    objs = list(runtime)
    if glue:
        objs.append(
            _symcc(
                glue,
                os.path.join(workdir, os.path.basename(glue) + ".o"),
                GLUE_FLAGS + (PIPS_FLAGS if libs else []),
            )
        )

    elf1 = os.path.join(workdir, stem + ".pass1.elf")
    _link(objs, lib, elf1, ignore_unresolved=True)
    # weak references (aws-lc's optional OPENSSL_memory_* hooks) are not imports: ld makes them 0 in pass 2
    undefined = sorted(BE._nm("--undefined-only", elf1) - {""} - _weak_undefined(elf1))
    imports, unmapped = devlink.split_missing(undefined, own_dll=stem + ".exe")
    dll_order = [devlink.EUSER_DLL, devlink.EFSRV_DLL, devlink.HAL_DLL, devlink.EFILE_EXE]
    if libs and unmapped:
        # the extra DLLs, resolved from their frozen .def files as an mmp's LIBRARY list is (euser keeps its names)
        import build_mmp

        extra, roms = build_mmp.provider_maps(libs)
        data = sorted(n for n in unmapped if n in extra and n in build_mmp.DATA_EXPORTS)
        if data:
            # shortcut: function imports only (each import is a code veneer); add data imports when one is needed
            sys.exit(f"{name}: DATA imports not supported: {', '.join(data)}")
        imports.update({n: extra[n] for n in unmapped if n in extra})
        unmapped = [n for n in unmapped if n not in extra]
        dll_order += [r for r in roms if r not in dll_order]
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

    import_list = devlink.import_blocks(ext, imports, dll_order=tuple(dll_order))
    n_imp = sum(len(e) for _, e in import_list)
    print(
        f"{name} uid3=0x{uid3:08X} "
        + (
            "(C++ only)"
            if not lib
            else f"({'C++ glue + ' if glue else ''}Rust {os.path.basename(lib)})"
        )
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
        stack_size=stack,
        heap_min=HEAP_MIN,
        heap_max=heap,
        cap1=caps,
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


def data_lines(path: str) -> list[str]:
    """rust/data.txt as --data lines for the ROM: `<Z: path>=<file under rust/>` per line (# comments, blanks)."""
    if not os.path.isfile(path):
        return []
    out = []
    with open(path) as fh:
        for n, line in enumerate(fh, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if any(ord(c) < 32 for c in line):
                raise SystemExit(f"{path}:{n}: a control character (an echo that read \\f as an escape?)")
            z, sep, src = line.partition("=")
            if not sep or not z.strip() or not src.strip() or os.path.isabs(src.strip()) or ".." in src:
                raise SystemExit(f"{path}:{n}: want <Z: path>=<file under rust/>")
            if not os.path.isfile(os.path.join(os.path.dirname(path), src.strip())):
                raise SystemExit(f"{path}:{n}: no file rust/{src.strip()}")
            out.append(f"--data\n{z.strip()}=rust/{src.strip()}\n")
    return out


def main() -> int:
    manifest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RUST_DIR, "exes.txt")
    exes = parse_manifest(manifest)
    rtdir = BE.workdir("rust_runtime")
    runtime = [
        _symcc(s, os.path.join(rtdir, os.path.basename(s) + ".o"), [])
        for s in RUNTIME_SOURCES
    ]
    results = [  # build every EXE even when one fails its check
        build_one(name, uid3, lib, glue, runtime, stack, libs, heap, caps)
        for name, uid3, lib, glue, _, stack, libs, heap, caps in exes
    ]
    ok = all(results)

    def img(name: str) -> str:
        return f"emitter/{name.split('.')[0].lower()}.exe"

    rom = [n for n, _, _, _, d, *_ in exes if d == "z"]
    cdrive = [n for n, _, _, _, d, *_ in exes if d == "c"]
    with open(ROM_ARGS, "w") as fh:
        fh.writelines(f"--xip\nSys\\Bin\\{n}={img(n)}\n" for n in rom)
        fh.writelines(data_lines(os.path.join(RUST_DIR, "data.txt")))
    with open(CDRIVE_ARGS, "w") as fh:
        fh.writelines(f"Sys/Bin/{n}={img(n)}\n" for n in cdrive)
    print(f"{ROM_ARGS}: {len(rom)} EXEs in the ROM; {CDRIVE_ARGS}: {len(cdrive)} on C:")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
