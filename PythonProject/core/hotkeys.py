import keyboard
import threading
from typing import Callable, Optional

class HotkeyManager:
    def __init__(self):
        self._enabled = False
        self._current_bind = ""
        self._callback: Optional[Callable] = None
        self._lock = threading.Lock()

    def set_callback(self, callback: Callable):
        """Set the function to call when hotkey is pressed."""
        self._callback = callback

    def enable(self, bind: str = "ctrl+shift+space"):
        """Enable the global hotkey."""
        with self._lock:
            if self._enabled and self._current_bind:
                try:
                    keyboard.remove_hotkey(self._current_bind)
                except Exception:
                    pass
            
            self._current_bind = bind
            self._enabled = False
            
            try:
                keyboard.add_hotkey(self._current_bind, self._on_hotkey, suppress=True)
                self._enabled = True
                return True
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("Could not enable hotkey")
                return False

    def disable(self):
        """Disable the global hotkey."""
        with self._lock:
            if self._enabled and self._current_bind:
                try:
                    keyboard.remove_hotkey(self._current_bind)
                except Exception:
                    pass
            self._enabled = False

    def _on_hotkey(self):
        """Called when hotkey is triggered."""
        if self._callback:
            # Call in a way that doesn't block the keyboard listener
            threading.Thread(target=self._callback, daemon=True).start()
