"""Timer behavior while foreground apps delay ticks or change wall time."""
from datetime import datetime
import unittest
from unittest.mock import Mock, patch

from core.timer_engine import TimerEngine
from utils.constants import TimerState


class TimerCoexistenceTests(unittest.TestCase):
    def setUp(self):
        clock = patch('core.timer_engine.time.monotonic', return_value=100)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.db = Mock()
        self.timer = TimerEngine(self.db)
        self.timer.update_durations(1, 1, 2, sessions=2)

    def test_delayed_ticks_record_one_completion_and_give_a_full_break(self):
        self.timer.start_focus()
        self.clock.return_value = 600
        self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.SHORT_BREAK)
        self.assertEqual(self.timer.remaining_seconds, 60)
        self.assertEqual(self.timer.session_count, 1)
        self.db.save_session.assert_called_once()
        self.assertEqual(self.db.save_session.call_args.args[0].elapsed_seconds, 60)
        self.timer.tick()
        self.db.save_session.assert_called_once()

    def test_long_other_app_activity_while_paused_is_not_focus_time(self):
        self.timer.start_focus()
        self.clock.return_value = 110.5
        self.timer.pause()
        self.clock.return_value = 9000
        self.timer.tick()
        self.assertEqual(self.timer.remaining_seconds, 50)
        self.timer.resume()
        self.clock.return_value = 9020
        self.timer.stop()
        session = self.db.save_session.call_args.args[0]
        self.assertEqual(session.elapsed_seconds, 30.5)
        self.assertFalse(session.completed)

    def test_midnight_or_wall_clock_adjustment_does_not_expire_timer(self):
        with patch('core.timer_engine.datetime') as wall:
            wall.now.return_value = datetime(2026, 10, 28, 23, 59, 50)
            self.timer.start_focus()
            wall.now.return_value = datetime(2026, 10, 29, 3, 0, 0)
            self.clock.return_value = 110
            self.timer.tick()
            self.assertEqual(self.timer.remaining_seconds, 50)
            self.timer.stop()
        self.assertEqual(self.db.save_session.call_args.args[0].elapsed_seconds, 10)

    def test_repeated_pause_resume_preserves_fractional_deadline(self):
        self.timer.start_focus()
        for _ in range(3):
            self.clock.return_value += .25
            self.timer.pause()
            self.clock.return_value += 100
            self.timer.resume()
        self.assertEqual(self.timer.remaining_seconds, 60)
        self.timer.stop()
        self.db.save_session.assert_called_once()
        self.assertEqual(self.db.save_session.call_args.args[0].elapsed_seconds, .75)
        self.assertEqual(self.timer.state, TimerState.IDLE)


if __name__ == '__main__':
    unittest.main()
