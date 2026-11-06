"""dtb_screen -- NeoSymbian: set the Syborg screen size in a compiled board description (.dtb).

The QEMU Syborg framebuffer takes its size from the `width`/`height` properties of the `framebuffer@0` node
(baseport/syborg/syborg.dts: 0x300 x 0x280 = 768x640), and the Symbian driver (svpframebuffer.cpp) reads it back from
the device registers and sizes video RAM to match. So a different screen -- e.g. the Pixel 3a XL's 1080x2160 -- is
just two 32-bit values in the .dtb. The QEMU image has no dtc, so this edits the flattened tree in place (same sizes,
nothing moves) and reads it back to check.

    python3 tools/dtb_screen.py IN.dtb OUT.dtb 1080x2160
"""

from __future__ import annotations

import struct
import sys

FDT_MAGIC = 0xD00DFEED
BEGIN_NODE, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9


def _props(dtb: bytes, node_prefix: str):
    """Yield (name, value offset, length) of the properties directly in nodes whose name starts with node_prefix."""
    magic, _total, off_struct, off_strings = struct.unpack_from(">IIII", dtb, 0)
    if magic != FDT_MAGIC:
        raise ValueError("not a flattened device tree")
    pos, path = off_struct, []
    while True:
        (tok,) = struct.unpack_from(">I", dtb, pos)
        pos += 4
        if tok == BEGIN_NODE:
            end = dtb.index(b"\0", pos)
            path.append(dtb[pos:end].decode())
            pos = (end + 1 + 3) & ~3
        elif tok == END_NODE:
            path.pop()
        elif tok == PROP:
            length, nameoff = struct.unpack_from(">II", dtb, pos)
            pos += 8
            name_end = dtb.index(b"\0", off_strings + nameoff)
            name = dtb[off_strings + nameoff : name_end].decode()
            if path and path[-1].startswith(node_prefix):
                yield name, pos, length
            pos = (pos + length + 3) & ~3
        elif tok == NOP:
            continue
        elif tok == END:
            return
        else:
            raise ValueError(f"bad FDT token {tok} at {pos - 4}")


def screen(dtb: bytes) -> tuple[int, int]:
    vals = {
        n: struct.unpack_from(">I", dtb, o)[0]
        for n, o, ln in _props(dtb, "framebuffer")
        if n in ("width", "height") and ln == 4
    }
    return vals["width"], vals["height"]


def set_screen(dtb: bytes, width: int, height: int) -> bytes:
    out = bytearray(dtb)
    seen = set()
    for name, off, length in _props(dtb, "framebuffer"):
        if name in ("width", "height") and length == 4:
            struct.pack_into(">I", out, off, width if name == "width" else height)
            seen.add(name)
    if seen != {"width", "height"}:
        raise ValueError(f"framebuffer width/height not found (got {sorted(seen)})")
    out = bytes(out)
    assert screen(out) == (width, height), screen(out)
    return out


def main() -> int:
    if len(sys.argv) != 4 or "x" not in sys.argv[3]:
        sys.exit("usage: dtb_screen.py IN.dtb OUT.dtb WIDTHxHEIGHT")
    w, h = (int(v) for v in sys.argv[3].lower().split("x"))
    if not (16 <= w <= 4096 and 16 <= h <= 4096):
        sys.exit("screen size out of range")
    with open(sys.argv[1], "rb") as fh:
        dtb = fh.read()
    before = screen(dtb)
    with open(sys.argv[2], "wb") as fh:
        fh.write(set_screen(dtb, w, h))
    print(f"{sys.argv[2]}: framebuffer {before[0]}x{before[1]} -> {w}x{h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
