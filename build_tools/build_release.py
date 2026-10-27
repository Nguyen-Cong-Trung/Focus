"""Build the clean Windows portable download, then archive and hash it."""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.1'
NAME = f'Focus-{VERSION}-Windows-x64'


def main():
    if os.name != 'nt' or sys.maxsize <= 2**32:
        raise SystemExit('Build this package with 64-bit Python on Windows.')
    environment = os.environ.copy()
    environment['PYINSTALLER_CONFIG_DIR'] = str(ROOT / '.release-work/cache')
    subprocess.run([sys.executable, '-B', '-m', 'PyInstaller', '--noconfirm',
        '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / '.release-work/build'),
        str(ROOT / 'build_tools/Focus.spec')], check=True, cwd=ROOT, env=environment)
    bundle = ROOT / 'dist/Focus'
    # Vendor macOS directory metadata is never required by the Windows runtime.
    for metadata_file in bundle.rglob('.DS_Store'):
        metadata_file.unlink()
    shutil.copyfile(ROOT / 'build_tools/README.txt', bundle / 'README.txt')
    shutil.copyfile(ROOT / 'build_tools/Create Desktop Shortcut.cmd', bundle / 'Create Desktop Shortcut.cmd')
    shutil.copyfile(ROOT / 'Install Desktop Shortcut.ps1', bundle / 'Install Desktop Shortcut.ps1')
    packages = ['customtkinter', 'numpy', 'sounddevice', 'Pillow', 'CTkMessagebox', 'CTkToolTip', 'keyboard', 'cffi', 'PyInstaller']
    notices = ['Focus 1.0.1 — third-party notices',
        'License texts are included under _internal/licenses.',
        'Python, Tcl/Tk, PortAudio and the fonts retain their respective notices.',
        'The PyInstaller bootloader is distributed under its GPL license with the bootloader exception.',
        'Rain recording: Shizhao, public domain. See _internal/assets/audio/README.md.', '']
    notices.extend(f'{package} {metadata.version(package)}' for package in packages)
    (bundle / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(notices) + '\n', encoding='utf-8')
    releases = ROOT / 'releases'
    releases.mkdir(exist_ok=True)
    archive = releases / (NAME + '.zip')
    entries = sorted(path for path in bundle.rglob('*') if path.is_file())
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in entries:
            relative = path.relative_to(bundle)
            if any(part in ('.git', '.runtime', '__pycache__', '.idea', 'tests') for part in relative.parts):
                raise ValueError(f'Unexpected development content in bundle: {relative}')
            if path.suffix.lower() in ('.db', '.log', '.lnk'):
                raise ValueError(f'Unexpected personal/machine-specific file: {relative}')
            output.write(path, str(Path(NAME) / relative))
    with zipfile.ZipFile(archive) as output:
        if output.testzip() is not None:
            raise ValueError('Archive integrity check failed')
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (releases / 'SHA256SUMS.txt').write_text(f'{checksum}  {archive.name}\n', encoding='ascii')
    manifest = {'name': NAME, 'version': VERSION, 'files': len(entries),
        'zip_bytes': archive.stat().st_size, 'uncompressed_bytes': sum(p.stat().st_size for p in entries),
        'sha256': checksum, 'root_items': sorted(p.name for p in bundle.iterdir())}
    (ROOT / '.release-work/package-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == '__main__':
    main()
