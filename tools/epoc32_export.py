"""epoc32_export -- build a real epoc32/include tree from bld.inf PRJ_EXPORTS.

The 2010 source has no epoc32/include: every component EXPORTS its public / platform headers there at build time
(bld.inf PRJ_EXPORTS). Everything above kernelhwsrv (estor, bafl, gdi, fbserv, wserv, ...) includes its neighbours via
that tree, so to compile them unmodified we do what `abld export` does: preprocess each bld.inf (platform_paths.hrh
macros), walk PRJ_EXPORTS, and copy each header to its destination under <repo>/.epoc32/include.

    python3 tools/epoc32_export.py                    # the default package set (sources.lock)
    python3 tools/epoc32_export.py oss.FCL.sf.os.graphics [more packages...]

Only destinations under /epoc32/include are honoured (no rom/ iby, data, zips). The export runs twice: with the new
header layout (/epoc32/include/platform/..., kernel/localise.h ...) and with -DSYMBIAN_OLD_EXPORT_LOCATION (headers
under include/kernel/...), the layout most mmps assume; the include tree is the union of the two.
"""
import filecmp, os, re, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(REPO, "src")
OUT = os.path.join(REPO, ".epoc32", "include")
CPP = os.environ.get("ARM_CPP", "arm-none-eabi-cpp")
PATHS_DIR = os.path.join(BASE, "oss.FCL.sf.os.deviceplatformrelease", "symbianosbld", "cedarutils")
VARIANT = os.path.join(PATHS_DIR, "inc", "Symbian_OS_tb102sf.hrh")
DEFAULT_PKGS = [
    "oss.FCL.sf.os.deviceplatformrelease", "oss.FCL.sf.os.kernelhwsrv",
    "oss.FCL.sf.os.ossrv", "oss.FCL.sf.os.persistentdata", "oss.FCL.sf.os.textandloc",
    "oss.FCL.sf.os.graphics", "oss.FCL.sf.os.devicesrv", "oss.FCL.sf.os.security",
    "symbian-qemu", "oss.FCL.sf.mw.uiresources",
    # mmf/common/mmfbase.h, icl/imagedata.h (included by bafl and the window server headers)
    "oss.FCL.sf.os.mm", "oss.FCL.sf.os.mmimaging", "oss.FCL.sf.os.mmaudio",
    # the application framework, CONE/Uikon/Avkon and the apps on them (legacy GUI apps)
    "oss.FCL.sf.mw.appsupport", "oss.FCL.sf.mw.classicui", "oss.FCL.sf.mw.inputmethods", "oss.FCL.sf.mw.hapticsservices",
    "oss.FCL.sf.mw.appinstall",
    "oss.FCL.sf.app.utils", "oss.FCL.sf.app.rndtools",
    # headers the Avkon stack includes from the rest of the platform (comms, location, XML, ALF, profiles, idle, widgets,
    # DRM, SVG-T, the layout system, contacts)
    "oss.FCL.sf.os.commsfw", "oss.FCL.sf.os.networkingsrv", "oss.FCL.sf.os.lbs", "oss.FCL.sf.os.xmlsrv",
    "oss.FCL.sf.mw.uiaccelerator", "oss.FCL.sf.mw.gsprofilesrv", "oss.FCL.sf.mw.homescreensrv", "oss.FCL.sf.mw.web",
    "oss.FCL.sf.mw.drm", "oss.FCL.sf.mw.svgt", "oss.FCL.sf.mw.uitools", "oss.FCL.sf.app.contacts",
    "oss.FCL.sf.os.cellularsrv", "oss.FCL.sf.mw.phonesrv", "oss.FCL.sf.mw.usbservices",
]
SKIP_DIRS = {"test", "tsrc", "tests", "documentation", "examples", "internal"}
# the pre-zero-copy MBuf manager: commsbufs/group/bld.inf includes it only without SYMBIAN_ZERO_COPY_NETWORKING, and
# its comms-infras/mbufpanic.h (no EMBuf_IndexOutofRange) overwrote the current one whenever os.walk reached it last
SKIP_PATHS = {os.path.join(BASE, "oss.FCL.sf.os.commsfw", "commsfwutils", "commsbufs", "version1")}
SECTION = re.compile(r"^\s*PRJ_(\w+)", re.I)
CPP_ERRORS = {}   # bld.inf -> cpp's first error, for the last preprocess of it (empty when it preprocessed cleanly)


def preprocess(path, old_location):
    # A bld.inf `#include "../../../../../mw/..."` written for Nokia's sf/<layer>/<pkg> tree is missing here and
    # STOPS cpp -- the whole package would export nothing. Rewrite such includes onto our checkouts
    # (emitter/mmp.py map_sf_path), feed the text on stdin from the file's own directory, and give the markers back
    # the real file name (exports() tracks the current dir from them).
    sys.path.insert(0, os.path.join(REPO, "emitter"))
    import mmp as _MMP
    d = os.path.dirname(os.path.abspath(path))
    text = open(path, errors="replace").read()

    def fix(m):
        full = os.path.normpath(os.path.join(d, m.group(2).replace("\\", "/")))
        if os.path.exists(full):
            return m.group(0)
        mapped = _MMP.map_sf_path(full)
        return m.group(1) + mapped.replace("\\", "/") + m.group(3) if mapped != full else m.group(0)
    fixed = _MMP._REL_INCLUDE.sub(fix, text)
    src, stdin = (path, None) if fixed == text else ("-", fixed)
    r = subprocess.run([CPP, "-undef", "-nostdinc", "-x", "c", "-w",
                        "-DEPOC32", "-DMARM", "-DEABI", "-DMARM_ARMV5", "-DGCCE",
                        "-D__GNUC__=3", "-DSBSV2", *(["-DSYMBIAN_OLD_EXPORT_LOCATION"] if old_location else []),
                        "-I", PATHS_DIR, "-I", OUT, "-I", os.path.dirname(path),
                        # the product-variant feature flags gate some exports
                        # (e.g. SYMBIAN_ENABLE_64_BIT_FILE_SERVER_API -> f32file64.h)
                        "-include", VARIANT,
                        *_MMP.sf_mirror_incs(), "-idirafter", os.path.join(REPO, ".casefix"),
                        "-include", os.path.join(PATHS_DIR, "platform_paths.hrh"), src],
                       input=stdin, cwd=d if stdin is not None else None,
                       capture_output=True, text=True, errors="replace")
    # cpp stops at the first missing #include: everything the bld.inf exports after it would be lost silently
    CPP_ERRORS[path] = "" if r.returncode == 0 else next(
        (ln for ln in r.stderr.splitlines() if "error" in ln), r.stderr.strip()[:200])
    out = r.stdout
    if stdin is not None:
        out = out.replace('"<stdin>"', '"' + path + '"')
    return out


def preprocessed_lines(bldinf, old_location):
    """the preprocessed bld.inf as lines, with a backslash-continued export ("../data/x.xml\\" + an indented
    "    /epoc32/data/z/..." line) joined back into one: the preprocessor drops the backslash but keeps the line break."""
    lines = preprocess(bldinf, old_location).splitlines()
    marker = re.compile(r'^#\s*\d+\s+"')
    joined, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip() and not ln.lstrip().startswith("#") and len(ln.split()) == 1:
            j = i + 1									# the preprocessor may also insert line markers after a splice
            while j < len(lines) and (not lines[j].strip() or marker.match(lines[j])):
                j += 1
            if j < len(lines) and lines[j][:1].isspace() and len(lines[j].split()) == 1 and "/" in lines[j]:
                joined.append(ln.strip() + " " + lines[j].strip())
                i = j + 1
                continue
        joined.append(ln)
        i += 1
    return joined


sys.path.insert(0, os.path.join(REPO, "emitter"))
import mmp as _MMP  # noqa: E402


def exports(bldinf, old_location):
    """yield (src_abs, dest_rel_to_epoc32_include) for one bld.inf."""
    cur_dir, section = os.path.dirname(bldinf), ""
    for ln in preprocessed_lines(bldinf, old_location):
        m = re.match(r'^#\s*\d+\s+"([^"]+)"', ln)
        if m:
            f = m.group(1).replace("\\\\", "\\")
            if not f.startswith("<"):
                cur_dir = os.path.dirname(os.path.abspath(f))
            continue
        m = SECTION.match(ln)
        if m:
            section = m.group(1).upper()
            continue
        if section != "EXPORTS":
            continue
        toks = re.findall(r'"[^"]*"|\S+', ln)
        if not toks or toks[0].startswith(":"):
            continue
        toks = [t.strip('"') for t in toks]
        src = os.path.normpath(os.path.join(cur_dir, toks[0].replace("\\", "/")))
        src = _MMP.nocase(src) or src          # the tree was authored on a case-insensitive file system
        dest = toks[1].replace("\\", "/") if len(toks) > 1 else ""
        if not dest:
            rel = os.path.basename(src)
        elif dest.startswith("+"):
            d = dest[1:].lstrip("/").lower()
            if not d.startswith("include/"):
                continue
            rel = dest[1:].lstrip("/")[len("include/"):]
        elif dest.startswith("/") or re.match(r"^[a-zA-Z]:", dest):
            d = re.sub(r"^[a-zA-Z]:", "", dest).lstrip("/")
            if not d.lower().startswith("epoc32/include/"):
                continue
            rel = d[len("epoc32/include/"):]
        elif dest.startswith("|"):
            continue                         # an export INTO the source tree: not an include-tree header
        else:
            rel = dest                       # relative dest => under epoc32/include
        if rel.endswith("/") or not rel:
            rel = rel + os.path.basename(src)
        yield src, rel


def seed():
    """the headers every bld.inf preprocess includes. bldvariant.hrh includes variant/Symbian_OS.hrh: without it in
    place before the walk, every bld.inf that includes <bldvariant.hrh> failed on a cold build and exported nothing
    (aknlayout2's aknlayoutscalable_*.cdl.common.h among them; casefix then linked an older per-variant copy)."""
    os.makedirs(os.path.join(OUT, "variant"), exist_ok=True)
    shutil.copy2(os.path.join(PATHS_DIR, "platform_paths.hrh"), os.path.join(OUT, "platform_paths.hrh"))
    shutil.copy2(VARIANT, os.path.join(OUT, "variant", "Symbian_OS.hrh"))


def ntfs(name):
    """the order Windows lists a directory in (case-insensitive); the exact name breaks case-only ties"""
    return name.upper(), name


def bld_infs(pkgs):
    """every bld.inf of the packages in NTFS order (as tools/mbg.py walks): when two bld.infs export the same header
    the later copy wins, and os.walk's file-system order made that differ between machines"""
    for pkg in pkgs:
        for root, dirs, files in os.walk(os.path.join(BASE, pkg)):
            dirs[:] = sorted((d for d in dirs if d.lower() not in SKIP_DIRS and d != ".git"
                              and os.path.join(root, d) not in SKIP_PATHS), key=ntfs)
            for f in sorted(files, key=ntfs):
                if f.lower() == "bld.inf":
                    yield os.path.join(root, f)


def run(pkgs, old_location):
    n = {"inf": 0, "new": 0, "same": 0, "missing": 0}

    def export_one(bldinf):
        """copy one bld.inf's exports; False when cpp failed on it (its exports after the error are missing)"""
        for src, rel in exports(bldinf, old_location):
            if not os.path.isfile(src):
                n["missing"] += 1
                continue
            dst = os.path.join(OUT, rel.replace("/", os.sep).lower())
            if os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False):
                n["same"] += 1
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            n["new"] += 1
        return not CPP_ERRORS.get(bldinf)

    seed()
    failed = []
    for bldinf in bld_infs(pkgs):
        n["inf"] += 1
        if not export_one(bldinf):
            failed.append(bldinf)
    # A failed bld.inf may include a header that a later one exported, or one whose spelling only resolves through
    # .casefix (bldvariant.hrh's #include "ProductVariant.hrh" is exported as productvariant.hrh): on a cold build
    # .casefix is still empty here (its own step runs later), so refresh it from the tree so far and retry while
    # that helps. A warm build passed only because the previous run's .casefix was still there.
    import casefix
    while failed:
        casefix.main()
        still = [b for b in failed if not export_one(b)]
        if len(still) == len(failed):
            break
        failed = still
    # several packages export the same name; the Symbian (cedarutils) platform_paths.hrh must win
    seed()
    print("bld.inf: %d   exported: %d new, %d up-to-date, %d missing-src -> %s%s"
          % (n["inf"], n["new"], n["same"], n["missing"], OUT, "  (old export location)" if old_location else ""))
    for b in failed:
        print("  cpp failed, exports incomplete: %s: %s" % (os.path.relpath(b, BASE), CPP_ERRORS[b]))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    pkgs = sys.argv[1:] or DEFAULT_PKGS
    run(pkgs, False)
    run(pkgs, True)
