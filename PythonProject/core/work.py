"""Background work whose UI completions are explicitly drained on the Tk thread."""
from concurrent.futures import ThreadPoolExecutor
import logging
import queue
import threading


class BackgroundWork:
    def __init__(self, report=None):
        self.events = queue.SimpleQueue()
        self.pools = {name:ThreadPoolExecutor(max_workers=1, thread_name_prefix=name) for name in ('audio','system')}
        self.closed = False
        self._lock = threading.Lock()
        self.report = report

    def submit(self, function, success=None, error=None, lane='system'):
        with self._lock:
            if self.closed:
                return
            future = self.pools[lane].submit(function)
        def done(result):
            if self.closed or result.cancelled():
                return
            try:
                value = result.result()
            except Exception as exc:
                logging.getLogger(__name__).exception('Background operation failed')
                if error:
                    self.events.put(lambda exc=exc: error(exc))
            else:
                if success:
                    self.events.put(lambda: success(value))
        future.add_done_callback(done)
        return future

    def drain(self):
        for _ in range(100):
            try:
                callback = self.events.get_nowait()
            except queue.Empty:
                return
            if self.closed:
                continue
            try:
                callback()
            except Exception:
                logging.getLogger(__name__).exception('Background completion callback failed')
                if self.report:
                    try:
                        self.report('An operation finished, but its display could not be updated.')
                    except Exception:
                        # A destroyed notice widget must not block the other
                        # queued completions or escape into the UI clock.
                        logging.getLogger(__name__).exception('Background error display failed')

    def close(self):
        with self._lock:
            self.closed = True
        for pool in self.pools.values():
            pool.shutdown(wait=True, cancel_futures=True)
