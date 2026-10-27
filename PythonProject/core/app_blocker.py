import subprocess
import threading
from typing import Optional


class AppBlocker:
    def __init__(self):
        self._monitoring: bool = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()
        self._blocked_apps: list[str] = []

    def kill_apps(self, app_names: list[str]) -> list[str]:
        if not app_names:
            return []
            
        killed = []
        try:
            # Batch all apps into a single taskkill command for massive CPU saving
            cmd = ["taskkill", "/F"]
            for app_name in app_names:
                cmd.extend(["/IM", app_name])
                
            subprocess.run(
                cmd,
                capture_output=True, timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # We don't parse the output for exact killed apps anymore since return value is ignored
            killed = app_names 
        except Exception:
            pass
        return killed

    def start_monitoring(self, app_names: list[str], interval: int = 30) -> None:
        self.stop_monitoring()
        self._blocked_apps = list(app_names)
        # A timed-out old worker must retain its signaled event. Clearing a
        # shared event resurrected it when switching modes after a slow OS call.
        self._stop_event = threading.Event()
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(self._blocked_apps, interval, self._stop_event),
            daemon=True
        )
        self._monitor_thread.start()

    def _monitor_loop(self, app_names: list[str], interval: int, stop_event=None) -> None:
        stop_event = stop_event if stop_event is not None else self._stop_event
        if not stop_event.is_set():
            self.kill_apps(app_names)
        while not stop_event.is_set():
            stop_event.wait(interval)
            if not stop_event.is_set():
                self.kill_apps(app_names)

    def request_stop(self) -> None:
        self._stop_event.set()

    def stop_monitoring(self) -> None:
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        self._monitoring = False

    @property
    def is_monitoring(self) -> bool:
        return self._monitoring

    def cleanup(self) -> None:
        self.stop_monitoring()
