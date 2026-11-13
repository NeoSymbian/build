# SPDX-License-Identifier: Apache-2.0
"""sis -- install old Symbian .sis packages (SIS v2, Symbian 9) into the build, unpacked on the host.

The packages are not ours (shareware, freeware, GPL builds), so they are never committed: sis.lock names each one by
URL and SHA-256 and this fetches it into .sis-cache/. Installing = unpacking the files the package installs on the
drive the user picks ("!:") or C: onto our C: image, exactly where the 2010 installer would have put them; apparc
finds the app through its private\\10003a3f\\import\\apps\\*_reg.rsc. No signature or hash checks (shortcut: the
on-device installer, SWI, does them; host-side installs trust the lock file's SHA-256 instead).

    python3 tools/sis.py list FILE.sis             the files a package installs
    python3 tools/sis.py imports FILE.exe|.dll     the DLLs an E32 image imports (Deflate images included)
    python3 tools/sis.py install NAME...           (build step) fetch + unpack -> mkfat specs on stdout
    python3 tools/sis.py check NAME... [--rom ARGS]  every import against the ROM: missing DLLs, ordinals past the end
    python3 tools/sis.py --self-test
"""

import hashlib
import os
import struct
import subprocess
import sys
import zlib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = os.path.join(REPO, "sis.lock")
CACHE = os.path.join(REPO, ".sis-cache")

# --- SIS v2 container (Symbian SIS file format: typed fields, 4-byte aligned) ---
SIS_UID1 = 0x10201A7A
T_COMPRESSED, T_INSTALLBLOCK, T_DATA = 3, 28, 30
OP_INSTALL = 1


def _field(b, p, ftype=None):
    if ftype is None:
        ftype = struct.unpack_from("<I", b, p)[0]
        p += 4
    n = struct.unpack_from("<I", b, p)[0]
    p += 4
    if n & 0x80000000:  # 63-bit length
        n = (n & 0x7FFFFFFF) | (struct.unpack_from("<I", b, p)[0] << 31)
        p += 4
    return ftype, b[p : p + n], p + n + (-n % 4)


def _fields(b):
    p = 0
    while p + 8 <= len(b):
        t, d, p = _field(b, p)
        yield t, d


def _payloads(b):
    return [d for _, d in _fields(b)]


def _array(d):
    et, p = struct.unpack_from("<I", d)[0], 4
    while p < len(d):
        _, x, p = _field(d, p, et)
        yield x


def _uncompress(d):
    return zlib.decompress(d[12:]) if struct.unpack_from("<I", d)[0] == 1 else d[12:]


def _install_block(d, conditional, out):
    parts = _payloads(d)
    for fd in _array(parts[0]):
        target = _payloads(fd)[0].decode("utf-16-le")
        op, _, _, length, index = struct.unpack("<IIQQI", fd[-28:])
        out.append(
            {
                "target": target,
                "op": op,
                "length": length,
                "index": index,
                "conditional": conditional,
            }
        )
    for ifd in _array(parts[2]):  # If-blocks (language or device variants)
        _, blk, elses = _payloads(ifd)
        _install_block(blk, True, out)
        for eid in _array(elses):
            _install_block(_payloads(eid)[1], True, out)


def read_sis(b: bytes):
    """-> (files, data): files = [{target, op, length, index, conditional}], data[index] = the file's bytes."""
    if struct.unpack_from("<I", b)[0] != SIS_UID1:
        raise ValueError("not a SIS v2 (Symbian 9) package")
    contents = dict(_fields(_field(b, 16)[1]))
    controller = dict(_fields(_field(_uncompress(contents[T_COMPRESSED]), 0)[1]))
    files = []
    _install_block(controller[T_INSTALLBLOCK], False, files)
    unit = next(
        _array(_payloads(contents[T_DATA])[0])
    )  # data unit 0 = this package (embedded SIS are others)
    data = [_uncompress(_payloads(f)[0]) for f in _array(_payloads(unit)[0])]
    return files, data


def install_path(target: str):
    """'!:\\sys\\bin\\x.exe' -> 'sys/bin/x.exe' on our C:, or None for another drive (E:, the memory card)."""
    drive, _, rest = target.partition(":")
    if drive.upper() not in ("!", "C") or not rest:
        return None
    return rest.replace("\\", "/").lstrip("/")


# --- E32 images (Symbian's own Deflate: f32 sf_inflate.cpp + euser us_decode.cpp, ported) ---
DEFLATE = 0x101F7AFC
_META = [  # us_decode.cpp HuffmanDecoding: the tree for the externalised code lengths
    0x0004006C, 0x00040064, 0x0004005C, 0x00040050, 0x00040044, 0x0004003C, 0x00040034, 0x00040021,
    0x00040023, 0x00040025, 0x00040027, 0x00040029, 0x00040014, 0x0004000C, 0x00040035, 0x00390037,
    0x00330031, 0x0004002B, 0x002F002D, 0x001F001D, 0x001B0019, 0x00040013, 0x00170015, 0x0004000D,
    0x0011000F, 0x000B0009, 0x00070003, 0x00050001,
]  # fmt: skip
LITERALS, LENGTHS, DISTANCES = 256, 28, 44
LITLENS = LITERALS + LENGTHS + 1  # + the end-of-stream code
EOS = LITERALS + LENGTHS
DIST_BASE = 0x200


class _Bits:
    def __init__(self, b: bytes):
        self.b, self.p = b, 0

    def bit(
        self,
    ) -> int:  # MSB first: the 2010 reader byte-reverses little-endian words
        v = (self.b[self.p >> 3] >> (7 - (self.p & 7))) & 1
        self.p += 1
        return v

    def read(self, n: int) -> int:
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v

    def huffman(self, tree) -> int:  # TBitInput::HuffmanL
        i = h = 0
        while True:
            i += (h >> 16) >> 2
            h = tree[i]
            if not self.bit():
                h = (h << 16) & 0xFFFFFFFF
            if h & 0x10000:
                return h >> 17


def _decoding(lengths, base=0):
    """Huffman::Decoding: code lengths -> the decoding tree TBitInput.huffman walks."""
    t = list(lengths)
    counts = [0] * 27
    for n in lengths:
        if n:
            counts[n - 1] += 1
    codes = sum(counts)
    level, lit = [], codes
    for c in counts:
        level.append(lit)
        lit -= c
    sb = (base << 17) + (1 << 16)
    for sym, n in enumerate(lengths):
        if n:
            level[n - 1] -= 1
            t[level[n - 1]] |= (sym << 17) + sb

    def sub(
        ptr, val, lv
    ):  # HuffmanSubTree: indices instead of pointers; *--aPtr = (ptr -= 1; t[ptr] = ...)
        if level[lv] > val:
            s0 = sub(ptr, val, lv + 1)
            ptr = sub(s0, val - (ptr - s0) - 1, lv + 1) - 1
            t[ptr] = (4 << 16) | ((s0 - ptr) * 4)
        elif level[lv] == val:
            term0 = t[val]
            ptr = sub(ptr, val - 1, lv + 1) - 1
            t[ptr] = (4 << 16) | (term0 >> 16)
        else:
            ptr -= 1
            t[ptr] = ((t[val - 1] >> 16) << 16) | (t[val] >> 16)
        return ptr

    if codes == 1:
        t[0] = (t[0] >> 16) | (t[0] & 0xFFFF0000)
    elif codes > 1:
        sub(codes - 1, codes - 1, 0)  # aPtr = aValue = aDecodeTree + codes - 1
    return t


def inflate(data: bytes, size: int) -> bytes:
    bits = _Bits(data)
    lengths, mtf, last, rl = (
        [],
        list(range(28)),
        0,
        0,
    )  # Huffman::InternalizeL: RLE-0 + move-to-front
    total = LITLENS + DISTANCES
    while len(lengths) + rl < total:
        c = bits.huffman(_META)
        if c < 2:
            rl += rl + c + 1
            continue
        lengths += [last] * rl
        rl, c = 0, c - 1
        mtf[0] = last
        last = mtf[c]
        mtf[1 : c + 1] = mtf[0:c]
        lengths.append(last)
    lengths += [last] * (total - len(lengths))
    litlen, dist = _decoding(lengths[:LITLENS]), _decoding(lengths[LITLENS:], DIST_BASE)
    out, tree, run = bytearray(), litlen, 0
    while True:  # CInflater::InflateL
        v = bits.huffman(tree) - LITERALS
        if v < 0:
            out.append(v + LITERALS)
            continue
        if v == EOS - LITERALS:
            break
        code = v & 0xFF
        if code >= 8:
            extra = (code >> 2) - 1
            code = ((code - (extra << 2)) << extra) | bits.read(extra)
        if v < DIST_BASE - LITERALS:
            run, tree = code + 3, dist
            continue
        for _ in range(run):
            out.append(out[-(code + 1)])
        tree = litlen
    if len(out) != size:
        raise ValueError(f"inflate: {len(out)} bytes, the header says {size}")
    return bytes(out)


def e32_image(b: bytes) -> bytes:
    """The image with its code and data uncompressed (header + body), as the loader sees it."""
    if b[16:20] != b"EPOC":
        raise ValueError("not an E32 image")
    kind = struct.unpack_from("<I", b, 0x1C)[0]
    if kind == 0:
        return b
    if kind != DEFLATE:
        raise ValueError(
            f"compression {kind:#x} (byte-pair images: use NeoCFW's e32.py)"
        )
    header = struct.unpack_from("<I", b, 0x64)[0]  # iCodeOffset = the header's length
    return b[:header] + inflate(b[header:], struct.unpack_from("<I", b, 0x7C)[0])


def imports(b: bytes):
    """-> [(dll, [ordinals])] for an ELF-derived E32 image."""
    img = e32_image(b)
    code, imp, n = (struct.unpack_from("<I", img, o)[0] for o in (0x64, 0x6C, 0x54))
    out, p = [], imp + 4
    for _ in range(n):
        name_off, count = struct.unpack_from("<II", img, p)
        name = img[imp + name_off : img.index(b"\0", imp + name_off)].decode()
        # each entry: the code offset of an import word holding the ordinal (low 16 bits)
        ords = [struct.unpack_from("<I", img, code + struct.unpack_from("<I", img, p + 8 + 4 * k)[0])[0] & 0xFFFF
                for k in range(count)]  # fmt: skip
        out.append((name, ords))
        p += 8 + 4 * count
    return out


def base_name(dll: str) -> str:
    """'avkon{000a0000}[100056c6].dll' -> 'avkon.dll'"""
    stem, dot, ext = dll.rpartition(".")
    return stem.split("{")[0].split("[")[0].lower() + dot + ext.lower()


# --- the lock file and the build step ---
def _read(path: str, n: int = -1) -> bytes:
    with open(path, "rb") as fh:
        return fh.read(n)


def lock():
    pkgs = {}
    with open(LOCK) as fh:
        for line in fh:
            line = line.split("#", 1)[0].split()
            if line:
                name, url, sha = line[:3]
                pkgs[name] = (url, sha)
    return pkgs


def fetch(name: str) -> bytes:
    url, sha = lock()[name]
    path = os.path.join(CACHE, name + ".sis")
    if not os.path.isfile(path):
        os.makedirs(CACHE, exist_ok=True)
        # curl: present in the build image and on macOS, whose python.org builds may lack CA certificates
        subprocess.run(
            ["curl", "-fsSL", "--retry", "3", "-o", path + ".part", url], check=True
        )
        os.replace(path + ".part", path)
    b = _read(path)
    if hashlib.sha256(b).hexdigest() != sha:
        raise SystemExit(
            f"sis: {name}: SHA-256 mismatch for {path} (delete it to refetch)"
        )
    return b


def install(names, out_dir):
    """Unpack each package under out_dir/<name>/ -> mkfat specs 'C-path=host-path'."""
    specs = []
    for name in names:
        files, data = read_sis(fetch(name))
        for f in files:
            dst = install_path(f["target"]) if f["op"] == OP_INSTALL else None
            if dst is None or f["conditional"]:
                print(
                    f"sis: {name}: skipped {f['target'] or '(text)'}", file=sys.stderr
                )
                continue
            host = os.path.join(out_dir, name, dst)
            os.makedirs(os.path.dirname(host), exist_ok=True)
            with open(host, "wb") as fh:
                fh.write(data[f["index"]])
            specs.append(f"{dst}={os.path.relpath(host, REPO)}")
    return specs


def rom_dlls(rom_args: str):
    """{dll name: export count} for every image the ROM carries (kernel/build_rom.sh's rombuild.args)."""
    out = {}
    args = _read(rom_args).decode().split("\n")
    for spec in args:
        if "=" not in spec or not spec.lower().startswith("sys\\bin\\"):
            continue
        name, path = spec.split("=", 1)
        full = os.path.join(REPO, path)
        try:
            img = _read(full, 0x60)
            out[name.rsplit("\\", 1)[1].lower()] = struct.unpack_from("<I", img, 0x5C)[
                0
            ]
        except OSError:
            pass
    return out


def check(names, rom_args):
    rom = rom_dlls(rom_args)
    bad = 0
    for name in names:
        files, data = read_sis(fetch(name))
        own = {os.path.basename(f["target"]).lower() for f in files}
        for f in files:
            if (
                not f["target"].lower().endswith((".exe", ".dll"))
                or f["op"] != OP_INSTALL
            ):
                continue
            for dll, ords in imports(data[f["index"]]):
                d = base_name(dll)
                top = max(ords, default=0)
                if d in own:
                    status = "package"
                elif d not in rom:
                    status, bad = "MISSING", bad + 1
                elif top > rom[d]:
                    status, bad = f"ORDINAL {top} > {rom[d]} exports", bad + 1
                else:
                    status = "ok"
                print(
                    f"{name}: {os.path.basename(f['target'])} -> {d} ({len(ords)}, max {top}): {status}"
                )
    return bad


def self_test():
    # a hand-made SIS: one file, !:\sys\bin\t.exe
    def fld(t, body):
        return struct.pack("<II", t, len(body)) + body + b"\0" * (-len(body) % 4)

    def arr(et, items):
        return fld(2, struct.pack("<I", et) + b"".join(struct.pack("<I", len(x)) + x + b"\0" * (-len(x) % 4) for x in items))  # fmt: skip

    target = "!:\\sys\\bin\\t.exe".encode("utf-16-le")
    fd = fld(1, target) + struct.pack("<IIQQI", OP_INSTALL, 0, 5, 5, 0)
    block = fld(28, arr(23, [fd]) + arr(29, []) + arr(31, []))
    ctl = fld(9, block)
    comp = fld(T_COMPRESSED, struct.pack("<IQ", 0, len(ctl)) + ctl)
    unit = arr(39, [fld(T_COMPRESSED, struct.pack("<IQ", 0, 5) + b"hello")])
    data = fld(T_DATA, arr(38, [unit]))
    sis = struct.pack("<IIII", SIS_UID1, 0, 0, 0) + fld(12, comp + data)
    files, blobs = read_sis(sis)
    assert [(f["target"], f["index"]) for f in files] == [("!:\\sys\\bin\\t.exe", 0)], (
        files
    )
    assert blobs[0] == b"hello" and install_path(files[0]["target"]) == "sys/bin/t.exe"
    assert install_path("e:\\data\\x") is None
    assert base_name("avkon{000a0000}[100056c6].dll") == "avkon.dll"
    # the 2010 constant tree for the meta code (29 symbols) must come out of our Huffman::Decoding port
    meta_lengths = [0] * 29

    def walk(i, depth):
        for half in (_META[i] & 0xFFFF, _META[i] >> 16):
            if half & 1:
                meta_lengths[half >> 1] = depth + 1
            else:
                walk(i + (half >> 2), depth + 1)

    walk(0, 0)
    assert _decoding(meta_lengths)[: len(_META)] == _META, (
        "Huffman::Decoding port"
    )  # n codes -> n-1 nodes
    print("sis self-test: ok")


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "--self-test":
        self_test()
    elif a[0] == "list":
        for f in read_sis(_read(a[1]))[0]:
            print(
                f"#{f['index']:<3} {f['length']:>9} {f['target']}{'  (conditional)' if f['conditional'] else ''}"
            )
    elif a[0] == "imports":
        for dll, ords in imports(_read(a[1])):
            print(
                f"{base_name(dll):28} {len(ords):4} imports, max ordinal {max(ords, default=0)}"
            )
    elif a[0] == "install":
        print("\n".join(install(a[1:], os.path.join(REPO, ".sis-build"))))
    elif a[0] == "check":
        rom = (
            a[a.index("--rom") + 1]
            if "--rom" in a
            else os.path.join(REPO, ".ekern-build", "rombuild.args")
        )
        names = [x for x in a[1:] if x != "--rom" and x != rom]
        sys.exit(1 if check(names, rom) else 0)
    else:
        sys.exit(f"sis: unknown command {a[0]}")


if __name__ == "__main__":
    main()
