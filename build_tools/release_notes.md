Focus **1.0.0** — Spertulo Utility, created by **Nguyễn Công Trung**.

### Recommended download: Windows installer

Download **Focus-Setup-1.0.0-Windows-x64.exe** and follow the setup wizard. No Python installation or runtime download is required.

- Branded English setup, with light/dark appearance matching Windows.
- Installs for the current Windows account; choose the installation folder.
- Start Menu entries and an optional Desktop shortcut using the Focus logo.
- Listed in Windows Settings → Apps → Installed apps, with version and publisher information.
- Updates retain the installation folder, plans, settings, history and imported recordings.
- Setup and uninstall ask you to quit Focus if it is running, including in the tray. They do not force-close your session.
- Prevents installing an older version over a newer one and prevents installing inside the workspace folder.
- Uninstall removes installed program files and shortcuts, keeps personal workspace data and unrelated files, and removes only startup entries belonging to that installation.

Your workspace stays in `%USERPROFILE%\.deepfocus`. Back it up in **Settings → Your data**. Choose **Quit Focus** from the tray menu before updating or uninstalling.

### Portable alternative

**Focus-1.0.0-Windows-x64.zip**: extract the full folder, keep `_internal` beside **Focus.exe**, then launch. It does not register an uninstaller. Quit a portable copy before starting Setup.

### Verification and signing

The installer passed a fresh install, installed executable diagnostics, an upgrade from simulated 0.9.0, downgrade rejection, running-app protection, shortcut/Windows registration checks and uninstall/data-retention checks. The source passed 106 unit/regression tests. Audio hardware, site/app blocking and OS shutdown are mocked in application diagnostics.

**This release is not Authenticode-signed.** No code-signing certificate is available for the publisher yet. Windows may show an unknown-publisher or SmartScreen prompt. Download only from this repository. `SHA256SUMS.txt` verifies the downloaded files against this release; it is not a digital signature.

The application version remains **1.0.0**. The release tag `v1.0.0-installer.1` identifies this installer revision and preserves the original portable release and its source history.

### Included in Focus

Focus timer, custom modes and distraction blocking; planner, schedules and checklists; seven offline sounds and personal WAV imports; Shutdown Timer; history, statistics, backup/restore; light/dark appearance; mini player and About/contact links.
