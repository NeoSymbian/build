# NeoSymbian build

The build system of [NeoSymbian](https://github.com/NeoSymbian): one command, `neo`, builds and runs everything in one
pinned image.

| | |
|---|---|
| `neo fetch`, `neo rom` | The 2010 Symbian user side as ARMv8-A AArch32, with the Rust programs and UI from [e32-rs](https://github.com/NeoSymbian/e32-rs) and [neoui](https://github.com/NeoSymbian/neoui) |
| `neo kernel BOARD`, `neo nkernsa BOARD`, `neo qemu`, `neo flash BOARD` | The AArch64 kernel from [kernel](https://github.com/NeoSymbian/kernel) (checked out beside this repo) with that user side, for a board (`qemu`, `bonito`), on QEMU virt or the phone |
| `images.sh` | The build image (`docker/toolchain`, `ghcr.io/neosymbian/toolchain`), pinned by digest |
| `zimaos/` | The home-server build desktop |

This repository started as Phorepoc's `symbian-2010`: the 2010 Symbian open-source release, built from its own source
with a modern compiler and booted in the Symbian QEMU (Syborg), with nothing in the Symbian source edited, in the
stripped-down **minigui** setup Symbian used to bring up new hardware. NeoSymbian builds that user side for ARMv8-A
AArch32 and runs it on its own AArch64 kernel (the phone, QEMU virt); it adds the Rust EXEs and the Rust UI on top
(`rust/`, `emitter/build_rust_exe.py`). The Syborg kernel and ROM were dropped on 2026-11-25 (their 2010 kernel can't
run the ARMv8 user side).

![Where it started: the Symbian text shell in minigui on QEMU Syborg](docs/minigui-eshell.png)

## Quick start

You'll need Docker, git, about 4 GB of disk, and [kernel](https://github.com/NeoSymbian/kernel) checked out as
`../kernel` (`neo` finds it there; `KERNEL=` points elsewhere). It works on Linux, macOS and Windows, since the build always runs
inside the NeoSymbian build image ([docker/toolchain](docker/toolchain), published as `ghcr.io/neosymbian/toolchain`).

```sh
./neo fetch          # download the source into src/
./neo rom            # build the user side (out/c_drive.img, out/e32-hashes.txt; the ROM list stays in the build volume)
./neo kernel qemu    # the AArch64 kernel with that user side (needs ../kernel), then
./neo qemu 60        # boot it on QEMU virt
```

The first build takes a few minutes on a big machine, or up to 20 on a laptop. After that only what changed gets
rebuilt, and `FULL=1 ./build.sh` starts from scratch. Every step logs to `out/log/`.

### Named builds

Each phone image can have a name: a date plus an invented animal, e.g. `2026-11-20-otterfox` (`./neo name` suggests
a new one).
- `NAME=… ./neo rom` puts the name first in the ROM's build line, which Settings → About phone shows.
- It also writes `out/manifest.txt` with the commit of every repo that went in: this repo, the `sources.lock` pins,
  and the Rust repos listed in `rust/revs.txt` (one `repo commit` line each; whoever copies the staticlibs writes it).
- `./neo kernel` adds the kernel commit and the image flags, in the kernel's `out/ekern-<board>/manifest.txt`.
- When a build is installed, commit that file as `releases/<name>.txt`.
- `./neo diff NAME1 NAME2` then lists, per repo, the commits between the two and their GitHub compare link.

`out/e32-hashes.txt` lists every E32 image the build made (sha256, size, name); `tools/e32_hashes.py compare A B`
checks two builds byte for byte, and `neo kernel` writes the board's own `user/e32-manifest.txt`. The CI builds the
user side and the qemu kernel, runs fshell on QEMU virt, and keeps the logs and `e32-hashes.txt`.

## How it works

The source isn't stored here. `sources.lock` pins the 13 Symbian packages the build needs, and `fetch.sh` downloads
them from our mirrors.

The release was written for Nokia's ARM compiler, RVCT, and a build tool called `elf2e32` that doesn't exist for
modern compilers. So we compile with today's GCC 14, and our own scripts in `emitter/` turn each compiled ELF file into
a Symbian E32Image, using the import and export tables frozen in the release's `.def` files.
`scripts/build-user-manifest.sh` lists what goes into Z:, and the kernel's `rombuild.py` packs it into the image.

The source also assumes a case-insensitive file system, with includes like `<f32plugin.h>` that only exist as
`F32plugin.h`. Rather than rename anything, `tools/casefix.py` adds links for every spelling the source uses.

## What we had to add

We didn't edit any Symbian file, but a modern compiler and a board with no real hardware need a few things added next
to the source:

- **Compiler glue.** `toolchain/symbian_gcc_prefix.h` defines what the release's own compiler headers expected but GCC
  doesn't provide. Two small header overlays fix code that modern GCC treats differently. One is `TRAP`, which returns
  twice and has to be marked so, or locals get lost across a leave.
- **Compiler flags.** The release depends on how RVCT and old GCC behaved, so we turn off a few modern optimisations,
  such as `-fno-strict-aliasing` and `-fno-delete-null-pointer-checks`. Each one has its reason in `toolchain/symcc`
  and `emitter/build_mmp.py`.
- **Runtime pieces** in `toolchain/dll_rt/` and `toolchain/efile_exe/` start up DLLs and programs the way the old
  toolchain's runtime did.
- **Two stand-ins.** The graphics resource and surface update libraries are replaced with empty versions, because the
  emulator has no GPU and no compositor. Tracing is turned off, since the trace compiler wasn't part of the release.

Everything else, including the window server and the screen driver, is built unmodified from its own `.mmp` file.

## Finding your way around

```
fetch.sh, sources.lock   the source, pinned
neo, build.sh            build in the toolchain image (neo: and the kernel, QEMU virt, the phone)
scripts/                 what runs inside the container, the Z: file list
kernel/                  the file server's objects (build_efile.sh), the ROM's component list (rom_args.py)
emitter/                 the .mmp reader, the component list, ELF to E32Image
toolchain/               compiler driver, prefix header, overlays, runtime pieces
tools/                   header export, FAT image, build names, E32 hashes
```

## License

EPL-1.0, the license of the Symbian release. The downloaded source keeps its own license headers.
