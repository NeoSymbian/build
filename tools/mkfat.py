"""mkfat -- build a FAT16 "superfloppy" image (no MBR) pre-populated with files.

The Syborg non-volatile memory device backs drive C: with one raw image
(<qemu cwd>/nvmemory/syborg_system.img; syborg.dts: drive_size 0x4000000, 512-byte
sectors) and the media driver exposes the WHOLE image as a single FAT16
partition at offset 0 (syborg_mednvmemory.cpp PartitionInfo). This writes such
an image so C: boots with content -- e.g. fonts on a NON-ROM drive, which makes
fntstore take its RAM path like a real (NAND) phone does.

    python3 tools/mkfat.py out.img  'Resource/Fonts/ceurope.gdr=path/to/CEUROPE.GDR' [...]
        [--size 0x4000000]

8.3 names are stored upper-cased as plain entries; any other name (long, mixed
case beyond 8.3, spaces...) gets VFAT long-name entries plus a NAME~N.EXT alias,
as Windows and F32's sl_vfat.cpp write them. Directories are created as needed.

    python3 tools/mkfat.py --self-test
"""
import struct, sys, time

SECTOR = 512


_OK83 = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$%'-_@~`!(){}^#&")


def _is83(name):
    base, dot, ext = name.upper().partition(".")
    return (0 < len(base) <= 8 and len(ext) <= 3 and "." not in ext and (ext or not dot)
            and set(base + ext) <= _OK83)


def _name83(name):
    base, _, ext = name.upper().partition(".")
    return base.ljust(8).encode("ascii") + ext.ljust(3).encode("ascii")


def _alias(name, taken):
    """The NAME~N.EXT short alias of a long name, unique among `taken` (11-byte names)."""
    base, dot, ext = name.upper().rpartition(".") if "." in name.strip(".") else (name.upper(), "", "")
    clean = lambda t: "".join(ch if ch in _OK83 else "_" for ch in t.replace(" ", "").replace(".", ""))
    base, ext = clean(base) or "_", clean(ext)[:3]
    for n in range(1, 1000000):
        tail = f"~{n}"
        short = (base[:8 - len(tail)] + tail).ljust(8).encode("ascii") + ext.ljust(3).encode("ascii")
        if short not in taken:
            return short
    raise SystemExit("mkfat: no free alias")


def _lfn_checksum(short):
    s = 0
    for b in short:
        s = (((s & 1) << 7) + (s >> 1) + b) & 0xFF
    return s


def _lfn_slots(name, short):
    """The VFAT entries for `name`, in on-disk order (last slot first)."""
    units = list(name.encode("utf-16-le"))
    chars = [units[i] | units[i + 1] << 8 for i in range(0, len(units), 2)]
    if len(chars) > 255:
        raise SystemExit(f"mkfat: '{name}' is longer than 255 characters")
    n = (len(chars) + 12) // 13
    chars += [0x0000] if len(chars) < n * 13 else []
    chars += [0xFFFF] * (n * 13 - len(chars))
    ck = _lfn_checksum(short)
    out = []
    for seq in range(n, 0, -1):
        c = chars[(seq - 1) * 13:seq * 13]
        out.append(struct.pack("<B5HBBB6HH2H", seq | (0x40 if seq == n else 0), *c[0:5],
                               0x0F, 0, ck, *c[5:11], 0, *c[11:13]))
    return out


class Fat16:
    def __init__(self, size):
        self.total = size // SECTOR
        self.spc = 4                                  # 2 KB clusters
        self.reserved, self.nfats, self.root_ents = 1, 2, 512
        root_secs = self.root_ents * 32 // SECTOR
        data_guess = self.total - self.reserved - root_secs
        clusters = data_guess // self.spc
        self.fatsz = ((clusters + 2) * 2 + SECTOR - 1) // SECTOR
        self.first_data = self.reserved + self.nfats * self.fatsz + root_secs
        self.clusters = (self.total - self.first_data) // self.spc
        assert 4085 <= self.clusters < 65525, "not a FAT16 geometry"
        self.img = bytearray(size)
        self.fat = [0] * (self.clusters + 2)
        self.fat[0], self.fat[1] = 0xFFF8, 0xFFFF
        self.next_free = 2
        self.root = bytearray(self.root_ents * 32)
        self.dirs = {"": None}                        # upper-cased path -> (cluster | None for root)
        self.shorts = {None: set()}                   # dir cluster -> the 11-byte short names in it
        self.dir_data = {}                            # cluster -> bytearray

    def _alloc(self, nbytes):
        n = max(1, (nbytes + self.spc * SECTOR - 1) // (self.spc * SECTOR))
        first = self.next_free
        for i in range(n):
            c = self.next_free
            self.next_free += 1
            self.fat[c] = c + 1 if i < n - 1 else 0xFFFF
        return first, n

    def _cluster_off(self, c):
        return (self.first_data + (c - 2) * self.spc) * SECTOR

    def _entry(self, short, attr, cluster, size):
        t = time.localtime()
        dt = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
        tm = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
        return short + struct.pack("<BBBHHHHHHHI", attr, 0, 0, tm, dt, dt, 0, tm, dt,
                                   cluster, size)

    def _add_entry(self, parent, name, attr, cluster, size):
        taken = self.shorts[parent]
        if _is83(name):
            short, slots = _name83(name), []
            if short in taken:
                raise SystemExit(f"mkfat: '{name}' already exists")
        else:
            short = _alias(name, taken)
            slots = _lfn_slots(name, short)
        taken.add(short)
        ents = slots + [self._entry(short, attr, cluster, size)]
        buf = self.root if parent is None else self.dir_data[parent]
        need = 32 * len(ents)
        for off in range(0, len(buf) - need + 1, 32):
            if not any(buf[o] for o in range(off, off + need, 32)):    # a run of free entries
                buf[off:off + need] = b"".join(ents)
                return
        raise SystemExit("mkfat: directory full")

    def mkdir(self, path):
        if path.upper() in self.dirs:
            return self.dirs[path.upper()]
        parent_path, _, name = path.rpartition("/")
        parent = self.mkdir(parent_path)
        c, _ = self._alloc(1)
        d = bytearray(self.spc * SECTOR)
        d[0:32] = self._entry(b".          ", 0x10, c, 0)
        d[32:64] = self._entry(b"..         ", 0x10, parent or 0, 0)
        self.dir_data[c] = d
        self.shorts[c] = set()
        self._add_entry(parent, name, 0x10, c, 0)
        self.dirs[path.upper()] = c
        return c

    def add_file(self, path, data):
        dpath, _, name = path.replace("\\", "/").strip("/").rpartition("/")
        parent = self.mkdir(dpath) if dpath else None
        c = 0
        if data:
            c, n = self._alloc(len(data))
            off = self._cluster_off(c)
            self.img[off:off + len(data)] = data
        self._add_entry(parent, name, 0x20, c, len(data))

    def finish(self):
        bpb = bytearray(SECTOR)
        bpb[0:3] = b"\xEB\x3C\x90"
        bpb[3:11] = b"MSDOS5.0"
        struct.pack_into("<HBHBHHBHHHII", bpb, 11, SECTOR, self.spc, self.reserved, self.nfats,
                         self.root_ents, self.total if self.total < 0x10000 else 0, 0xF8,
                         self.fatsz, 63, 255, 0, self.total if self.total >= 0x10000 else 0)
        struct.pack_into("<BBBI", bpb, 36, 0x80, 0, 0x29, int(time.time()) & 0xFFFFFFFF)
        bpb[43:54] = b"NEOSYMBIAN "
        bpb[54:62] = b"FAT16   "
        bpb[510:512] = b"\x55\xAA"
        self.img[0:SECTOR] = bpb
        fat = struct.pack(f"<{len(self.fat)}H", *self.fat)
        for i in range(self.nfats):
            off = (self.reserved + i * self.fatsz) * SECTOR
            self.img[off:off + len(fat)] = fat
        roff = (self.reserved + self.nfats * self.fatsz) * SECTOR
        self.img[roff:roff + len(self.root)] = self.root
        for c, d in self.dir_data.items():
            off = self._cluster_off(c)
            self.img[off:off + len(d)] = d
        return bytes(self.img)


def _list_dir(buf):
    """(long-or-short name, attr, cluster) of each entry in a directory buffer, checking LFN checksums."""
    out, parts, ck = [], [], None
    for off in range(0, len(buf), 32):
        e = buf[off:off + 32]
        if e[0] == 0:
            break
        if e[11] == 0x0F:
            u = struct.unpack("<5H", e[1:11]) + struct.unpack("<6H", e[14:26]) + struct.unpack("<2H", e[28:32])
            parts.insert(0, "".join(chr(x) for x in u if x not in (0, 0xFFFF)))
            ck = e[13]
            continue
        short = bytes(e[0:11])
        if parts:
            assert ck == _lfn_checksum(short), "LFN checksum mismatch"
            name = "".join(parts)
        else:
            base, ext = short[0:8].decode().rstrip(), short[8:11].decode().rstrip()
            name = base + ("." + ext if ext else "")
        out.append((name, e[11], struct.unpack("<H", e[26:28])[0]))
        parts, ck = [], None
    return out


def _self_test():
    fs = Fat16(0x1000000)
    fs.add_file("Resource/Fonts/ceurope.gdr", b"font")
    fs.add_file("Long Directory Name/A long file name.text", b"x" * 5000)
    fs.add_file("Long Directory Name/A long file name too.text", b"y")
    fs.add_file("readme.txt", b"")
    fs.finish()
    root = [(n, a) for n, a, _ in _list_dir(fs.root)]
    assert root == [("RESOURCE", 0x10), ("Long Directory Name", 0x10), ("README.TXT", 0x20)], root
    sub = _list_dir(fs.dir_data[fs.dirs["LONG DIRECTORY NAME"]])
    assert [n for n, _, _ in sub] == [".", "..", "A long file name.text", "A long file name too.text"], sub
    shorts = sorted(fs.shorts[fs.dirs["LONG DIRECTORY NAME"]])
    assert shorts == [b"ALONGF~1TEX", b"ALONGF~2TEX"], shorts
    assert _list_dir(fs.dir_data[fs.dirs["RESOURCE/FONTS"]])[2][0] == "CEUROPE.GDR"
    print("mkfat self-test: ok")


def main():
    a = sys.argv[1:]
    if a == ["--self-test"]:
        return _self_test()
    size = 0x4000000
    if "--size" in a:
        i = a.index("--size"); size = int(a[i + 1], 0); del a[i:i + 2]
    out, specs = a[0], a[1:]
    fs = Fat16(size)
    for spec in specs:
        dst, _, src = spec.partition("=")
        fs.add_file(dst, open(src, "rb").read())
    open(out, "wb").write(fs.finish())
    print(f"wrote {out}: {size >> 20} MB FAT16, {fs.clusters} clusters, {len(specs)} files")


if __name__ == "__main__":
    main()
