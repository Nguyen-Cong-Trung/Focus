"""Regressions observed or exposed while using the actual app with Computer Use."""
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
import numpy as np
from core.sound_engine import SoundEngine
from data.models import DailyStats


class WhitelistSettingsTests(unittest.TestCase):
    def test_focus_uses_latest_settings_instead_of_startup_snapshot(self):
        from ui.app import DeepFocusApp
        from data.models import FocusMode
        blocker = Mock()
        blocker.get_enabled_sites.return_value = []
        blocker.get_enabled_apps.return_value = []
        app = SimpleNamespace(
            views={'blocker': blocker}, blocking=Mock(),
            active_mode=lambda: FocusMode(name='Whitelist', whitelist_mode=True),
            is_focus_phase=lambda: True, report_error=Mock())
        with patch('ui.app.load_config', return_value={
                'hardcore_sites': ['latest.example'], 'hardcore_apps': ['Latest.exe']}):
            DeepFocusApp.apply_blocking(app)
        app.blocking.apply.assert_called_once_with(True, ['latest.example'], ['Latest.exe'])



class ShortSessionStatsTests(unittest.TestCase):
    def test_one_minute_session_is_not_rounded_to_no_activity(self):
        stats = DailyStats(total_focus_minutes=1, completed_sessions=1)
        self.assertGreater(stats.focus_hours, 0)
        self.assertAlmostEqual(stats.focus_hours * 60, 1)


class SoundFailureTests(unittest.TestCase):
    def setUp(self):
        self.engine = SoundEngine()
        self.buffer_patch = patch.object(self.engine, '_get_or_create_buffer', return_value=np.ones(16, dtype=np.float32))
        self.buffer = self.buffer_patch.start()
        self.addCleanup(self.buffer_patch.stop)

    @patch('core.sound_engine.sd.OutputStream')
    def test_failed_device_start_can_be_retried_without_ghost_playback(self, output):
        output.return_value.start.side_effect = RuntimeError('Device unavailable')
        with self.assertRaises(RuntimeError):
            self.engine.play('rain', 0.1)
        self.assertFalse(self.engine.is_playing('rain'))
        self.assertEqual(self.engine.get_playing_sounds(), [])
        output.return_value.close.assert_called_once()
        output.return_value.start.side_effect = None
        self.engine.play('rain', 0.1)
        self.assertTrue(self.engine.is_playing('rain'))
        self.engine.stop('rain')
        self.assertFalse(self.engine.is_playing('rain'))

    @patch('core.sound_engine.SOUNDDEVICE_AVAILABLE', False)
    def test_missing_audio_backend_is_reported_instead_of_fake_success(self):
        with self.assertRaisesRegex(RuntimeError, 'Audio playback is not available'):
            self.engine.play('rain')
        self.assertEqual(self.engine.get_playing_sounds(), [])

    @patch('core.sound_engine.sd.OutputStream')
    def test_empty_audio_does_not_start_an_infinite_callback(self, output):
        self.buffer.return_value = np.array([], dtype=np.float32)
        with self.assertRaisesRegex(ValueError, 'empty'):
            self.engine.play('custom_empty')
        output.assert_not_called()


if __name__ == '__main__':
    unittest.main()
