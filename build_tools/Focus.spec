# Reproducible Windows onedir bundle: app/runtime assets only, no user workspace.
from pathlib import Path
import sys
import importlib.metadata as metadata
from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent
datas = [(str(ROOT / 'PythonProject/assets'), 'assets')]
for name in ('focus-logo.png', 'focus.ico', 'creator.json'):
    datas.append((str(ROOT / 'branding' / name), 'branding'))
datas += collect_data_files('customtkinter')
datas += collect_data_files('CTkMessagebox')
for package in ('customtkinter', 'numpy', 'sounddevice', 'Pillow', 'CTkMessagebox', 'CTkToolTip', 'keyboard', 'cffi', 'PyInstaller'):
    distribution = metadata.distribution(package)
    for file in distribution.files or ():
        if 'license' in str(file).lower() or Path(str(file)).name.lower().startswith('copying'):
            source = Path(distribution.locate_file(file))
            if source.is_file():
                datas.append((str(source), 'licenses/' + package + '/' + str(Path(str(file)).parent)))
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.exists():
    datas.append((str(python_license), 'licenses/Python'))

a = Analysis([str(ROOT / 'PythonProject/main.py')], pathex=[str(ROOT / 'PythonProject')],
    binaries=[], datas=datas, hiddenimports=[], hookspath=[], runtime_hooks=[],
    excludes=['pip', 'setuptools', 'numpy.tests', 'numpy.testing', 'tkinter.test', 'test',
              'PIL.AvifImagePlugin', 'PIL._avif'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Focus', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    icon=str(ROOT / 'branding/focus.ico'), version=str(ROOT / 'build_tools/windows-version.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Focus')
