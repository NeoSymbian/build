# SPDX-License-Identifier: Apache-2.0
"""fshell_components -- fshell (NeoSymbian/fshell, the text shell for debug access; docs debug-access.md), merged into
components.py's registry: its libraries, consoles and the commands we use. No c32 and no memoryaccess LDD
(toolchain/fshell/platform.mmh turns them off).
"""
import os

F = 'oss.FCL.sf.os.fshell'
COMPONENTS = {
    'hash': dict(mmp='oss.FCL.sf.os.security/crypto/weakcrypto/group/hash.mmp'),
    'consoleextensions': dict(mmp=f'{F}/plugins/consoles/common/consoleextensions.mmp',
                              **{'def': f'{F}/plugins/consoles/common/eabi/consoleextensions.def'}),
    # fshell's default console: picks econs on a text configuration (plugins/consoles/defcons/src/defcons.cpp)
    'defcons': dict(mmp=f'{F}/plugins/consoles/defcons/src/defcons.mmp'),
    'consoleproxy': dict(mmp=f'{F}/plugins/consoles/consoleproxy/group/consoleproxy.mmp'),
    'ltkutils-tcb': dict(mmp=f'{F}/libraries/ltkutils/group/ltkutils-tcb.mmp'),
    'ltkutils': dict(mmp=f'{F}/libraries/ltkutils/group/ltkutils.mmp'),
    'lineeditor': dict(mmp=f'{F}/libraries/lineeditor/group/lineeditor.mmp'),
    'iocli': dict(mmp=f'{F}/libraries/iosrv/group/iocli.mmp'),
    'iosrv': dict(mmp=f'{F}/libraries/iosrv/group/iosrv.mmp',
                  rom_data=[f'resource\\iosrv.idf=src/{F}/libraries/iosrv/data/iosrv.idf']),
    'vt100': dict(mmp=f'{F}/plugins/consoles/vt100cons/group/vt100.mmp', rom_data=[
        f'resource\\vt100.idf=src/{F}/plugins/consoles/vt100cons/src/vt100/vt100.idf',
        f'system\\console\\vt100.ini=src/{F}/plugins/consoles/vt100cons/src/vt100/vt100.ini.noautodetect']),
    'vt100busdevcons': dict(mmp=f'{F}/plugins/consoles/vt100cons/group/vt100busdevcons.mmp',
                           **{'def': f'{F}/plugins/consoles/vt100cons/eabi/vt100consu.def'}),
    'fshell': dict(mmp=f'{F}/core/src/fshell.mmp', heap_max=0x1000000),
    'fshhash': dict(mmp=f'{F}/commands/hash/hash.mmp', rom='hash.exe',
                   rom_data=[f'resource\\cif\\fshell\\hash.cif=src/{F}/commands/hash/hash.cif']),
    'fshbase64': dict(mmp=f'{F}/commands/base64/base64.mmp', rom='base64.exe',
                     rom_data=[f'resource\\cif\\fshell\\base64.cif=src/{F}/commands/base64/base64.cif']),
}

# every builtin's command description (.cif): fshell needs it to run the builtin (export, var, ... fail without)
_BUILTINS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", F, "core", "builtins")
COMPONENTS['fshell']['rom_data'] = [
    f'resource\\cif\\fshell\\{name}=src/{F}/core/builtins/{name}'
    for name in (sorted(n for n in os.listdir(_BUILTINS) if n.endswith(".cif")) if os.path.isdir(_BUILTINS) else [])]
