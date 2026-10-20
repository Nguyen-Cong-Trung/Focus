"""Exercise the actual installer and uninstaller without Computer Use.

Creates a temporary installation and a uniquely named Start Menu group. Any
existing desktop shortcut/startup values are backed up and restored in finally.
Never opens the user's database; only adds/removes a uniquely named data marker.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import winreg

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.release-work/installer-qa'
INSTALL = WORK / 'Installed Focus'
SETUP = ROOT / 'releases/Focus-Setup-1.0.0-Windows-x64.exe'
KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{139698E0-3B7B-4867-AB38-C8B37B01C9E1}_is1'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
sys.path.insert(0, str(ROOT / 'PythonProject'))
from core.instance import SingleInstance


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def known_folder(csidl):
    buffer = C.create_unicode_buffer(32768)
    shell = C.WinDLL('shell32')
    shell.SHGetFolderPathW.argtypes = [W.HWND, C.c_int, W.HANDLE, W.DWORD, W.LPWSTR]
    if shell.SHGetFolderPathW(None, csidl, None, 0, buffer) != 0:
        raise RuntimeError('Cannot resolve Windows shortcut directory')
    return Path(buffer.value)


def run(exe, args, expected=0, timeout=150):
    process = subprocess.run([str(exe), *args], timeout=timeout, creationflags=0x08000000)
    if expected is None:
        assert process.returncode != 0, 'An unsafe install/uninstall was allowed'
    else:
        assert process.returncode == expected, (str(exe), process.returncode)
    return process.returncode


def registration():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return {winreg.EnumValue(key, i)[0]: winreg.EnumValue(key, i)[1]
                    for i in range(winreg.QueryInfoKey(key)[1])}
    except FileNotFoundError:
        return None


def shortcut(path):
    assert path.is_file(), 'Shortcut not created: ' + str(path)
    script = "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); " \
             "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:FOCUS_QA_LINK); " \
             "@{target=$s.TargetPath;icon=$s.IconLocation;directory=$s.WorkingDirectory}|ConvertTo-Json -Compress"
    env = dict(os.environ, FOCUS_QA_LINK=str(path))
    output = subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                     env=env, encoding='utf-8-sig', creationflags=0x08000000)
    return json.loads(output)


def set_file_version(path, version):
    from PyInstaller.utils.win32 import versioninfo
    text = (ROOT / 'build_tools/windows-version.txt').read_text(encoding='utf-8')
    text = text.replace('(1,0,0,0)', version)
    version_file = WORK / 'test-version.txt'
    version_file.write_text(text, encoding='utf-8')
    versioninfo.write_version_info_to_executable(str(path), versioninfo.load_version_info_from_text_file(version_file))


def main():
    if registration():
        raise RuntimeError('Focus is already installed. Refusing to replace a real installation during QA.')
    WORK.mkdir(parents=True, exist_ok=True)
    if INSTALL.exists():
        raise RuntimeError('QA installation directory already exists; inspect before reusing.')
    checks = []
    report = {'ok': False, 'checks': checks, 'installer_sha256': sha(SETUP)}
    desktop = known_folder(0x10) / 'Focus.lnk'
    desktop_backup = desktop.read_bytes() if desktop.exists() else None
    if desktop_backup is not None:
        (WORK / 'original-desktop-shortcut.lnk').write_bytes(desktop_backup)
    group = 'Focus Installer QA ' + uuid.uuid4().hex[:12]
    menu = known_folder(2) / group
    data = Path.home() / '.deepfocus'
    data.mkdir(exist_ok=True)
    marker = data / ('installer-qa-' + uuid.uuid4().hex + '.txt')
    marker.write_text('preserve this workspace marker', encoding='utf-8')
    workspace_before = {p.name: sha(p) for p in data.iterdir()
                        if p.is_file() and p.suffix in ('.db', '.json')}
    startup_saved = {}
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        for name in ('DeepFocus', 'Focus'):
            try:
                startup_saved[name] = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                startup_saved[name] = None
    args = ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
            '/DIR=' + str(INSTALL), '/GROUP=' + group, '/TASKS=desktopicon']
    uninstall = INSTALL / 'unins000.exe'
    try:
        # Creating the app's own guard proves Setup's detection matches runtime.
        guard = SingleInstance(WORK / 'guard')
        try:
            code = run(SETUP, [*args, '/LOG=' + str(WORK / 'blocked-install.log')], expected=None)
            assert not INSTALL.exists()
            assert 'Focus is currently running' in (WORK / 'blocked-install.log').read_text(encoding='utf-8-sig')
            checks.append('running Focus blocks installation (exit %s)' % code)
        finally:
            guard.close()

        # Silent mode must enforce the same workspace protection as the wizard.
        code = run(SETUP, [*args, '/DIR=' + str(data), '/LOG=' + str(WORK / 'protected-data.log')], expected=None)
        assert not (data / 'Focus.exe').exists() and registration() is None
        assert 'outside your Focus workspace' in (WORK / 'protected-data.log').read_text(encoding='utf-8-sig')
        checks.append('workspace folder cannot be selected as the install folder')

        # Back up rather than permanently replacing the user's existing link.
        if desktop.exists():
            desktop.unlink()
        run(SETUP, [*args, '/LOG=' + str(WORK / 'fresh-install.log')])
        registered = registration()
        assert registered['DisplayName'] == 'Focus'
        assert registered['DisplayVersion'] == '1.0.0'
        assert registered['Publisher'] == 'Spertulo Utility'
        assert Path(registered['InstallLocation']).resolve() == INSTALL.resolve()
        assert registered['NoModify'] == 1 and registered['NoRepair'] == 1
        assert uninstall.is_file() and (INSTALL / '_internal').is_dir()
        assert not (INSTALL / 'Create Desktop Shortcut.cmd').exists()
        for path in (desktop, menu / 'Focus.lnk'):
            link = shortcut(path)
            assert Path(link['target']).resolve() == (INSTALL / 'Focus.exe').resolve(), link
            assert Path(link['directory']).resolve() == INSTALL.resolve(), link
            assert 'Focus.exe' in link['icon'] or link['icon'] == ',0', link
        assert (menu / 'Uninstall Focus.lnk').is_file()
        checks.append('fresh per-user install; Installed apps metadata; Desktop and Start Menu shortcuts')

        app_report = WORK / 'installed-app-check.json'
        run(INSTALL / 'Focus.exe', ['--self-test', str(app_report)])
        assert json.loads(app_report.read_text(encoding='utf-8'))['ok']
        checks.append('installed executable: audio, all views/themes, About, backup/restore and shutdown')

        # Simulate an earlier installed file version, then run the real upgrade.
        unrelated = INSTALL / 'keep-user-file.txt'
        unrelated.write_text('not owned by installer', encoding='utf-8')
        set_file_version(INSTALL / 'Focus.exe', '(0,9,0,0)')
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
            winreg.SetValueEx(key, 'DisplayVersion', 0, winreg.REG_SZ, '0.9.0')
        # Neither the directory nor task choice is passed: reuse saved values.
        upgrade_args = [a for a in args if not a.startswith(('/DIR=', '/TASKS='))]
        desktop.unlink()
        run(SETUP, [*upgrade_args, '/LOG=' + str(WORK / 'upgrade.log')])
        assert sha(INSTALL / 'Focus.exe') == sha(ROOT / 'dist/Focus/Focus.exe')
        assert registration()['DisplayVersion'] == '1.0.0'
        assert marker.exists() and unrelated.exists()
        assert len(list(INSTALL.glob('unins*.exe'))) == 1
        assert desktop.exists() and Path(shortcut(desktop)['target']).resolve() == (INSTALL / 'Focus.exe').resolve()
        checks.append('upgrade from simulated 0.9.0 retains install path, shortcut preference, workspace and a single uninstall entry')

        # Refuse to overwrite a newer version, including unattended setup.
        set_file_version(INSTALL / 'Focus.exe', '(2,0,0,0)')
        newer_hash = sha(INSTALL / 'Focus.exe')
        run(SETUP, [*args, '/LOG=' + str(WORK / 'downgrade.log')], expected=None)
        assert 'A newer version of Focus is installed' in (WORK / 'downgrade.log').read_text(encoding='utf-8-sig')
        assert sha(INSTALL / 'Focus.exe') == newer_hash
        (INSTALL / 'Focus.exe').write_bytes((ROOT / 'dist/Focus/Focus.exe').read_bytes())
        checks.append('downgrade protection keeps a newer executable intact')

        guard = SingleInstance(WORK / 'guard')
        try:
            code = run(uninstall, ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                '/LOG=' + str(WORK / 'blocked-uninstall.log')], expected=None)
            assert (INSTALL / 'Focus.exe').is_file() and registration()
            assert 'Focus is currently running' in (WORK / 'blocked-uninstall.log').read_text(encoding='utf-8-sig')
            checks.append('running Focus blocks uninstall (exit %s)' % code)
        finally:
            guard.close()

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, 'DeepFocus', 0, winreg.REG_SZ, '"' + str(INSTALL / 'Focus.exe') + '"')
            winreg.SetValueEx(key, 'Focus', 0, winreg.REG_SZ, '"C:\\Unrelated Focus\\Focus.exe"')
        run(uninstall, ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/LOG=' + str(WORK / 'uninstall.log')])
        # The copied uninstaller finishes file cleanup just after its parent.
        for _ in range(50):
            if not (INSTALL / 'Focus.exe').exists() and not desktop.exists() and registration() is None:
                break
            time.sleep(.1)
        assert not (INSTALL / 'Focus.exe').exists() and registration() is None
        assert not desktop.exists() and not (menu / 'Focus.lnk').exists()
        assert not (menu / 'Uninstall Focus.lnk').exists()
        assert marker.exists() and unrelated.exists()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            try:
                winreg.QueryValueEx(key, 'DeepFocus')
                raise AssertionError('Owned startup entry remains')
            except FileNotFoundError:
                pass
            assert winreg.QueryValueEx(key, 'Focus')[0] == '"C:\\Unrelated Focus\\Focus.exe"'
        checks.append('uninstall removes app, shortcuts, registration and owned startup; preserves unrelated files/entries')

        # Exercise the opposite shortcut choices on a second clean install.
        minimal = WORK / 'No Shortcuts'
        minimal_group = group + ' No Shortcuts'
        run(SETUP, ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
            '/DIR=' + str(minimal), '/GROUP=' + minimal_group, '/TASKS=', '/NOICONS',
            '/LOG=' + str(WORK / 'no-shortcuts-install.log')])
        try:
            assert (minimal / 'Focus.exe').is_file() and registration()
            assert not desktop.exists() and not (known_folder(2) / minimal_group / 'Focus.lnk').exists()
        finally:
            run(minimal / 'unins000.exe', ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                '/LOG=' + str(WORK / 'no-shortcuts-uninstall.log')])
        assert registration() is None
        checks.append('optional Desktop and Start Menu shortcuts can both be omitted')
        assert all((data / name).is_file() and sha(data / name) == digest for name, digest in workspace_before.items())
        checks.append('existing workspace databases/settings remain byte-identical')
        report['ok'] = True
    except BaseException:
        import traceback
        report['error'] = traceback.format_exc()
        raise
    finally:
        # On a failed check, remove only our exact registered QA installation
        # before restoring the original shortcut (Uninstall owns Focus.lnk).
        remaining = registration()
        if remaining and Path(remaining.get('InstallLocation', '')).resolve() == INSTALL.resolve() and uninstall.is_file():
            try:
                run(uninstall, ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'])
            except Exception as error:
                report['cleanup_error'] = str(error)
        # Always put the original desktop link and startup values back.
        if desktop_backup is not None:
            desktop.write_bytes(desktop_backup)
        elif desktop.exists():
            link = shortcut(desktop)
            if Path(link['target']).resolve() == (INSTALL / 'Focus.exe').resolve():
                desktop.unlink()
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            for name, saved in startup_saved.items():
                if saved is not None:
                    winreg.SetValueEx(key, name, 0, saved[1], saved[0])
                else:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
        marker.unlink(missing_ok=True)
        (ROOT / '.release-work/installer-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
