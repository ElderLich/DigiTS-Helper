# Build with py -m PyInstaller art_studio.spec
import os
import sys
from pathlib import Path

# Search the build interpreter and Windows for native libraries. Unrelated
# graphics tools on PATH can supply an incompatible icuuc.dll for QtCore.
if sys.platform == 'win32':
    windows = Path(os.environ['SystemRoot'])
    os.environ['PATH'] = os.pathsep.join(map(str, (
        Path(sys.executable).parent, Path(sys.base_prefix),
        windows / 'System32', windows,
    )))

a = Analysis(
    ['art_studio.pyw'],
    datas=[('assets/render_portrait.py', 'assets')],
    excludes=['numpy'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='Time Stranger Art Studio',
    console=False,
)
