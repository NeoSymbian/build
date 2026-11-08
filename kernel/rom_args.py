"""rom_args -- rombuild arguments for every built registry component.

Prints one argument per line (`--xip` / spec / `--data` / spec ...) for kernel/build_rom.sh: every
emitter/components.py entry whose image exists in emitter/, plus the files its build staged for the ROM:
  <image>.romfiles   compiled resources (build_mmp.build_resources)
  <stem>.rsc         ECOM registration next to a plug-in DLL -> \\Resource\\Plugins
  rom_data           the component's own data files ("Z path=repo-relative file", e.g. a Central Repository .txt)
Minigui slot renames: wserv.exe -> EWSRV.EXE (estart launches it), and ECONS.DLL (what Console::NewL loads, e.g. for
ESHELL) = econswserv.dll, a window-server console -- or, in the UI ROM (emitter/rust_rom.args lists SYSSTART.EXE, which
estart runs instead of the window server), econs_twin.dll: the stock text console, served by neoui's Terminal app.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "emitter"))
import components as C  # noqa: E402
import mmp as MMP  # noqa: E402

RUST_ARGS = os.path.join(REPO, "emitter", "rust_rom.args")
UI_ROM = os.path.isfile(RUST_ARGS) and "SYSSTART.EXE" in open(RUST_ARGS).read()
SLOT = {"wserv.exe": "EWSRV.EXE", ("econs_twin.dll" if UI_ROM else "econswserv.dll"): "ECONS.DLL"}


def main() -> None:
    out = []
    seen = set()
    for key, comp in C.COMPONENTS.items():
        targettype = MMP.parse(os.path.join(MMP.BASE, comp["mmp"])).targettype
        rom = C.rom_name(key, targettype)
        img = os.path.join(REPO, "emitter", rom)
        zname = SLOT.get(rom, rom).lower()      # one ROM name once (Z: is case-blind)
        if os.path.isfile(img) and zname not in seen:
            seen.add(zname)
            out += ["--xip", "Sys\\Bin\\" + SLOT.get(rom, rom) + "=emitter/" + rom]
            if targettype == "plugin":
                rsc = os.path.splitext(rom)[0] + ".rsc"
                if os.path.isfile(os.path.join(REPO, "emitter", rsc)):
                    out += ["--data", "Resource\\Plugins\\" + rsc + "=emitter/" + rsc]
            for spec in comp.get("rom_data", []):     # data files the component needs at run time
                out += ["--data", spec]
        man = img + ".romfiles"
        if os.path.isfile(man):
            for line in open(man).read().split():
                out += ["--data", line]
    print("\n".join(out))


if __name__ == "__main__":
    main()
