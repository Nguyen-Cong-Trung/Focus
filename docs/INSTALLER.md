# Windows installer

The recommended download is `Focus-Setup-1.0.1-Windows-x64.exe`. It is a single, offline, x64 Inno Setup 7.1.0 installer for Windows 10 (1809+) and Windows 11. Setup UI is English and adapts to the Windows light/dark preference.

## Install, update and remove

Setup defaults to `%LOCALAPPDATA%\Programs\Spertulo Utility\Focus` for the current Windows account. It needs no administrator elevation. Choose another local folder if desired. A Start Menu group is created; the Desktop shortcut is optional and unchecked by default. Finish offers an optional launch. Python is bundled privately under `_internal` and is not added to PATH.

Quit Focus from the notification-area menu before running Setup or Uninstall. A shared Windows mutex detects running copies across source, installed and newly packaged portable locations. Restart Manager additionally checks files in use. Setup never uses forced application closure. A stable AppId, previous directory/tasks and an appended uninstall log allow an in-place update with one Windows Installed apps entry. Downgrades are rejected by executable version; a new release must update both the app version and installer version checks.

Windows Settings → Apps → Installed apps → Focus → Uninstall removes installed files, installer-created shortcuts and uninstall registration. Matching Focus/DeepFocus startup entries are removed only if they point to that exact installation. Files unknown to the installer are retained. No recursive wildcard uninstall deletion is used.

The workspace in `%USERPROFILE%\.deepfocus` is outside the installation. Updates and uninstall never delete it. Setup rejects that folder or its children as an application directory, including during unattended installation. Back up the workspace from Focus Settings before changing computers.

## Build

First build the app bundle as described in [BUILD.md](BUILD.md). Obtain Inno Setup 7.1.0 from [its official release](https://github.com/jrsoftware/issrc/releases/tag/is-7_1_0). Verify the downloaded compiler's Authenticode signature and release digest. Its own installer supports `/PORTABLE=1 /CURRENTUSER /VERYSILENT /NOICONS /DIR="..."` to keep build tools local.

```powershell
.runtime\Scripts\python.exe -B build_tools\build_installer.py --compiler "C:\path\to\ISCC.exe"
```

The builder composes installer artwork from the supplied logo and Inter fonts, compiles `build_tools/installer/Focus.iss`, and writes SHA256 hashes for both the installer and portable ZIP. Keep `AppId={139698E0-3B7B-4867-AB38-C8B37B01C9E1}` unchanged in future versions.

## Acceptance checks

```powershell
.runtime\Scripts\python.exe -B build_tools\verify_installer.py
```

This Windows integration check executes the exact installer and uninstaller. It requires no existing installed Focus. It creates a test installation under `.release-work`, a uniquely named Start Menu group, and a temporary Desktop shortcut. An existing Desktop shortcut and startup values are backed up and restored in `finally`. It checks running-app rejection, workspace-directory rejection, per-user Windows registration, shortcuts, installed app diagnostics, upgrade from a simulated 0.9.0 executable, downgrade rejection, uninstall, startup cleanup and data retention. The simulated older version tests installation mechanics; it is not a claim to migrate an independently released 0.9.0 database schema. Existing workspace databases/settings must remain byte-identical. Tests do not operate real audio hardware, terminate apps or schedule shutdown.

The publication script requires the exact installer's successful report and matching checksums. It uploads assets to a draft, verifies GitHub digests, then publishes. `v1.0.1` identifies the current maintenance release. Earlier published releases remain intact.

The recorded results are in [INSTALLER-QA.md](INSTALLER-QA.md).

## Signing status

This installer and its app/uninstaller are **unsigned**. No publisher code-signing certificate with a private key is available in the current build environment. Company/version/icon resources do not constitute a verified publisher signature, and SHA256 does not replace one.

For a signed release, obtain a trusted code-signing certificate or signing-service account for the publisher. Use Microsoft's SignTool/service to sign `Focus.exe` before packaging, configure Inno Setup's `SignTool` and `SignedUninstaller=yes` to sign Setup and Uninstall (with SHA256 and a trusted timestamp), then rebuild, repeat acceptance checks, regenerate hashes and publish. Keep certificate private keys/passwords out of the repository. Do not substitute a self-signed certificate for public publisher verification.
