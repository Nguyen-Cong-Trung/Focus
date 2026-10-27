"""Manage only Focus's Windows sign-in entry, with least-privilege handles."""
import logging
import os
from pathlib import Path
import sys
import winreg


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _get_registry_key(access=winreg.KEY_QUERY_VALUE, create=False):
    function = winreg.CreateKeyEx if create else winreg.OpenKey
    return function(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)


def _startup_command():
    if getattr(sys, 'frozen', False):
        return '"' + os.path.abspath(sys.executable) + '"'
    main_script = os.path.abspath(sys.argv[0])
    if main_script.lower().endswith(('.py', '.pyw')):
        executable = Path(sys.executable)
        windowed = executable.with_name('pythonw.exe')
        if executable.name.lower() == 'python.exe' and windowed.is_file():
            executable = windowed
        return f'"{executable}" "{main_script}"'
    return '"' + main_script + '"'


def set_run_on_startup(enable: bool, app_name: str = "DeepFocus") -> bool:
    key = None
    try:
        key = _get_registry_key(winreg.KEY_SET_VALUE, create=enable)
        if enable:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        return True
    except FileNotFoundError:
        return not enable
    except OSError:
        logging.getLogger(__name__).exception('Could not update the Focus sign-in setting')
        return False
    finally:
        if key is not None:
            winreg.CloseKey(key)


def is_run_on_startup(app_name: str = "DeepFocus") -> bool:
    key = None
    try:
        key = _get_registry_key(winreg.KEY_QUERY_VALUE)
        value, kind = winreg.QueryValueEx(key, app_name)
        return kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and bool(value.strip())
    except OSError:
        return False
    finally:
        if key is not None:
            winreg.CloseKey(key)
