"""Deterministic audio close/cancel regressions, using no output device."""
import threading
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace, MethodType

import numpy as np

from core.sound_engine import SoundEngine
from core.work import BackgroundWork


class AudioLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = SoundEngine()
        self.output = patch('core.sound_engine.sd.OutputStream').start()
        self.addCleanup(patch.stopall)
        self.output.return_value.active = True
        self.buffer = patch.object(self.engine, '_get_or_create_buffer', return_value=np.ones(32, dtype=np.float32)).start()
        self.addCleanup(self.engine.close)

    def test_cancelled_queued_play_never_starts_a_stream(self):
        token = self.engine.generation
        self.engine.stop_all()
        self.assertFalse(self.engine.play('rain', generation=token))
        self.output.assert_not_called()
        self.assertTrue(self.engine.play('rain', generation=self.engine.generation))

    def test_close_window_cancels_inflight_preparation_without_waiting(self):
        from ui.app import DeepFocusApp
        started, release = threading.Event(), threading.Event()
        def prepare(*args):
            started.set()
            if not release.wait(3):
                raise TimeoutError('fixture not released')
            return np.ones(32, dtype=np.float32)
        self.buffer.side_effect = prepare
        work = BackgroundWork()
        self.addCleanup(work.close)
        app = SimpleNamespace(_closing=False, _restoring=False, _audio_generation=0,
            _auto_sound_owned=None, sound_engine=self.engine, work=work,
            views={'sound': SimpleNamespace(refresh_playback=Mock())},
            config={'close_to_tray': True}, tray=SimpleNamespace(available=True),
            testing=False, withdraw=Mock(), _quit=Mock())
        app.run_background = lambda f, success=None, lane='system': work.submit(f, success, lane=lane)
        app.stop_all_sounds = MethodType(DeepFocusApp.stop_all_sounds, app)
        token = self.engine.generation
        future = work.submit(lambda: self.engine.play('rain', generation=token), lane='audio')
        self.assertTrue(started.wait(2))
        try:
            DeepFocusApp._on_close(app)
            app.withdraw.assert_called_once()
            app._quit.assert_not_called()
        finally:
            release.set()
        self.assertFalse(future.result(3))
        work.submit(lambda: None, lane='audio').result(3)
        self.output.assert_not_called()
        self.assertEqual(self.engine.get_playing_sounds(), [])

    def test_global_stop_silences_callback_before_worker_closes_stream(self):
        self.engine.play('rain')
        callback = self.output.call_args.kwargs['callback']
        data = np.empty((1024, 2), dtype=np.float32)
        callback(data, len(data), None, None)
        self.assertTrue(np.any(data))
        self.engine.request_stop_all()
        callback(data, len(data), None, None)
        self.assertFalse(np.any(data))

    def test_terminal_close_forbids_play_but_restore_cleanup_is_reusable(self):
        token = self.engine.generation
        self.engine.cleanup()
        self.assertFalse(self.engine.play('rain', generation=token))
        self.assertTrue(self.engine.play('rain'))
        self.engine.close()
        self.output.reset_mock()
        self.assertFalse(self.engine.play('rain'))
        self.output.assert_not_called()
        self.assertEqual(self.engine.get_playing_sounds(), [])

    def test_device_stopped_stream_does_not_report_playing(self):
        self.engine.play('rain')
        self.output.return_value.active = False
        self.assertFalse(self.engine.is_playing('rain'))
        self.assertEqual(self.engine.get_playing_sounds(), [])
        self.engine.stop('rain')
        self.output.return_value.close.assert_called_once()

    def test_invalidation_during_device_start_closes_the_stale_stream(self):
        self.output.return_value.start.side_effect = self.engine.request_stop_all
        self.assertFalse(self.engine.play('rain'))
        self.output.return_value.abort.assert_called_once()
        self.output.return_value.close.assert_called_once()
        self.assertEqual(self.engine.get_playing_sounds(), [])

    def test_failed_stream_close_cannot_restart_old_callback_on_new_volume(self):
        first, second = Mock(active=True), Mock(active=True)
        self.output.side_effect = [first, second]
        self.engine.play('rain')
        old_callback = self.output.call_args.kwargs['callback']
        first.close.side_effect = RuntimeError('driver close failure')
        with self.assertLogs('core.sound_engine', level='ERROR'):
            self.engine.stop('rain')
        self.engine.play('rain')
        data = np.ones((1024, 2), dtype=np.float32)
        old_callback(data, len(data), None, None)
        self.assertFalse(np.any(data))

    def test_late_auto_sound_completion_cannot_stop_new_manual_playback(self):
        from ui.app import DeepFocusApp
        from data.models import FocusMode
        first, second = Mock(active=True), Mock(active=True)
        self.output.side_effect = [first, second]
        queued = []
        app = SimpleNamespace(apply_blocking=Mock(), active_mode=lambda: FocusMode(auto_sound='rain'),
            sound_engine=self.engine, _audio_generation=0, _auto_sound_owned=None, report_error=Mock())
        app.run_background = lambda f, success=None, error=None, lane='system': queued.append((f, success))
        DeepFocusApp._on_focus_start(app)
        start, finished = queued.pop(0)
        stream = start()
        self.engine.stop_all()
        app._audio_generation += 1
        self.engine.play('rain')
        finished(stream)
        stop_old, _ = queued.pop(0)
        stop_old()
        self.assertIs(self.engine.playback_handle('rain'), second)
        self.assertTrue(self.engine.is_playing('rain'))
        second.close.assert_not_called()

    def test_hidden_window_cannot_restart_auto_sound_on_next_focus_phase(self):
        from ui.app import DeepFocusApp
        from data.models import FocusMode
        app = SimpleNamespace(apply_blocking=Mock(), active_mode=lambda: FocusMode(auto_sound='rain'),
            sound_engine=self.engine, _audio_generation=0, _audio_suspended=True, run_background=Mock())
        DeepFocusApp._on_focus_start(app)
        app.apply_blocking.assert_called_once()
        app.run_background.assert_not_called()
        self.output.assert_not_called()


if __name__ == '__main__':
    unittest.main()
