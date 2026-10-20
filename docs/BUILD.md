# Building the Windows portable release

For the recommended Windows installer, continue with [INSTALLER.md](INSTALLER.md) after building this bundle.

Use 64-bit Python 3.12 on Windows. Runtime dependencies are pinned to the versions tested for Focus 1.0.0.

```powershell
py -3.12 -m venv .runtime
.runtime\Scripts\python.exe -m pip install -r PythonProject\requirements.txt -r build_tools\requirements-build.txt
.runtime\Scripts\python.exe -B build_tools\build_release.py
```

The result is `releases/Focus-1.0.0-Windows-x64.zip`, with `SHA256SUMS.txt` beside it. Build intermediates stay in `.release-work` and the unpacked app in `dist/Focus`; neither is committed. A one-folder executable avoids unpacking the entire runtime every time the app starts. The download contains no virtual environment, source tests, IDE settings, workspace database, cached audio, personal recordings or machine-specific shortcut.

The portable folder contains:

```text
Focus-1.0.0-Windows-x64/
  Focus.exe
  _internal/
  README.txt
  THIRD-PARTY-NOTICES.txt
  Create Desktop Shortcut.cmd
  Install Desktop Shortcut.ps1
```

Keep `_internal` next to the executable. Its licenses include Python and bundled Python packages. Font and rainfall credits remain with their assets.

## Packaged executable verification

The executable supports an isolated diagnostic mode. It uses temporary data and fake audio output; it does not modify the real workspace, block websites, stop apps or schedule Windows shutdown.

```powershell
Start-Process -FilePath .\dist\Focus\Focus.exe -ArgumentList '--self-test', 'D:\path\to\report.json' -Wait -WindowStyle Hidden
```

The report must contain `"ok": true` and `"frozen": true`. This check loads all seven bundled sounds and the audio library, visits nine views in both themes, opens About, verifies the Windows instance guard, creates/restores a backup and quits cleanly. Release acceptance also checks the extracted ZIP, its checksum and a shortcut created into a temporary folder.
