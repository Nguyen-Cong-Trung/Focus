import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.instance import SingleInstance
from core.work import BackgroundWork
from utils.constants import TimerState


class RuntimeLifecycleTests(unittest.TestCase):
    def test_windowed_startup_libraries_always_have_writable_standard_streams(self):
        import sys
        from utils.windowed_io import ensure_standard_streams
        with patch.object(sys, 'stdout', None), patch.object(sys, 'stderr', None):
            ensure_standard_streams()
            stdout, stderr = sys.stdout, sys.stderr
            try:
                stdout.write('startup warning')
                stderr.write('font fallback warning')
            finally:
                stdout.close()
                stderr.close()

    def test_cleanup_failure_cannot_skip_other_resources(self):
        from ui.app import DeepFocusApp
        app = SimpleNamespace(sound_engine=Mock(), work=Mock(), blocking=Mock(), hotkeys=Mock(), tray=Mock())
        app.sound_engine.close.side_effect = RuntimeError('audio driver failure')
        app.work.close.side_effect = RuntimeError('worker failure')
        with self.assertLogs('ui.app', level='ERROR'):
            DeepFocusApp.shutdown_resources(app)
        app.blocking.close.assert_called_once()
        app.hotkeys.disable.assert_called_once()
        app.tray.stop.assert_called_once()

    def test_failed_timer_display_does_not_skip_unblocking(self):
        from ui.app import DeepFocusApp
        app = SimpleNamespace(_previous_state=TimerState.FOCUSING, header_status=Mock(),
            _original_on_state_change=Mock(), _on_focus_end=Mock())
        app.header_status.configure.side_effect = RuntimeError('display failure')
        with self.assertLogs('ui.app', level='ERROR'):
            DeepFocusApp._wrapped_on_state_change(app, TimerState.IDLE)
        app._on_focus_end.assert_called_once()

    def test_one_failed_completion_does_not_drop_following_completions(self):
        report = Mock()
        work = BackgroundWork(report=report)
        self.addCleanup(work.close)
        observed = []
        def broken():
            raise RuntimeError('render failed')
        work.events.put(broken)
        work.events.put(lambda: observed.append('next result'))
        with self.assertLogs('core.work', level='ERROR'):
            work.drain()
        self.assertEqual(observed, ['next result'])
        report.assert_called_once()

    def test_closed_workers_reject_submissions_and_drop_stale_ui_completions(self):
        work = BackgroundWork()
        success = Mock()
        work.submit(lambda: 42, success).result(2)
        work.close()
        work.drain()
        success.assert_not_called()
        self.assertIsNone(work.submit(lambda: 43))

    @unittest.skipUnless(os.name == 'nt', 'Windows named objects')
    def test_duplicate_instance_activates_first_and_releases_on_exit(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
            first = SingleInstance(folder)
            second = SingleInstance(folder)
            try:
                self.assertTrue(first.is_primary)
                self.assertFalse(second.is_primary)
                self.assertTrue(second.activate())
                self.assertTrue(first.consume_activation())
                self.assertFalse(first.consume_activation())
            finally:
                second.close()
                first.close()
            reopened = SingleInstance(folder)
            try:
                self.assertTrue(reopened.is_primary)
            finally:
                reopened.close()

    def test_duplicate_entry_point_does_not_construct_another_app(self):
        import main
        guard = Mock(is_primary=False)
        with patch('core.instance.SingleInstance', return_value=guard), patch('ui.app.DeepFocusApp') as constructor:
            main.main()
        constructor.assert_not_called()
        guard.activate.assert_called_once()
        guard.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
