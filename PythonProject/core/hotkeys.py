"""Global focus shortcut without consuming other applications' keystrokes."""
import logging
import keyboard
import threading
from typing import Callable, Optional


class HotkeyManager:
    def __init__(self):
        self._enabled = False
        self._current_bind = ""
        self._callback: Optional[Callable] = None
        self._lock = threading.RLock()
        self._registrations = []
        self._generation = 0

    def set_callback(self, callback: Callable):
        with self._lock:
            self._callback = callback

    def _remove_owned_locked(self):
        remaining = []
        for registration in self._registrations:
            try:
                # The returned registration owns exactly our hook. Removing by
                # shortcut text can remove another component's matching hook.
                keyboard.remove_hotkey(registration)
            except Exception:
                logging.getLogger(__name__).exception('Could not remove a Focus shortcut hook')
                remaining.append(registration)
        self._registrations = remaining

    def enable(self, bind: str = "ctrl+shift+space"):
        with self._lock:
            if self._enabled and bind == self._current_bind:
                return True
            self._generation += 1
            self._enabled = False
            self._remove_owned_locked()
            self._current_bind = bind
            generation = self._generation
            try:
                registration = keyboard.add_hotkey(
                    bind, lambda: self._on_hotkey(generation), suppress=False,
                    trigger_on_release=True)
                self._registrations.append(registration)
                self._enabled = True
                return True
            except Exception:
                logging.getLogger(__name__).exception('Could not enable hotkey')
                return False

    def disable(self):
        with self._lock:
            # A listener may already have queued a callback from the old bind.
            self._enabled = False
            self._generation += 1
            self._remove_owned_locked()

    def _on_hotkey(self, generation):
        with self._lock:
            if not self._enabled or generation != self._generation:
                return
        threading.Thread(target=self._invoke, args=(generation,), daemon=True,
                         name='focus-hotkey').start()

    def _invoke(self, generation):
        with self._lock:
            if not self._enabled or generation != self._generation:
                return
            callback = self._callback
        if callback:
            try:
                callback()
            except Exception:
                logging.getLogger(__name__).exception('Focus shortcut action failed')
