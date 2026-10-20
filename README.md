<p align="center"><img src="branding/focus-logo.png" width="88" alt="Focus logo"></p>
<h1 align="center">Focus</h1>
<p align="center">Spertulo Utility · Version 1.0.0 · Windows x64</p>

A personal workspace for focused work, planning and a calmer daily rhythm.

## Download

[**Download Focus for Windows**](https://github.com/Nguyen-Cong-Trung/Focus/releases/latest)

Download `Focus-1.0.0-Windows-x64.zip` from Releases, extract the whole folder, and open **Focus.exe**. **Python installation is not required.** Keep the `_internal` folder beside the executable. Run **Create Desktop Shortcut.cmd** if you want a desktop shortcut. `SHA256SUMS.txt` is included with the release for integrity verification.

## What you can do

- Focus with a Pomodoro timer, custom modes, breaks and daily goals.
- Plan tasks, schedules and checklists with reminders and linked focus sessions.
- Block distracting websites and Windows applications during focus.
- Mix seven offline sounds: recorded rain, brown/pink/white noise, a 432 Hz tone and two stereo binaural presets. Import your own PCM WAV recordings.
- Schedule or cancel a Windows shutdown after confirmation.
- Review history and statistics; back up and restore your workspace.
- Choose light or dark appearance and use a compact mini player.

## Closing and audio controls

Closing the window **stops all sounds**, including pending playback. With **Keep working in the tray** enabled, the timer continues in the notification area; automatic audio stays suspended while the window is hidden. Use **Stop all sounds** in Sound Studio or the tray menu to stop the mix without ending the session. Use **Quit Focus** to exit completely.

Launching Focus again reopens the existing app. If its tray icon becomes unavailable, the hidden window reopens so controls remain accessible.

## Your workspace

Data is stored separately in `%USERPROFILE%\.deepfocus`. App updates do not require deleting this folder. Use **Settings → Your data** to create or restore a backup. No personal workspace or recordings are included in the download.

Website blocking may require administrator access. App blocking closes the selected applications during focus. Shutdown Timer only schedules a Windows shutdown after you confirm it; save your documents before using it.

## Creator

Created by **Nguyễn Công Trung**, as part of **Spertulo Utility**.

- [More tools on GitHub](https://github.com/Nguyen-Cong-Trung)
- [LinkedIn](https://www.linkedin.com/in/nguyencongtrung)
- Email: trungcong0106a7@gmail.com

These links are also available in **Settings → About Focus**.

## Run from source

Use 64-bit Python 3.12 on Windows. Run **Setup.cmd**, then **Focus.cmd**. Dependencies are in `PythonProject/requirements.txt`. Older `DeepFocus.cmd` shortcuts remain compatible.

See [building the portable package](docs/BUILD.md) and [verification](docs/TESTING.md). Runtime environments, build intermediates, tests and internal development notes are excluded from the downloadable application.

## Credits

The logo was supplied by the creator. Rain is derived from a public-domain recording by Shizhao; [source and preparation](PythonProject/assets/audio/README.md). Inter fonts retain their bundled license. Dependency notices and license texts are included in the Windows download.
