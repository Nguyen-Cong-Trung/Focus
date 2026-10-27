"""Schedule Windows shutdown only when explicitly requested by the user."""
import os
import subprocess
import time
from datetime import datetime, timedelta


class ShutdownScheduler:
    MAX_SECONDS = 315360000

    def __init__(self, persist=False):
        self.deadline = self._monotonic_deadline = None
        self.persist = persist
        self.restored = False
        if persist:
            from utils.constants import load_config
            record = load_config().get('shutdown_record')
            if isinstance(record, dict):
                try:
                    deadline = datetime.fromisoformat(record['deadline'])
                    remaining = (deadline-datetime.now()).total_seconds()
                    # An expired reminder must not lock the scheduling controls
                    # after a reboot or a shutdown canceled outside Focus.
                    if remaining > 0:
                        self.deadline = deadline
                        self._monotonic_deadline = time.monotonic() + remaining
                        self.restored = True
                except (ValueError, TypeError, KeyError):
                    self.deadline = None

    def _save_record(self, state=None):
        if self.persist:
            from utils.constants import update_config
            try:
                update_config({'shutdown_record': {'deadline': self.deadline.isoformat()} if self.deadline else None})
            except OSError as exc:
                state = state or ('Windows accepted the shutdown schedule' if self.deadline else 'Windows canceled the shutdown')
                raise OSError(state + ', but Focus could not save its reminder. Check the data folder permissions.') from exc

    def refresh(self):
        """Expire the app's elapsed reminder without changing Windows schedules."""
        if self.deadline is None or self.remaining_seconds > 0:
            return False
        self.deadline = self._monotonic_deadline = None
        self.restored = False
        try:
            self._save_record('The shutdown countdown has elapsed')
        except OSError:
            # A stale reminder on disk must not leave the controls locked.
            import logging
            logging.getLogger(__name__).exception('Could not clear the expired shutdown reminder')
        return True

    @staticmethod
    def _run(arguments):
        if os.name != 'nt':
            raise OSError('Shutdown scheduling is only supported on Windows.')
        executable = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'shutdown.exe')
        result = subprocess.run([executable, *arguments], capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if result.returncode:
            messages = {
                5: 'Windows denied permission to change the shutdown schedule.',
                1116: 'No shutdown is currently scheduled.',
                1190: 'A shutdown is already scheduled. Cancel it before setting a new time.',
                1314: 'Your Windows account does not have permission to shut down this PC.',
            }
            error = OSError(messages.get(result.returncode,
                            f'Windows could not change the shutdown schedule (error {result.returncode}).'))
            error.winerror = result.returncode
            raise error


    def schedule(self, seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= self.MAX_SECONDS:
            raise ValueError('Enter a valid shutdown delay.')
        self._run(['/s', '/t', str(seconds)])
        self.deadline = datetime.now() + timedelta(seconds=seconds)
        self._monotonic_deadline = time.monotonic() + seconds
        self.restored = False
        self._save_record()

    def cancel(self):
        try:
            self._run(['/a'])
        except OSError as error:
            if getattr(error, 'winerror', None) != 1116:
                raise
        self.deadline = self._monotonic_deadline = None
        self.restored = False
        self._save_record()

    @property
    def remaining_seconds(self):
        import math
        return max(0, math.ceil(self._monotonic_deadline - time.monotonic())) if self._monotonic_deadline else 0
