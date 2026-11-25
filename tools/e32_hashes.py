#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""e32_hashes.py -- the E32 images a build produced, one line each: "sha256 size name" (docs user-side-smp.md US5:
CI and the phone run the same user-side bytes).

  e32_hashes.py list DIR [OUT]   every E32 image directly in DIR ("EPOC" at byte 16), sorted by name
  e32_hashes.py compare A B      every image of list A must be in list B with the same bytes; B's extra images
                                 (e.g. the Rust EXEs a phone build adds) are only listed. Exit 1 on a difference.
  e32_hashes.py selftest
"""

import hashlib
import os
import sys
import tempfile


def is_e32(path):
    with open(path, "rb") as fh:
        head = fh.read(20)
    return len(head) == 20 and head[16:20] == b"EPOC"


def listing(d):
    rows = []
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if os.path.isfile(p) and not os.path.islink(p) and is_e32(p):
            with open(p, "rb") as fh:
                data = fh.read()
            rows.append(f"{hashlib.sha256(data).hexdigest()} {len(data)} {name}")
    return rows


def read(path):
    out = {}
    with open(path) as fh:
        for line in fh:
            if line.strip():
                digest, size, name = line.split()
                out[name] = (digest, size)
    return out


def compare(a, b):
    """The problems (lines) and B's extra names."""
    bad = [f"missing in B: {n}" for n in sorted(a) if n not in b]
    bad += [f"differs: {n}" for n in sorted(a) if n in b and a[n] != b[n]]
    return bad, sorted(set(b) - set(a))


def selftest():
    with tempfile.TemporaryDirectory() as d:
        e32 = bytes(16) + b"EPOC" + b"x" * 8
        for name, data in [
            ("a.dll", e32),
            ("b.exe", e32 + b"y"),
            ("c.txt", b"no image here at all!"),
        ]:
            with open(os.path.join(d, name), "wb") as fh:
                fh.write(data)
        rows = listing(d)
        assert [r.split()[2] for r in rows] == ["a.dll", "b.exe"], rows
        assert rows[0].split()[1] == "28"
        a = {r.split()[2]: tuple(r.split()[:2]) for r in rows}
        assert compare(a, a) == ([], [])
        b = dict(a, **{"c.exe": ("0" * 64, "1")})
        assert compare(a, b) == ([], ["c.exe"])
        b["a.dll"] = ("1" * 64, "28")
        del b["b.exe"]
        assert compare(a, b)[0] == ["missing in B: b.exe", "differs: a.dll"]
    print("e32_hashes selftest: ok")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "list" and len(argv) in (3, 4):
        text = "".join(r + "\n" for r in listing(argv[2]))
        if len(argv) == 4:
            with open(argv[3], "w") as fh:
                fh.write(text)
        else:
            sys.stdout.write(text)
    elif cmd == "compare" and len(argv) == 4:
        bad, extra = compare(read(argv[2]), read(argv[3]))
        for line in bad:
            print(line)
        if extra:
            print(f"only in B ({len(extra)}): {' '.join(extra)}")
        print(
            f"e32_hashes: {'DIFFERENT' if bad else 'same'} ({len(read(argv[2]))} images in A)"
        )
        return 1 if bad else 0
    elif cmd == "selftest":
        selftest()
    else:
        sys.stderr.write(__doc__ or "")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
