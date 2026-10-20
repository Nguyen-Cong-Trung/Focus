import os
import sys
import winreg

def _get_registry_key():
    return winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_ALL_ACCESS
    )

def set_run_on_startup(enable: bool, app_name: str = "DeepFocus") -> bool:
    """Enable or disable running the application on Windows startup.
    Returns True if successful, False otherwise.
    """
    try:
        key = _get_registry_key()
        
        if enable:
            pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
            main_script = os.path.abspath(sys.argv[0])
            
            if main_script.endswith('.py'):
                command = f'"{pythonw_path}" "{main_script}"'
            else:
                command = f'"{main_script}"'
                
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass # Already disabled
                
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Failed to set startup: {e}")
        return False

def is_run_on_startup(app_name: str = "DeepFocus") -> bool:
    """Check if the application is set to run on startup."""
    try:
        key = _get_registry_key()
        value, _ = winreg.QueryValueEx(key, app_name)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False
