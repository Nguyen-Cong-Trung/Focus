# Focus 1.0.1 — coexistence and operational review

Reviewed on 28 October 2026, Windows 11 x64 build 26200, Python 3.12.14. Three subagents reviewed Windows integration, audio/timer workers and data/blockers; the primary integrated fixes and performed UI/package checks. No Computer Use was used.

## Reproduced issues and changes

| Area | Failure | Fix and evidence |
| --- | --- | --- |
| Workspace ownership | Source/portable/installed copies used different path identities for one personal database | Main entry now uses the workspace directory as instance identity; six real competing Windows test processes yield one primary |
| Keyboard integration | Suppressed keystrokes affected other apps, repeat/stale callbacks toggled Focus | Non-suppressing release callbacks; remove only owned hooks; generation-gate old callbacks |
| Tray lifecycle | Late worker could recreate icon after quit, or stop could join an unstarted thread | Idempotent start/stop and explicit worker lifetime; unavailable tray is reported for window recovery |
| Windows startup | Registry handles leaked on read/write failures and packaged commands could target the wrong entry | Close handles on every path, minimum access, use actual frozen executable |
| Audio coexistence | Previewing many recordings retained large idle buffers | 64 MiB idle-cache budget, active streams retained; failed/cancelled preparation evicts unused oversized buffers |
| Recording import | External recorder could change WAV bytes during copying | Validate the private copy before database insertion |
| UI/background failures | One failed callback could starve timer ticks or leave audio/data controls busy forever | Isolate each clock step and recover rejected worker submissions |
| Planner concurrency | Parallel checklist edits lost updates; concurrent due polls duplicated reminders | Transaction covers reads and writes, including reminder claims |
| SQLite contention | Backup/restore could retry forever while another process held an exclusive lock | Bounded backup deadline, verified against an actual locked disposable database |
| Hosts coexistence | Malformed owned markers or text-mode rewriting could erase/change unrelated records | Validate marker structure, preserve bytes/newlines, re-read through a Windows deny-write sharing handle |
| App monitor lifecycle | A timed-out old worker could resume after switching modes, or act after a stop request | Each monitor retains its own stop event and checks before its initial action |
| Existing UI/shutdown work | Control sizes and elapsed shutdown reminders had unreleased improvements | Preserved and tested the existing edits, including worker rejection recovery |

## Verification

- 171 unit/regression tests passed (baseline 117). New tests cover failures and coexistence, including native Windows process/file handles.
- Real Tk coexistence smoke passed alongside an independent disposable Tk application and a CPU-load process. Both helpers stayed responsive while Focus exercised all nine views, light/dark, resizing, mini player, timer advance/pause/resume, fake output loss/retry and cleanup.
- Cold light-theme startup, full UI workflow smoke, and close-to-tray/quit lifecycle passed.
- The executable extracted from the final portable ZIP passed all seven bundled sounds, PortAudio import, instance activation, nine views/themes, About and isolated backup/restore; reported version 1.0.1.
- The exact installer passed fresh install, real upgrade from the published 1.0.0 installer, downgrade rejection, running-app protection, Desktop/Start Menu choices, Windows registration and uninstall. Existing workspace databases/settings remained byte-identical. The original Desktop shortcut and startup settings were restored.

## Scope and limits

After the user explicitly authorized stopping the remaining background Focus instances, only those verified Focus processes were stopped before installer QA. No unrelated user applications were closed. Tests did not schedule a real shutdown, sleep/log off Windows, change actual hosts, register actual global keyboard hooks or play audio on real hardware. OS/audio failures were mocked; hosts/database contention used temporary resources. Disposable processes provide real concurrency, not a compatibility certificate for every browser, conferencing client, VPN, antivirus, audio driver or Windows version. Existing workspace database/config files must remain byte-identical through installer testing. No schema migration is required for this release.

The public app/installer/uninstaller remain unsigned; SHA256 verifies file integrity, not publisher identity. Previous releases are retained. Build-tool runtimes, generated intermediates, personal workspace data and unrelated output files are excluded from Git and release artifacts.

## Artifacts

- `Focus-Setup-1.0.1-Windows-x64.exe`: 25009851 bytes; SHA256 `4adbcfc2d26f60f6a7ac13e1ef7889515c41ac160f0b314332bddcaca7ea77a3`.
- `Focus-1.0.1-Windows-x64.zip`: 31751789 bytes; SHA256 `1d34452e365643b63ed01bf930ab72f3814b41817e5de8bc60224c364d64f8d8`.
