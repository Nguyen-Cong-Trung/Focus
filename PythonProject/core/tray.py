"""Windows notification-area icon using the OS API; no additional dependency."""
import os
import threading
import logging


class TrayIcon:
    def __init__(self, icon_path, dispatch):
        self.icon_path, self.dispatch = str(icon_path), dispatch
        self.available = False
        self.status = 'Ready to focus'
        self._ready = threading.Event()
        self._hwnd = None
        self._data_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._stopping = threading.Event()
        self.thread = None

    def start(self):
        if os.name != 'nt' or os.environ.get('DEEPFOCUS_TESTING') == '1':
            return False
        with self._lifecycle_lock:
            if self._stopping.is_set():
                return False
            if self.thread is None or not self.thread.is_alive():
                self._ready.clear()
                self.thread = threading.Thread(target=self._run, daemon=True, name='tray')
                self.thread.start()
        self._ready.wait(3)
        return self.available

    def update(self, status):
        if status==self.status: return
        self.status = status
        if self.available:
            with self._data_lock:
                if not self.available or self._stopping.is_set():
                    return
                self._data.szTip = ('Focus · ' + status)[:127]
                if not self._shell.Shell_NotifyIconW(1, self._ctypes.byref(self._data)):
                    self.available = False

    def notify(self, title, message):
        if not self.available:
            return False
        with self._data_lock:
            if not self.available or self._stopping.is_set():
                return False
            self._data.szInfoTitle = title[:63]
            self._data.szInfo = message[:255]
            self._data.dwInfoFlags = 1
            self._data.uFlags |= 0x10
            try:
                success = bool(self._shell.Shell_NotifyIconW(1, self._ctypes.byref(self._data)))
                if not success:
                    self.available = False
                return success
            finally:
                self._data.uFlags &= ~0x10

    def stop(self):
        self._stopping.set()
        self.available = False
        with self._lifecycle_lock:
            thread, hwnd = self.thread, self._hwnd
        if hwnd:
            self._user.PostMessageW(hwnd, 0x0010, 0, 0)
        if thread and threading.current_thread() is not thread:
            thread.join(timeout=2)

    def _run(self):
        import ctypes as C
        from ctypes import wintypes as W
        try:
            if self._stopping.is_set():
                return
            user, shell, kernel = C.windll.user32, C.windll.shell32, C.windll.kernel32
            self._ctypes, self._user, self._shell = C, user, shell
            LRESULT = C.c_ssize_t
            WNDPROC = C.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
            class WNDCLASS(C.Structure):
                _fields_ = [('style',W.UINT),('lpfnWndProc',WNDPROC),('cbClsExtra',C.c_int),('cbWndExtra',C.c_int),
                    ('hInstance',W.HINSTANCE),('hIcon',W.HICON),('hCursor',W.HANDLE),('hbrBackground',W.HBRUSH),
                    ('lpszMenuName',W.LPCWSTR),('lpszClassName',W.LPCWSTR)]
            class GUID(C.Structure):
                _fields_=[('Data1',W.DWORD),('Data2',W.WORD),('Data3',W.WORD),('Data4',C.c_ubyte*8)]
            class NOTIFYICONDATA(C.Structure):
                _fields_=[('cbSize',W.DWORD),('hWnd',W.HWND),('uID',W.UINT),('uFlags',W.UINT),
                    ('uCallbackMessage',W.UINT),('hIcon',W.HICON),('szTip',W.WCHAR*128),('dwState',W.DWORD),
                    ('dwStateMask',W.DWORD),('szInfo',W.WCHAR*256),('uTimeout',W.UINT),
                    ('szInfoTitle',W.WCHAR*64),('dwInfoFlags',W.DWORD),('guidItem',GUID),('hBalloonIcon',W.HICON)]
            # Declare pointer-sized Windows signatures explicitly (important on 64-bit Python).
            user.CreateWindowExW.argtypes=[W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,C.c_int,C.c_int,C.c_int,C.c_int,W.HWND,W.HMENU,W.HINSTANCE,C.c_void_p]
            user.CreateWindowExW.restype=W.HWND
            user.DefWindowProcW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
            user.DefWindowProcW.restype=LRESULT
            user.RegisterClassW.argtypes=[C.POINTER(WNDCLASS)]
            kernel.GetModuleHandleW.argtypes=[W.LPCWSTR]
            kernel.GetModuleHandleW.restype=W.HMODULE
            user.LoadImageW.argtypes=[W.HINSTANCE,W.LPCWSTR,W.UINT,C.c_int,C.c_int,W.UINT]
            user.LoadImageW.restype=W.HANDLE
            user.CreatePopupMenu.restype=W.HMENU
            user.AppendMenuW.argtypes=[W.HMENU,W.UINT,C.c_size_t,W.LPCWSTR]
            user.TrackPopupMenu.argtypes=[W.HMENU,W.UINT,C.c_int,C.c_int,C.c_int,W.HWND,C.c_void_p]
            user.SetForegroundWindow.argtypes=[W.HWND]
            user.DestroyMenu.argtypes=[W.HMENU]
            user.DestroyWindow.argtypes=[W.HWND]
            user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
            user.DestroyIcon.argtypes=[W.HICON]
            shell.Shell_NotifyIconW.argtypes=[W.DWORD,C.POINTER(NOTIFYICONDATA)]
            user.UnregisterClassW.argtypes=[W.LPCWSTR,W.HINSTANCE]
            user.RegisterWindowMessageW.argtypes=[W.LPCWSTR]
            taskbar_created=user.RegisterWindowMessageW('TaskbarCreated')
            self._callback_message=0x8001
            def menu(hwnd):
                popup=user.CreatePopupMenu()
                user.AppendMenuW(popup,2,0,self.status)
                user.AppendMenuW(popup,0x800,0,None)
                for ident, text in ((1,'Open Focus'),(2,'Start / Pause'),(3,'Stop session'),
                                    (6,'Stop all sounds'),(4,'Emergency unblock'),(5,'Quit Focus')):
                    user.AppendMenuW(popup,0,ident,text)
                point=W.POINT()
                user.GetCursorPos(C.byref(point))
                user.SetForegroundWindow(hwnd)
                chosen=user.TrackPopupMenu(popup,0x100|0x2,point.x,point.y,0,hwnd,None)
                user.DestroyMenu(popup)
                if chosen:
                    self.dispatch({1:'open',2:'toggle',3:'stop',4:'emergency',5:'quit',6:'stop_sounds'}[chosen])
                user.PostMessageW(hwnd,0,0,0)
            @WNDPROC
            def proc(hwnd,msg,wp,lp):
                try:
                    if taskbar_created and msg==taskbar_created and hasattr(self,'_data'):
                        if not self._stopping.is_set():
                            self.available = bool(shell.Shell_NotifyIconW(0,C.byref(self._data)))
                        return 0
                    if msg==self._callback_message:
                        if lp==0x203:
                            self.dispatch('open')
                        elif lp in (0x205,0x7B):
                            menu(hwnd)
                        return 0
                    if msg==0x0010:
                        user.DestroyWindow(hwnd)
                        return 0
                    if msg==0x0002:
                        shell.Shell_NotifyIconW(2,C.byref(self._data))
                        self.available=False
                        user.PostQuitMessage(0)
                        return 0
                except Exception:
                    logging.getLogger(__name__).exception('Tray callback failed')
                return user.DefWindowProcW(hwnd,msg,wp,lp)
            self._proc=proc
            instance=kernel.GetModuleHandleW(None)
            name='DeepFocusTray'+str(id(self))
            wc=WNDCLASS()
            wc.lpfnWndProc, wc.hInstance, wc.lpszClassName=proc,instance,name
            if not user.RegisterClassW(C.byref(wc)):
                raise OSError('Could not register tray window')
            hwnd=user.CreateWindowExW(0,name,name,0,0,0,0,0,None,None,instance,None)
            if not hwnd: raise OSError('Could not create tray window')
            icon=user.LoadImageW(None,self.icon_path,1,32,32,0x10)
            data=NOTIFYICONDATA()
            data.cbSize=C.sizeof(data)
            data.hWnd,data.uID,data.uFlags,data.uCallbackMessage,data.hIcon=hwnd,1,1|2|4,self._callback_message,icon
            data.szTip='Focus'
            self._data=data
            self._hwnd=hwnd
            self.available = not self._stopping.is_set() and bool(shell.Shell_NotifyIconW(0,C.byref(data)))
            self._ready.set()
            if not self.available:
                user.DestroyWindow(hwnd)
            message=W.MSG()
            while user.GetMessageW(C.byref(message),None,0,0)>0:
                user.TranslateMessage(C.byref(message))
                user.DispatchMessageW(C.byref(message))
            if icon: user.DestroyIcon(icon)
            user.UnregisterClassW(C.c_wchar_p(name),instance)
        except Exception:
            logging.getLogger(__name__).exception('Tray icon unavailable')
            self.available=False
        finally:
            self.available=False
            self._hwnd=None
            self._ready.set()
