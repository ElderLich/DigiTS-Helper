import os
import sys
from pathlib import Path

# Resolve Qt's dependencies using the interpreter and Windows runtime.
if sys.platform == 'win32':
    windows = Path(os.environ['SystemRoot'])
    os.environ['PATH'] = os.pathsep.join(map(str, (
        Path(sys.executable).parent, Path(sys.base_prefix),
        windows / 'System32', windows,
    )))

app = Path(SPECPATH).parent / 'app'
a = Analysis(
    [str(app / 'digimon_editor.py')],
    pathex=[],
    binaries=[],
    datas=[(str(app / 'assets/game_icons'), 'assets/game_icons'),
           (str(app / 'assets/game_ui'), 'assets/game_ui')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Time Stranger Mod Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
