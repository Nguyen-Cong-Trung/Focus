# Focus 1.0.0 installer acceptance

Verified on Windows 11 x64, build 26200, on 21 October 2026. No Computer Use was used.

Artifact: `Focus-Setup-1.0.0-Windows-x64.exe` — 25,004,679 bytes.

SHA256: `c4e2566260662ed5e6efc1c3282bd25e43d433ffabb823f9538491c134242f4f`

106 source unit/regression tests passed. The extracted portable executable also passed its separate diagnostic check.

The exact installer passed:

- running Focus blocks installation (exit 1).
- workspace folder cannot be selected as the install folder.
- fresh per-user install; Installed apps metadata; Desktop and Start Menu shortcuts.
- installed executable: audio, all views/themes, About, backup/restore and shutdown.
- upgrade from simulated 0.9.0 retains install path, shortcut preference, workspace and a single uninstall entry.
- downgrade protection keeps a newer executable intact.
- running Focus blocks uninstall (exit 1).
- uninstall removes app, shortcuts, registration and owned startup; preserves unrelated files/entries.
- optional Desktop and Start Menu shortcuts can both be omitted.
- existing workspace databases/settings remain byte-identical.

Original Desktop shortcut and startup settings were restored after QA. The Desktop directory contains Vietnamese characters; the test installation path contains spaces.

Application diagnostics use isolated temporary data and fake audio output. They do not operate real audio devices, modify hosts, terminate user apps or schedule a Windows shutdown. The older installed version is simulated to test installation mechanics; an independently released 0.9.0 database schema was not migrated. Windows 10 is a compatibility target, not a tested machine in this review. Interactive page rendering at every DPI and every Windows configuration is not certified by these programmatic checks.

The application, installer and uninstaller are **not Authenticode-signed**. A trusted publisher certificate/signing service is still required for a signed public release. File hashes verify integrity only.

See [INSTALLER.md](INSTALLER.md) for reproduction and build instructions. Detailed local diagnostic reports stay outside version control under `.release-work`.
