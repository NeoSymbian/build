# SPDX-License-Identifier: Apache-2.0
"""mif -- Avkon's icon file (avkon2.mif) with NeoSymbian's own icons, as bitmap entries.

The release has no avkon2.mif (the platform icons were never opened), so every Avkon icon lookup -- the Uikon server's
first note, softkeys, list markers -- fails. This writes one in the 2010 MIF layout (uiresources AknIconLoader.h):
    file header  {0x34232342, version 2, offset of the index, index length}
    index        {offset, length} per MIF id (bitmap and mask ids both point at the icon)
    icon         TMifIconHeader {0x34232343, 1, data offset 32, data length, type, depth, animated, mask depth} + data
Entries are bitmaps (type EIconFormatBMP), drawn by the icon server's CAknBmpFormatHandler (our uiresources fork):
    "NBMP", width (u16), height (u16), width*height pixels 0xAARRGGBB
Every id of avkon.mbg gets an entry: one transparent placeholder shared by all, and our drawings for the icons ART
names (by their avkon.mbg name, qgn_...).

    python3 tools/mif.py [out]          (a build step; default emitter/avkon2.mif)
    python3 tools/mif.py --self-test
"""

import os
import re
import struct
import sys

from rombuild import uid_checksum  # the UID checksum (TCheckedUid)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MBG = os.path.join(REPO, ".epoc32", "include", "avkon.mbg")
OUT = os.path.join(REPO, "emitter", "avkon2.mif")
FILE_UID, ICON_UID = 0x34232342, 0x34232343
MIF_FIRST = 16384
BMP = 0  # mifconvdefs.h EIconFormatBMP
COLOR16MU, GRAY256 = 11, 4  # TDisplayMode


def icon(width: int, height: int, pixels: list[int]) -> bytes:
    """An icon entry: the TMifIconHeader plus our bitmap data."""
    data = (
        b"NBMP"
        + struct.pack("<HH", width, height)
        + struct.pack(f"<{len(pixels)}I", *pixels)
    )
    return (
        struct.pack("<8i", ICON_UID, 1, 32, len(data), BMP, COLOR16MU, 0, GRAY256)
        + data
    )


def draw(size: int, shade) -> list[int]:
    """size x size pixels from shade(x, y) -> 0xAARRGGBB (coordinates in 0..1)."""
    return [
        shade((x + 0.5) / size, (y + 0.5) / size)
        for y in range(size)
        for x in range(size)
    ]


def disc(colour: int):
    """A filled circle: notes' status marks, radio buttons."""
    return lambda x, y: colour if (x - 0.5) ** 2 + (y - 0.5) ** 2 <= 0.2 else 0


# Our drawings, by avkon.mbg name. Simple flat shapes; the rest of Avkon's ids show nothing (the placeholder).
ART = {
    "qgn_note_info": disc(0xFF3B82F6),
    "qgn_note_error": disc(0xFFEF4444),
    "qgn_note_warning": disc(0xFFF59E0B),
    "qgn_note_ok": disc(0xFF22C55E),
    "qgn_note_query": disc(0xFF6366F1),
    "qgn_indi_marked_add": disc(0xFF22C55E),
}


def mbg_ids(path: str) -> dict[str, int]:
    """{qgn_... name: bitmap id} from avkon.mbg (EMbmAvkonQgn_note_info = 16384, ...)."""
    with open(path, encoding="latin-1") as fh:
        text = fh.read()
    ids = {}
    for m in re.finditer(r"EMbmAvkon(\w+?)\s*=\s*(\d+)", text):
        name, value = m.group(1), int(m.group(2))
        if value >= MIF_FIRST and not name.endswith("_mask"):
            ids[name.lower()] = value
    return ids


def mif(ids: dict[str, int], count: int = 0) -> bytes:
    """count: at least this many entries (the rest of a skin's ids show the placeholder too)."""
    count = max(count, (max(ids.values()) - MIF_FIRST + 2) if ids else 0)
    blobs = [icon(1, 1, [0])]  # 0: the transparent placeholder
    where = [0] * count
    for name, value in ids.items():
        if name in ART:
            where[value - MIF_FIRST] = where[value - MIF_FIRST + 1] = len(blobs)
            blobs.append(icon(24, 24, draw(24, ART[name])))
    index_at = 16
    data_at = index_at + 8 * count
    offsets, pos = [], data_at
    for b in blobs:
        offsets.append((pos, len(b)))
        pos += len(b)
    index = b"".join(struct.pack("<II", *offsets[w]) for w in where)
    return struct.pack("<4i", FILE_UID, 2, index_at, count) + index + b"".join(blobs)


def mbm(count: int) -> bytes:
    """A multi-bitmap file (.mbm, a direct file store: UIDs KDirectFileStoreLayoutUid + KMultiBitmapFileImageUid, the
    root stream = the trailer {count, offsets}) whose COUNT bitmaps are all one 1x1 8-bit grey pixel of 0: an empty
    bitmap, and as a mask fully transparent. For a skin's bitmap ids (below 16384) that have no artwork."""
    uids = (0x10000037, 0x10000042, 0)
    head = struct.pack("<3I", *uids) + struct.pack("<I", uid_checksum(*uids))
    pixel_at = len(head) + 4
    # SEpocBitmapHeader: size (header + data), header size, width, height, twips w/h, bpp, colour (0 grey), palette, compression
    pixel = struct.pack("<10i", 40 + 4, 40, 1, 1, 15, 15, 8, 0, 0, 0) + b"\0" * 4  # one scanline, 4-byte aligned
    trailer_at = pixel_at + len(pixel)
    trailer = struct.pack(f"<{count + 1}I", count, *([pixel_at] * count))
    return head + struct.pack("<I", trailer_at) + pixel + trailer


def self_test() -> None:
    m = mbm(3)
    assert struct.unpack_from("<4I", m) == (0x10000037, 0x10000042, 0, uid_checksum(0x10000037, 0x10000042, 0))
    at = struct.unpack_from("<I", m, 16)[0]
    assert struct.unpack_from("<4I", m, at) == (3, 20, 20, 20) and struct.unpack_from("<2i", m, 20) == (44, 40)
    blob = mif({"qgn_note_info": 16384, "qgn_other": 16386})
    uid, version, at, n = struct.unpack_from("<4i", blob)
    assert (uid, version, at, n) == (FILE_UID, 2, 16, 4)
    entries = [struct.unpack_from("<II", blob, at + 8 * i) for i in range(n)]
    assert (
        entries[0] == entries[1]
        and entries[2] == entries[3]
        and entries[0] != entries[2]
    )
    assert struct.unpack_from("<4i", mif({}, 6))[3] == 6
    off, length = entries[0]
    hdr = struct.unpack_from("<8i", blob, off)
    assert hdr[0] == ICON_UID and hdr[4] == BMP and hdr[3] == length - 32
    assert blob[off + 32 : off + 36] == b"NBMP" and struct.unpack_from(
        "<HH", blob, off + 36
    ) == (24, 24)
    print("mif self-test: ok")


def main() -> None:
    if sys.argv[1:] == ["--self-test"]:
        self_test()
        return
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    ids = mbg_ids(MBG)
    with open(out, "wb") as fh:
        fh.write(mif(ids))
    drawn = sum(1 for n in ids if n in ART)
    print(
        f"mif: {os.path.relpath(out, REPO)}: {len(ids)} Avkon icons, {drawn} drawn, the rest transparent"
    )


if __name__ == "__main__":
    main()
