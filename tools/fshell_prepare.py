# SPDX-License-Identifier: Apache-2.0
"""fshell_prepare -- fshell's build inputs: its exported headers, our text-only platform.mmh (chosen explicitly, not by
the export walk's order), the generated version file, and a check that every command description (.cif) exists.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
PACKAGE = 'oss.FCL.sf.os.fshell'


def main():
    source = REPO / 'src' / PACKAGE
    if not source.is_dir():
        raise SystemExit('fshell source is absent; fetch the pinned source set first')
    sys.path.insert(0, str(REPO / 'tools'))
    import epoc32_export as export
    out = REPO / '.epoc32/include/fshell'
    out.mkdir(parents=True, exist_ok=True)
    platform = REPO / 'toolchain/fshell/platform.mmh'
    shutil.copy2(platform, out / 'platform.mmh')
    for name in ('common.mmh', 'fsh_system_include.mmh'):
        shutil.copy2(source / 'build/common' / name, out / name)
    export.run([PACKAGE], False)
    export.run([PACKAGE], True)
    shutil.copy2(platform, out / 'platform.mmh')
    generated = REPO / '.epoc32/build/fshell/core/generated/platform_GCCE'
    generated.mkdir(parents=True, exist_ok=True)
    # Keep upstream's version generator; the unknown compiler spelling is only
    # a version string and does not substitute a different compiler/toolchain.
    result = subprocess.run(['perl', 'genver.pl', 'NeoSymbian'],
                            cwd=source / 'core/group', capture_output=True, check=True,
                            env=dict(os.environ, USERNAME='NeoSymbian'))
    # Perl on Unix retains CR from the upstream Windows change-history file;
    # that CR would split the version's generated C++ string literal.
    (generated / 'fshell_version.cpp').write_bytes(result.stdout.replace(b'\r', b''))
    sys.path.insert(0, str(REPO / 'emitter'))
    import components
    for spec in components.COMPONENTS['fshell']['rom_data']:
        if not (REPO / spec.split('=', 1)[1]).is_file():
            raise SystemExit('required command description is absent: ' + spec)
    print('fshell: native headers, explicit text platform, version and CIF data prepared')


if __name__ == '__main__':
    main()
