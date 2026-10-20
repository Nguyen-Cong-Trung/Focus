"""Timer progression survives failed observers without duplicate history."""
import unittest
from unittest.mock import Mock, patch

from core.timer_engine import TimerEngine
from utils.constants import TimerState


class TimerLifecycleTests(unittest.TestCase):
    def setUp(self):
        clock = patch('core.timer_engine.time.monotonic', return_value=100)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.db = Mock()
        self.timer = TimerEngine(self.db)
        self.timer.update_durations(1, 1, 2, sessions=2)

    def failing_callback(self):
        return Mock(side_effect=RuntimeError('Refresh failed'))

    def test_failed_completion_refresh_does_not_repeat_history(self):
        self.timer.start_focus()
        self.timer.on_session_complete = self.failing_callback()
        self.clock.return_value = 160
        with self.assertLogs('core.timer_engine', level='ERROR'):
            self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.SHORT_BREAK)
        self.assertEqual(self.timer.remaining_seconds, 60)
        self.clock.return_value = 161
        self.timer.tick()
        self.assertEqual(self.db.save_session.call_count, 1)
        self.assertEqual(self.timer.session_count, 1)
        self.assertTrue(self.db.save_session.call_args.args[0].completed)
        self.timer.on_session_complete.assert_called_once()

    def test_failed_tick_observer_cannot_prevent_focus_expiry(self):
        self.timer.start_focus()
        self.timer.on_tick = self.failing_callback()
        self.clock.return_value = 160
        with self.assertLogs('core.timer_engine', level='ERROR'):
            self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.SHORT_BREAK)
        self.db.save_session.assert_called_once()

    def test_failed_state_observer_cannot_prevent_timer_start_or_stop(self):
        self.timer.on_state_change = self.failing_callback()
        ticks = Mock()
        self.timer.on_tick = ticks
        with self.assertLogs('core.timer_engine', level='ERROR'):
            self.timer.start_focus()
        ticks.assert_called_once_with(60)
        self.clock.return_value = 110
        with self.assertLogs('core.timer_engine', level='ERROR'):
            self.timer.stop()
        self.assertEqual(self.timer.state, TimerState.IDLE)
        self.assertIsNone(self.timer._deadline)
        self.assertEqual(self.timer.remaining_seconds, 0)
        self.assertEqual(ticks.call_args.args, (0,))
        self.assertEqual(self.db.save_session.call_args.args[0].elapsed_seconds, 10)

    def test_failed_break_end_callback_preserves_manual_idle(self):
        self.timer.start_break('short_break')
        self.timer.on_break_end = self.failing_callback()
        self.clock.return_value = 160
        with self.assertLogs('core.timer_engine', level='ERROR'):
            self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.IDLE)
        self.timer.tick()
        self.timer.on_break_end.assert_called_once()
        self.db.save_session.assert_not_called()

    def test_failed_break_end_callback_preserves_auto_flow(self):
        self.timer.auto_flow = True
        self.timer.start_break('short_break')
        self.timer.on_break_end = self.failing_callback()
        self.clock.return_value = 160
        with self.assertLogs('core.timer_engine', level='ERROR'):
            self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.FOCUSING)
        self.assertEqual(self.timer.remaining_seconds, 60)
        self.db.save_session.assert_not_called()

    def test_failed_completion_observer_still_selects_long_break(self):
        self.timer.session_count = 1
        self.timer.start_focus()
        self.timer.on_session_complete = self.failing_callback()
        self.clock.return_value = 160
        with self.assertLogs('core.timer_engine', level='ERROR'):
            self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.LONG_BREAK)
        self.assertEqual(self.timer.remaining_seconds, 120)
        self.assertEqual(self.timer.session_count, 2)

    def test_history_failure_on_stop_releases_focus_and_reports_error(self):
        self.timer.start_focus()
        self.db.save_session.side_effect = OSError('Disk full')
        states = Mock()
        self.timer.on_state_change = states
        with self.assertRaisesRegex(OSError, 'Disk full'):
            self.timer.stop()
        self.assertEqual(self.timer.state, TimerState.IDLE)
        self.assertIsNone(self.timer._deadline)
        states.assert_called_once_with(TimerState.IDLE)
        self.timer.stop()
        self.db.save_session.assert_called_once()

    def test_history_failure_on_paused_stop_still_releases_focus(self):
        self.timer.start_focus()
        self.timer.pause()
        self.db.save_session.side_effect = OSError('Disk full')
        with self.assertRaisesRegex(OSError, 'Disk full'):
            self.timer.stop()
        self.assertEqual(self.timer.state, TimerState.IDLE)
        self.assertEqual(self.timer.remaining_seconds, 0)

    def test_history_failure_on_skip_still_starts_short_break(self):
        self.timer.start_focus()
        self.db.save_session.side_effect = OSError('Disk full')
        states = Mock()
        self.timer.on_state_change = states
        with self.assertRaisesRegex(OSError, 'Disk full'):
            self.timer.skip()
        self.assertEqual(self.timer.state, TimerState.SHORT_BREAK)
        self.assertEqual(self.timer.remaining_seconds, 60)
        self.assertEqual(self.timer.session_count, 0)
        states.assert_called_once_with(TimerState.SHORT_BREAK)
        self.timer.tick()
        self.db.save_session.assert_called_once()

    def test_history_failure_on_expiry_does_not_retry_or_lock_focus(self):
        self.timer.start_focus()
        self.db.save_session.side_effect = OSError('Disk full')
        completed = Mock()
        states = Mock()
        self.timer.on_session_complete = completed
        self.timer.on_state_change = states
        self.clock.return_value = 160
        with self.assertRaisesRegex(OSError, 'Disk full'):
            self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.SHORT_BREAK)
        self.assertEqual(self.timer.session_count, 1)
        states.assert_called_once_with(TimerState.SHORT_BREAK)
        completed.assert_not_called()
        self.clock.return_value = 161
        self.timer.tick()
        self.db.save_session.assert_called_once()

    def test_history_failure_on_expiry_preserves_long_break_cadence(self):
        self.timer.session_count = 1
        self.timer.start_focus()
        self.db.save_session.side_effect = OSError('Disk full')
        self.clock.return_value = 160
        with self.assertRaisesRegex(OSError, 'Disk full'):
            self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.LONG_BREAK)
        self.assertEqual(self.timer.session_count, 2)


if __name__ == '__main__':
    unittest.main()
