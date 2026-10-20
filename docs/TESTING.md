# Verification

Run source tests from `PythonProject` with the project's Python environment:

```powershell
..\.runtime\Scripts\python.exe -B -m unittest discover -s tests -q
..\.runtime\Scripts\python.exe -B tests\smoke_close.py
..\.runtime\Scripts\python.exe -B tests\smoke_ui.py
..\.runtime\Scripts\python.exe -B tests\smoke_startup_theme.py light
```

The 1.0.0 review passed 106 unit/regression tests, the lifecycle smoke, full UI smoke across both themes, and cold light-theme startup. Tests isolate their workspace and mock audio hardware, website blocking, app termination and Windows shutdown. No Computer Use is required. The executable extracted from the final portable ZIP also passed: seven offline sounds and bundled PortAudio, single-instance activation, all nine views in both themes, logo/fonts and About metadata, isolated backup/restore, and final shutdown. The portable shortcut target and icon were verified in a temporary folder.

Coverage includes queued and in-flight playback cancellation; X/tray close; global audio stop; inactive output devices; failed stream closure; late automatic playback callbacks; cleanup failure isolation; duplicate-launch activation; lost tray recovery; blocker concurrency and retries; timer callback/history-write failures; backup/restore; planner and checklist operations; About/contact actions; theme/layout behavior.

Passing these tests verifies the exercised paths and package integrity. It does not certify every possible Windows/driver failure or replace listening on the target output device.

See [installer acceptance checks](INSTALLER.md) for fresh install, upgrade, downgrade rejection, running-app protection, shortcuts, Windows registration and uninstall/data-retention verification.
