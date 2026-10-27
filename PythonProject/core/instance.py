"""One running Focus per user/project, including while its window is hidden."""
import getpass
import hashlib
import os
from pathlib import Path


class SingleInstance:
    # Stable name shared with Setup/Uninstall, independent of bundle location.
    INSTALLER_MUTEX = 'Local\\Spertulo.Focus.Running'

    def __init__(self, project_path):
        self.is_primary = True
        self._handles = []
        self._event = None
        if os.name != 'nt':
            return
        import ctypes as C
        from ctypes import wintypes as W
        self._kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel = self._kernel
        kernel.CreateEventW.argtypes = [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]
        kernel.CreateEventW.restype = W.HANDLE
        kernel.CreateMutexW.argtypes = [C.c_void_p, W.BOOL, W.LPCWSTR]
        kernel.CreateMutexW.restype = W.HANDLE
        kernel.SetEvent.argtypes = [W.HANDLE]
        kernel.SetEvent.restype = W.BOOL
        kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
        kernel.WaitForSingleObject.restype = W.DWORD
        kernel.CloseHandle.argtypes = [W.HANDLE]
        kernel.CloseHandle.restype = W.BOOL
        identity = os.path.normcase(str(Path(project_path).resolve())) + ':' + getpass.getuser()
        key = hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]
        # Create the event first so a second launch can signal during startup.
        self._event = kernel.CreateEventW(None, False, False, 'Local\\Spertulo.Focus.Open.' + key)
        if not self._event:
            raise C.WinError(C.get_last_error())
        self._handles.append(self._event)
        mutex = kernel.CreateMutexW(None, False, 'Local\\Spertulo.Focus.Instance.' + key)
        error = C.get_last_error()
        if not mutex:
            self.close()
            raise C.WinError(error)
        self._handles.append(mutex)
        self.is_primary = error != 183  # ERROR_ALREADY_EXISTS
        running = kernel.CreateMutexW(None, False, self.INSTALLER_MUTEX)
        if not running:
            error = C.get_last_error()
            self.close()
            raise C.WinError(error)
        self._handles.append(running)

    def activate(self):
        return bool(self._event and self._kernel.SetEvent(self._event))

    def consume_activation(self):
        return bool(self._event and self._kernel.WaitForSingleObject(self._event, 0) == 0)

    def close(self):
        for handle in self._handles:
            self._kernel.CloseHandle(handle)
        self._handles.clear()
        self._event = None
