"""One serial owner of OS blocking. Editing a list never activates idle blocking."""
from concurrent.futures import ThreadPoolExecutor
import logging
import threading


class BlockingCoordinator:
    def __init__(self, sites, apps, report=None):
        self.sites, self.apps, self.report = sites, apps, report or (lambda text: None)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='blocker')
        self.generation = 0
        self.lock = threading.Lock()
        self.applied = None
        self.status = "Off"
        self.closed = False

    def apply(self, active, sites=(), apps=()):
        desired = (bool(active), tuple(sites) if active else (), tuple(apps) if active else ())
        with self.lock:
            if self.closed:
                return
            if not active or not apps:
                self.apps.request_stop()
            self.generation += 1
            generation = self.generation
            return self.pool.submit(self._apply, generation, desired)

    def _apply(self, generation, desired):
        with self.lock:
            if generation != self.generation:
                return
            if desired == self.applied:
                return
            # OS calls below can change hosts/monitoring even if a newer request
            # arrives before they finish. The previous snapshot is no longer a
            # safe reason to skip the next request (especially a stop/quit).
            self.applied = None
        active, sites, apps = desired
        self.status = "On" if active and (sites or apps) else "Off"
        try:
            if sites:
                if not self.sites.block(list(sites)):
                    self.status = 'Partial'
                    self.report('Website blocking could not start. Check administrator access.')
            else:
                if not self.sites.unblock():
                    self.status = "Partial"
                    self.report('Websites could not be unblocked. Use administrator access and try again.')
        except Exception:
            logging.getLogger(__name__).exception('Website blocker failed')
            self.status = 'Partial'
            self.report('Website blocking failed. Check the application log.')
        with self.lock:
            if generation != self.generation:
                return
        try:
            if apps:
                self.apps.start_monitoring(list(apps), interval=5)
            else:
                self.apps.stop_monitoring()
        except Exception:
            logging.getLogger(__name__).exception('Application blocker failed')
            self.status = 'Partial'
            self.report('Application blocking failed. Check the application log.')
        with self.lock:
            if generation == self.generation and self.status != "Partial":
                self.applied = desired

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.generation += 1
            self.apps.request_stop()
            # Mark closed and queue the final release atomically: no late
            # enable can supersede it or submit after executor shutdown.
            self.pool.submit(self._apply, self.generation, (False, (), ()))
        self.pool.shutdown(wait=True, cancel_futures=False)
