Focus 1.0.0 is part of **Spertulo Utility**, created by **Nguyễn Công Trung**.

### Download and run

1. Download **Focus-1.0.0-Windows-x64.zip** below.
2. Extract the complete folder and double-click **Focus.exe**. No Python installation is needed.
3. Keep `_internal` beside the executable. Optionally run **Create Desktop Shortcut.cmd**.

The portable download contains the application, its required runtime, a short guide and dependency notices. It excludes source tests, build tools, virtual environments, cache, workspace databases and personal recordings. `SHA256SUMS.txt` is provided for verification.

### Included

- Focus timer, custom modes and distraction blocking.
- Planner, schedules, checklists and reminders.
- Seven offline sounds, independent volume controls and personal WAV imports.
- Shutdown Timer, history, statistics and workspace backup/restore.
- Light/dark appearance, mini player and About/contact links.

### Reliability fixes

- Closing the window stops audio and cancels pending playback while optionally keeping the timer in the tray.
- Global **Stop all sounds** controls in Sound Studio and the tray.
- One running instance, recovery when the tray icon is lost, and independent resource cleanup.
- Fixed blocker stop/quit races, stale audio callbacks and timer/history error handling.

Your workspace remains in `%USERPROFILE%\.deepfocus`, outside the app folder. Quit an older running version before opening this release. Website blocking may require administrator access.
