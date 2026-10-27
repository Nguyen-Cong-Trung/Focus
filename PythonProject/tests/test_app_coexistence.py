"""App orchestration regressions with no real OS or workspace side effects."""
import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ui.app import DeepFocusApp
from utils.constants import TimerState


class AppCoexistenceTests(unittest.TestCase):
    def test_failed_integration_callback_does_not_starve_timer_or_later_events(self):
        first = Mock(side_effect=OSError('external Windows integration unavailable'))
        later = Mock()
        events = queue.SimpleQueue()
        events.put(first)
        events.put(later)
        app = SimpleNamespace(_destroyed=False, _closing=False, _restoring=False,
            _ui_events=events, work=Mock(), instance_guard=None, _ready_shown=False,
            timer_engine=Mock(), _last_slow_tick=float('inf'), _last_planner_tick=float('inf'),
            report_error=Mock(), after=Mock(return_value='next-clock'))
        app._clock_step = lambda callback: DeepFocusApp._clock_step(app, callback)
        app._poll_window_state = lambda: DeepFocusApp._poll_window_state(app)
        app._poll_clock = lambda: DeepFocusApp._poll_clock(app)
        with self.assertLogs('ui.app', level='ERROR'):
            app._poll_clock()
        later.assert_called_once()
        app.timer_engine.tick.assert_called_once()
        app.work.drain.assert_called_once()
        app.after.assert_called_once()

    def test_failed_native_activation_does_not_stop_the_timer(self):
        app = SimpleNamespace(_destroyed=False, _closing=False, _restoring=False,
            _ui_events=queue.SimpleQueue(), work=Mock(), instance_guard=Mock(),
            _ready_shown=False, timer_engine=Mock(), _last_slow_tick=float('inf'),
            _last_planner_tick=float('inf'), report_error=Mock(), after=Mock())
        app.instance_guard.consume_activation.side_effect = OSError('native handle unavailable')
        app._clock_step = lambda callback: DeepFocusApp._clock_step(app, callback)
        app._poll_window_state = lambda: DeepFocusApp._poll_window_state(app)
        app._poll_clock = lambda: DeepFocusApp._poll_clock(app)
        with self.assertLogs('ui.app', level='ERROR'):
            app._poll_clock()
        app.timer_engine.tick.assert_called_once()
        app.after.assert_called_once()

    def test_primary_instance_is_released_even_when_startup_fails(self):
        import main
        guard = Mock(is_primary=True)
        with patch('core.instance.SingleInstance', return_value=guard) as constructor, \
                patch('main._run_primary', side_effect=OSError('workspace locked')):
            with self.assertRaises(OSError):
                main.main()
        from utils.constants import DB_DIR
        constructor.assert_called_once_with(DB_DIR)
        guard.close.assert_called_once()

    def test_timer_started_while_file_dialog_open_prevents_restore(self):
        engine = SimpleNamespace(state=TimerState.IDLE)
        app = SimpleNamespace(_restoring=False, _closing=False, _data_busy=False,
                              timer_engine=engine, report_error=Mock())
        def choose(**kwargs):
            engine.state = TimerState.FOCUSING
            return 'test-backup.zip'
        with patch('tkinter.filedialog.askopenfilename', side_effect=choose), \
                patch('ui.app.CTkMessagebox') as confirm, patch('ui.app.ctk.CTkToplevel') as progress:
            confirm.return_value.get.return_value = 'Restore workspace'
            DeepFocusApp.workspace_action(app, 'restore')
        progress.assert_not_called()
        app.report_error.assert_called_once()

    def test_rejected_background_submission_releases_data_modal_and_busy_flags(self):
        app = SimpleNamespace(_restoring=False, _closing=False, _data_busy=False,
            timer_engine=SimpleNamespace(state=TimerState.IDLE), db=Mock(),
            run_background=Mock(return_value=None), report_error=Mock())
        with patch('tkinter.filedialog.asksaveasfilename', return_value='test-backup.zip'), \
                patch('ui.app.ctk.CTkToplevel') as progress, patch('ui.app.ctk.CTkLabel'), \
                patch('ui.app.set_window_brand'), patch('core.backup.BackupManager'):
            DeepFocusApp.workspace_action(app, 'backup')
        self.assertFalse(app._data_busy)
        self.assertFalse(app._restoring)
        progress.return_value.destroy.assert_called_once()
        app.report_error.assert_called_once()

    def test_rejected_audio_submission_restores_play_and_volume_controls(self):
        from ui.sound_view import SoundCard
        for failure in (None, RuntimeError('executor already stopped')):
            with self.subTest(failure=failure):
                app = SimpleNamespace(_restoring=False, _closing=False,
                    run_background=Mock(return_value=None), report_error=Mock())
                if failure is not None:
                    app.run_background.side_effect = failure
                engine = Mock(generation=1)
                engine.is_playing.return_value = False
                card = SimpleNamespace(_pending=False, winfo_toplevel=lambda: app,
                    winfo_exists=lambda: True, sound_engine=engine, sound_type='rain',
                    custom_path=None, toggle_btn=Mock(), vol_slider=Mock(), sync_playback=Mock())
                card.vol_slider.get.return_value = 50
                SoundCard._toggle_play(card)
                self.assertFalse(card._pending)
                card.toggle_btn.configure.assert_any_call(state='normal')
                card.vol_slider.configure.assert_any_call(state='normal')
                card.sync_playback.assert_called_once()
                app.report_error.assert_called_once()


if __name__ == '__main__':
    unittest.main()
