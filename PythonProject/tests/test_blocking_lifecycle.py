"""Deterministic blocker lifecycle regressions without any real OS changes."""
import threading
import unittest
from unittest.mock import Mock

from core.blocking import BlockingCoordinator


class BlockingLifecycleTests(unittest.TestCase):
    def make_controller(self):
        sites, apps = Mock(), Mock()
        sites.block.return_value = sites.unblock.return_value = True
        controller = BlockingCoordinator(sites, apps)
        self.addCleanup(controller.close)
        return controller, sites, apps

    def test_stop_after_inflight_enable_clears_hosts_despite_cached_off(self):
        controller, sites, apps = self.make_controller()
        controller.apply(False).result(2)
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        blocked = {'value': False}

        def block(_):
            entered.set()
            if not release.wait(2):
                raise TimeoutError('Test did not release the site blocker')
            blocked['value'] = True
            return True

        def unblock():
            blocked['value'] = False
            return True

        sites.block.side_effect = block
        sites.unblock.side_effect = unblock
        pending = controller.apply(True, ['example.com'], ['Game.exe'])
        self.assertTrue(entered.wait(2))
        stopped = controller.apply(False)
        release.set()
        pending.result(2)
        stopped.result(2)
        self.assertFalse(blocked['value'])
        self.assertEqual(controller.applied, (False, (), ()))
        self.assertEqual(controller.status, 'Off')
        apps.start_monitoring.assert_not_called()

    def test_close_after_inflight_enable_releases_hosts(self):
        controller, sites, _ = self.make_controller()
        controller.apply(False).result(2)
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        sites.block.side_effect = lambda _: entered.set() or release.wait(2)
        pending = controller.apply(True, ['example.com'])
        self.assertTrue(entered.wait(2))
        # close queues its stop before waiting for the in-flight OS call.
        stop_queued = threading.Event()
        submit = controller.pool.submit

        def queue_stop(*args, **kwargs):
            future = submit(*args, **kwargs)
            stop_queued.set()
            return future

        controller.pool.submit = queue_stop
        closing = threading.Thread(target=controller.close)
        closing.start()
        self.assertTrue(stop_queued.wait(2))
        release.set()
        pending.result(2)
        closing.join(2)
        self.assertFalse(closing.is_alive())
        self.assertEqual(sites.unblock.call_count, 2)
        self.assertEqual(controller.status, 'Off')

    def test_failed_site_start_is_retried_for_identical_request(self):
        controller, sites, _ = self.make_controller()
        sites.block.side_effect = [False, True]
        controller.apply(True, ['example.com']).result(2)
        self.assertEqual(controller.status, 'Partial')
        self.assertIsNone(controller.applied)
        controller.apply(True, ['example.com']).result(2)
        self.assertEqual(sites.block.call_count, 2)
        self.assertEqual(controller.status, 'On')

    def test_failed_unblock_is_retried_for_identical_stop(self):
        controller, sites, _ = self.make_controller()
        sites.unblock.side_effect = [False, True]
        controller.apply(False).result(2)
        self.assertEqual(controller.status, 'Partial')
        self.assertIsNone(controller.applied)
        controller.apply(False).result(2)
        self.assertEqual(sites.unblock.call_count, 2)
        self.assertEqual(controller.status, 'Off')

    def test_failed_app_start_is_retried_for_identical_request(self):
        controller, _, apps = self.make_controller()
        apps.start_monitoring.side_effect = [OSError('Monitor failed'), None]
        with self.assertLogs('core.blocking', level='ERROR'):
            controller.apply(True, apps=['Game.exe']).result(2)
        self.assertIsNone(controller.applied)
        controller.apply(True, apps=['Game.exe']).result(2)
        self.assertEqual(apps.start_monitoring.call_count, 2)
        self.assertEqual(controller.status, 'On')

    def test_apply_submits_under_lock_before_close_can_shutdown_executor(self):
        controller, _, _ = self.make_controller()
        submit = controller.pool.submit
        submitted_with_lock = []

        def submit_checked(*args, **kwargs):
            submitted_with_lock.append(controller.lock.locked())
            return submit(*args, **kwargs)

        controller.pool.submit = submit_checked
        controller.apply(True, ['example.com']).result(2)
        controller.close()
        self.assertEqual(submitted_with_lock, [True, True])

    def test_concurrent_enable_cannot_supersede_final_close_request(self):
        controller, sites, apps = self.make_controller()
        controller.apply(True, ['example.com'], ['Game.exe']).result(2)
        submit = controller.pool.submit
        final_queued, contender_started = threading.Event(), threading.Event()
        submitted_after_closed = []
        attempts, errors = [], []

        def submit_final(*args, **kwargs):
            submitted_after_closed.append(controller.closed)
            future = submit(*args, **kwargs)
            final_queued.set()
            if not contender_started.wait(2):
                raise TimeoutError('Concurrent request did not start')
            return future

        def enable():
            try:
                if not final_queued.wait(2):
                    raise TimeoutError('Final unblock was not queued')
                contender_started.set()
                attempts.append(controller.apply(True, ['late.example'], ['Late.exe']))
            except Exception as exc:
                errors.append(exc)

        controller.pool.submit = submit_final
        contender = threading.Thread(target=enable)
        contender.start()
        controller.close()
        contender.join(2)
        self.assertFalse(contender.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(attempts, [None])
        self.assertEqual(submitted_after_closed, [True])
        self.assertEqual(controller.status, 'Off')
        self.assertEqual(controller.applied, (False, (), ()))
        sites.block.assert_called_once_with(['example.com'])
        apps.start_monitoring.assert_called_once_with(['Game.exe'], interval=5)

    def test_close_is_idempotent_and_late_apply_is_ignored(self):
        controller, sites, apps = self.make_controller()
        controller.close()
        controller.close()
        self.assertIsNone(controller.apply(True, ['example.com'], ['Game.exe']))
        sites.unblock.assert_called_once()
        sites.block.assert_not_called()
        apps.start_monitoring.assert_not_called()


if __name__ == '__main__':
    unittest.main()
