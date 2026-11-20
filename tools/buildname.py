#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""buildname.py -- named builds: a name per phone image, a manifest of every repo's commit, a diff between two names.

  buildname.py name                     a new name: YYYY-MM-DD-<an invented animal>, not used in releases/ yet
  buildname.py manifest OUT             write the user side's manifest (build.sh): NAME, the build commit,
                                        sources.lock's pins, rust/revs.txt (one "repo commit" line per Rust repo)
  buildname.py kernel ROM_MANIFEST REV OUT [KEY=VALUE...]
                                        the image's manifest (neo kernel): the ROM's + the kernel commit + image flags
  buildname.py diff A B                 what changed between releases/A.txt and releases/B.txt, per repo
  buildname.py selftest

Manifest lines are "key value": name, build, kernel, flag.*, then one line per repo (sources.lock package or Rust repo).
An installed build's manifest is committed as releases/<name>.txt.
"""

import datetime
import json
import os
import secrets
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RELEASES = os.path.join(REPO, "releases")

# invented animals: a head and a tail from two different creatures
HEADS = [
    "otter",
    "owl",
    "lynx",
    "newt",
    "heron",
    "moth",
    "yak",
    "ibis",
    "gecko",
    "tapir",
    "finch",
    "koala",
    "vole",
    "wren",
    "lemur",
    "puffin",
    "okapi",
    "quokka",
    "narwhal",
    "axolotl",
    "pangolin",
    "marmot",
    "ferret",
    "civet",
]
TAILS = [
    "fox",
    "bat",
    "wing",
    "horn",
    "tail",
    "claw",
    "snout",
    "fin",
    "paw",
    "beak",
    "mane",
    "tusk",
    "shell",
    "quill",
]
# GitHub repo names that differ from the sources.lock package name
GITHUB = {"oss.FCL.sf.os.kernelhwsrv": "kernel"}


def github(key):
    """The NeoSymbian repo behind a manifest key: "kernel" itself, a sources.lock package ("<package>@<tag>" is a
    second checkout of the same fork) or a Rust repo."""
    repo = key.split("@", 1)[0]
    return GITHUB.get(repo, repo)


def used_names(releases=RELEASES):
    try:
        return {f[:-4] for f in os.listdir(releases) if f.endswith(".txt")}
    except FileNotFoundError:
        return set()


def new_name(today=None, used=None, pick=secrets.choice):
    today = today or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    used = used_names() if used is None else used
    taken = {n.split("-", 3)[3] for n in used if n.count("-") >= 3}
    free = [h + t for h in HEADS for t in TAILS if h + t not in taken]
    if not free:
        raise SystemExit("no free animal names left: add HEADS/TAILS")
    return f"{today}-{pick(free)}"


def parse(text):
    """key -> value; comments and blank lines skipped, the first word is the key."""
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].split()
        if len(line) >= 2:
            out[line[0]] = line[1]
    return out


def user_manifest(name, build, lock_text, rust_text):
    lines = [f"name {name or 'unnamed'}", f"build {build}"]
    lines += [f"{k} {v[:10]}" for k, v in parse(lock_text).items()]
    lines += [f"{k} {v[:10]}" for k, v in parse(rust_text).items()]
    return "\n".join(lines) + "\n"


def image_manifest(rom_text, kernel, flags):
    rom = rom_text.splitlines()
    return (
        "\n".join(
            rom[:2] + [f"kernel {kernel}"] + [f"flag.{k} {v}" for k, _, v in (f.partition("=") for f in flags)] + rom[2:]
        )
        + "\n"
    )


def compare(repo, a, b):
    """Commits from a to b on GitHub, or None when GitHub can't tell (unknown repo, offline, gh missing)."""
    try:
        r = subprocess.run(
            [
                "gh",
                "api",
                f"repos/NeoSymbian/{github(repo)}/compare/{a}...{b}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return json.loads(r.stdout)["ahead_by"] if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
        return None


def diff(a_text, b_text, count=compare):
    a, b = parse(a_text), parse(b_text)
    out = []
    for key in list(a) + [k for k in b if k not in a]:
        if key == "name":
            continue
        va, vb = a.get(key, "-"), b.get(key, "-")
        if va == vb:
            out.append(f"  {key:<34} same")
            continue
        n = (
            count(key, va, vb)
            if "-" not in (va, vb) and not key.startswith("flag.")
            else None
        )
        more = f"  ({n} commits)" if n is not None else ""
        link = (
            f"  https://github.com/NeoSymbian/{github(key)}/compare/{va}...{vb}"
            if "-" not in (va, vb) and not key.startswith("flag.")
            else ""
        )
        out.append(f"  {key:<34} {va} -> {vb}{more}{link}")
    return "\n".join(out)


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def selftest():
    assert (
        new_name("2026-11-20", {"2026-11-19-otterfox"}, pick=min)
        == "2026-11-20-axolotlbat"
    )
    assert "otterfox" not in new_name(
        "2026-11-20",
        {"2026-11-19-otterfox"},
        pick=lambda xs: next(x for x in xs if x.startswith("otter")),
    )
    lock = "# comment\noss.FCL.sf.os.ossrv\t7a4d23a4853d9a4e447df9e60be2b80d3bc072af\n\nlegacy\te7b00bb2aa\n"
    m = user_manifest("2026-11-20-owlfin", "dd7e573", lock, "neoui 0ca50cf\n")
    assert (
        m
        == "name 2026-11-20-owlfin\nbuild dd7e573\noss.FCL.sf.os.ossrv 7a4d23a485\nlegacy e7b00bb2aa\nneoui 0ca50cf\n"
    ), m
    img = image_manifest(m, "2d3343a2", ["ROFS=flash", "EMMC_C=1"])
    assert parse(img)["kernel"] == "2d3343a2" and parse(img)["flag.ROFS"] == "flash", img
    b = img.replace("neoui 0ca50cf", "neoui 1111111").replace(
        "kernel 2d3343a2", "kernel 34ed0aa6"
    )
    d = diff(
        img, b + "files 8df1ced\n", count=lambda r, _a, _b: 3 if r == "neoui" else None
    )
    assert (
        "neoui                              0ca50cf -> 1111111  (3 commits)"
        "  https://github.com/NeoSymbian/neoui/compare/0ca50cf...1111111" in d
    ), d
    assert github("oss.FCL.sf.mw.classicui@master") == "oss.FCL.sf.mw.classicui", github("x@y")
    assert github("oss.FCL.sf.os.kernelhwsrv") == github("kernel") == "kernel"
    assert (
        "kernel                             2d3343a2 -> 34ed0aa6" in d
        and "legacy" in d
        and "same" in d
    ), d
    assert "files                              - -> 8df1ced" in d, d
    print("buildname selftest: ok")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd == "name":
        print(new_name())
    elif cmd == "manifest" and len(argv) == 3:
        text = user_manifest(
            os.environ.get("NAME", ""),
            os.environ.get("NEO_BUILD_REV", "unknown"),
            read(os.path.join(REPO, "sources.lock")),
            read(os.path.join(REPO, "rust", "revs.txt")),
        )
        with open(argv[2], "w", encoding="utf-8") as f:
            f.write(text)
    elif cmd == "kernel" and len(argv) >= 5:
        with open(argv[4], "w", encoding="utf-8") as f:
            f.write(image_manifest(read(argv[2]), argv[3], argv[5:]))
    elif cmd == "diff" and len(argv) == 4:
        texts = [read(os.path.join(RELEASES, n + ".txt")) for n in argv[2:4]]
        for n, t in zip(argv[2:4], texts):
            if not t:
                raise SystemExit(f"no releases/{n}.txt")
        print(f"{argv[2]} -> {argv[3]}")
        print(diff(*texts))
    elif cmd == "selftest":
        selftest()
    else:
        print(__doc__.strip())
        return cmd == "help"
    return True


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv) else 1)
