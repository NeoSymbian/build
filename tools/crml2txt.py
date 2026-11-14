# SPDX-License-Identifier: Apache-2.0
"""crml2txt -- Central Repository initialisation files (<uid>.txt) from S60 .crml definitions.

Some S60 repositories ship only as a .crml (the XML the S60 configuration tool turned into the ROM's <uid>.txt / .cre
with the product's values). CentRepSrv reads only .txt / .cre, so a missing one makes CRepository::NewL leave
KErrNotFound. This writes the .txt the configuration tool would have: every key of the .crml with its <value> when
the .crml has one, otherwise the type's zero ("" / 0 / 0.0); the repository's own default read/write policies.

    python3 tools/crml2txt.py            (a build step: CRMLS below -> emitter/cenrep/<uid>.txt, UTF-16 as CentRepSrv wants)
"""

import os
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "emitter", "cenrep")
CRMLS = [
    # KCRUidThemes: the skin server (CAknsSrvSettings) opens it at start-up
    "oss.FCL.sf.mw.classicui/psln/conf/themes_102818E8.crml",
    # KCRUidThemesVariation: the skin server reads its local variation when it starts the animated background
    "oss.FCL.sf.mw.classicui/psln/conf/themes_102818EB.crml",
    # KCRUidAknPhysicsSettings: Avkon's kinetic scrolling (missing: on by default, and its engine needs ODE)
    "oss.FCL.sf.mw.classicui/uifw/AvKon/aknphysics/conf/s60/aknphysics_20021192.crml",
    # the FEP's settings: AknCapServer sets the hash-key selection there at start-up
    "oss.FCL.sf.mw.inputmethods/fep/aknfep/conf/aknfep_101F876D.crml",
    # application orientation: AknCapServer opens it at start-up
    "oss.FCL.sf.mw.appsupport/contextframework/cfw/conf/contextframework_200159ED.crml",
    # the skin server: wallpaper configuration and the DRM helper's settings
    "oss.FCL.sf.mw.uiresources/skins/AknSkins/conf/aknskins_10282CB2.crml",
    "oss.FCL.sf.mw.drm/omadrm/conf/drm5_10205CA7.crml",
    # the profiles engine's active-profile settings (Avkon reads tones and vibra there)
    "oss.FCL.sf.mw.gsprofilesrv/profilesservices/ProfileEngine/conf/profilesengine_101F8798.crml",
]
# board values over a .crml's defaults: {uid: {key: value}}
OVERRIDES = {
    "20021192": {0x9: "0"},  # KFeatureEnabled: no kinetic scrolling (ODE, the physics engine, is not built)
}
ZERO = {
    "int": "0",
    "real": "0.0",
    "string": '""',
    "string8": '""',
    "binary": "00",
    "selection": "0",
}


def caps(el) -> str:
    out = []
    for a in el.findall("{*}access"):
        cap = a.get("capabilities") or ""
        sid = a.get("sid")
        kind = "rd" if a.get("type") == "R" else "wr"
        if sid:
            out.append(f"sid_{kind}={sid}")
        if cap:
            out.append(f"cap_{kind}={cap.replace(' ', ',')}")
    # CentRepSrv reads a setting's read policy before its write policy (CIniFileIn::ReadSettingL): wr first is corrupt
    return " ".join(sorted(out, key=lambda p: p.split("_", 1)[1].startswith("wr")))


def value(key, typ: str) -> str:
    v = key.find("{*}value")
    if v is None or v.text is None:
        return ZERO.get(typ, "0")
    text = v.text.strip()
    return (
        '"' + text.replace('"', '\\"') + '"' if typ in ("string", "string8") else text
    )


def convert(crml: str) -> tuple[str, str]:
    with open(crml, "rb") as fh:
        raw = fh.read()
    root = ET.fromstring(
        raw.decode("utf-16")
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff")
        else raw.decode("utf-8")
    )
    uid = int(root.get("uidValue") or "0", 16)
    lines = [
        "cenrep",
        "version 1",
        "[owner]",
        root.get("owner") or "0x00000000",
        "[defaultmeta]",
        "0",
        "[platsec]",
        caps(root) or "cap_rd=AlwaysPass cap_wr=AlwaysPass",
        "[Main]",
    ]
    for key in root.findall("{*}key"):
        typ = key.get("type", "int")
        k = int(key.get("int") or "0", 16)
        v = OVERRIDES.get(f"{uid:08X}", {}).get(k, value(key, typ))
        lines.append(f"0x{k:x} {typ} {v} 0 {caps(key)}".rstrip())
    return f"{uid:08x}".upper(), "\r\n".join(lines) + "\r\n"


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for rel in CRMLS:
        uid, text = convert(os.path.join(REPO, "src", rel))
        out = os.path.join(OUT, uid + ".txt")
        with open(out, "wb") as fh:
            fh.write(b"\xff\xfe" + text.encode("utf-16-le"))
        print(
            f"crml2txt: {rel} -> {os.path.relpath(out, REPO)} ({text.count(chr(10)) - 9} keys)"
        )


if __name__ == "__main__":
    main()
