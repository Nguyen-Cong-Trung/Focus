# Focus — Spertulo Utility

App name: **Focus**. Suite: **Spertulo Utility**. Version: **1.0.1**.

- `focus-logo.png`: exact copy of the user-provided `Logo Focus.png` in the project root. The red square and white F are preserved.
- `focus.ico`: Windows icon converted from that PNG at 16, 24, 32, 48, 64, 128 and 256 pixels.
- `Focus.lnk`: project-local copy of the shortcut installed on the desktop.
- `creator.json`: creator information displayed in Settings → About Focus: Nguyễn Công Trung, GitHub, email and LinkedIn. Edit this file to update these details; the About dialog reads it when opened.

The same logo is used in the app header, Settings, window/taskbar and notification area, and desktop shortcut. Do not stretch or replace the supplied artwork.

Run `Install Desktop Shortcut.ps1` to recreate the desktop shortcut. Existing workspace storage, backup format identifiers and startup registry keys retain their legacy names for compatibility with previous installations.

Previous generated artwork and prompts are kept in `maintenance/legacy-branding` for reference; they are not used by Focus.
