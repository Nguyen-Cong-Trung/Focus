Focus **1.0.1** — Spertulo Utility

This maintenance release improves reliability when Focus runs alongside other applications and Windows features.

### Fixes

- Installed, source and portable copies now coordinate around the same personal workspace, preventing two current copies from editing it at once.
- Global shortcuts no longer consume other applications' keystrokes; stale callbacks and repeated key presses are controlled.
- Fixed tray start/stop races, sign-in registry handle leaks and packaged startup commands.
- Limited idle audio buffer caching to 64 MiB while preserving active playback. Cancelled/failed preparation releases oversized idle buffers.
- Validate the copied WAV before importing, so recordings changed by another application are rejected safely.
- A failed Windows/UI callback no longer stops timer ticks or subsequent completed operations. Audio/data buttons recover when work cannot be queued.
- Planner checklist updates and reminder claims are transactional, preventing lost edits and duplicate notifications.
- SQLite backup/restore stops waiting when an external lock exceeds its timeout.
- Website blocking preserves unrelated hosts bytes and entries, rejects malformed owned sections, and protects writes from concurrent editors. Stopped app monitors cannot restart themselves after mode changes.
- Includes existing control-size improvements and shutdown-reminder/control recovery fixes.

### Downloads

**Focus-Setup-1.0.1-Windows-x64.exe** is the recommended offline installer. Quit Focus (including its tray icon) before updating. Installation, Desktop/Start Menu options and uninstall retain your workspace in `%USERPROFILE%\.deepfocus`.

**Focus-1.0.1-Windows-x64.zip** is the portable alternative. Extract the complete folder and keep `_internal` beside **Focus.exe**. Python installation is not required for either download.

### Verification

171 unit/regression tests passed, plus cold light-theme startup, UI and close-lifecycle checks. A real Tk integration check exercised both themes, all nine views, resizing, mini player, audio device-loss simulation and timer pause/resume alongside two disposable Windows processes (an independent Tk app and a CPU worker). Separate native tests launched six competing processes and verified one workspace owner.

Audio hardware, app termination, hosts modifications, actual shutdown and sign-in registration are mocked or redirected to disposable test resources. No user applications were closed and no Computer Use was used. These checks do not certify every driver, VPN, antivirus or Windows configuration. See the repository's `docs/QA-1.0.1.md` for results and limitations.

### Signing

This release remains **unsigned** because a trusted publisher code-signing certificate is not available. Windows may show SmartScreen or an unknown-publisher prompt. `SHA256SUMS.txt` verifies file integrity; it is not a digital signature.
