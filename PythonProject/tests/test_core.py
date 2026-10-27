import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from core.timer_engine import TimerEngine
from core.shutdown_scheduler import ShutdownScheduler
from core.app_blocker import AppBlocker
from utils.constants import TimerState


class TimerTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch('core.timer_engine.time.monotonic', return_value=100)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.db = Mock()
        self.timer = TimerEngine(self.db)
        self.timer.update_durations(1, 1, 2, 2)

    def test_completed_focus_enters_short_break_once(self):
        self.timer.start_focus()
        self.now.return_value = 160
        self.timer.tick()
        self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.SHORT_BREAK)
        self.assertEqual(self.timer.session_count, 1)
        self.db.save_session.assert_called_once()
        self.assertTrue(self.db.save_session.call_args.args[0].completed)

    def test_pause_preserves_remaining_time(self):
        self.timer.start_focus()
        self.now.return_value = 110.5
        self.timer.pause()
        self.now.return_value = 999
        self.timer.tick()
        self.assertEqual(self.timer.remaining_seconds, 50)
        self.timer.resume()
        self.now.return_value = 1000
        self.timer.tick()
        self.assertEqual(self.timer.remaining_seconds, 49)

    def test_skip_paused_focus_does_not_count_as_completed(self):
        self.timer.start_focus()
        self.timer.pause()
        self.timer.skip()
        self.assertEqual(self.timer.state, TimerState.SHORT_BREAK)
        self.assertEqual(self.timer.session_count, 0)
        self.assertFalse(self.db.save_session.call_args.args[0].completed)

    def test_stop_paused_focus_records_incomplete_session(self):
        self.timer.start_focus()
        self.timer.pause()
        self.timer.stop()
        self.timer.stop()
        self.db.save_session.assert_called_once()
        self.assertEqual(self.timer.state, TimerState.IDLE)

    def test_long_break_after_two_completed_sessions(self):
        self.timer.start_focus()
        self.now.return_value = 160
        self.timer.tick()
        self.timer.skip()
        self.timer.start_focus()
        self.now.return_value = 220
        self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.LONG_BREAK)
        self.assertEqual(self.timer.remaining_seconds, 120)

    def test_stop_restart_cannot_leave_an_old_timer(self):
        self.timer.start_focus()
        self.timer.stop()
        self.timer.start_focus()
        self.now.return_value = 101
        self.timer.tick()
        self.assertEqual(self.timer.remaining_seconds, 59)
        self.assertEqual(self.timer.session_count, 0)

    def test_auto_flow_stops_at_goal(self):
        self.timer.update_durations(1, 1, 1, 2, True, 1)
        self.timer.start_focus()
        self.now.return_value = 160
        self.timer.tick()
        self.now.return_value = 220
        self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.IDLE)

    def test_auto_flow_starts_next_focus(self):
        self.timer.update_durations(1, 1, 1, 2, True, 2)
        self.timer.start_focus()
        self.now.return_value = 160
        self.timer.tick()
        self.now.return_value = 220
        self.timer.tick()
        self.assertEqual(self.timer.state, TimerState.FOCUSING)

    def test_invalid_durations_and_mode_change_while_running(self):
        for values in [(0, 1, 1, 1), (1, 1, 1, 0), (-1, 1, 1, 1)]:
            with self.assertRaises(ValueError):
                self.timer.update_durations(*values)
        self.timer.start_focus()
        with self.assertRaises(ValueError):
            self.timer.update_durations(2, 2, 2)


class ShutdownTests(unittest.TestCase):
    def test_expired_reminder_does_not_restore_an_active_schedule(self):
        with patch('utils.constants.load_config', return_value={
            'shutdown_record': {'deadline': '2000-01-01T00:00:00'}
        }), patch('utils.constants.update_config') as save, \
                patch.object(ShutdownScheduler, '_run') as command:
            scheduler = ShutdownScheduler(persist=True)
        self.assertIsNone(scheduler.deadline)
        self.assertIsNone(scheduler._monotonic_deadline)
        self.assertFalse(scheduler.restored)
        self.assertEqual(scheduler.remaining_seconds, 0)
        self.assertFalse(scheduler.refresh())
        command.assert_not_called()
        save.assert_not_called()

    def test_live_elapsed_reminder_unlocks_and_clears_persisted_record(self):
        with patch('utils.constants.load_config', return_value={}), \
                patch('utils.constants.update_config') as save, \
                patch('core.shutdown_scheduler.time.monotonic', return_value=100) as clock, \
                patch.object(ShutdownScheduler, '_run') as command:
            scheduler = ShutdownScheduler(persist=True)
            scheduler.schedule(60)
            command.assert_called_once_with(['/s', '/t', '60'])
            command.reset_mock()
            save.reset_mock()
            clock.return_value = 160

            self.assertTrue(scheduler.refresh())
            self.assertIsNone(scheduler.deadline)
            self.assertIsNone(scheduler._monotonic_deadline)
            self.assertFalse(scheduler.restored)
            self.assertEqual(scheduler.remaining_seconds, 0)
            save.assert_called_once_with({'shutdown_record': None})
            self.assertFalse(scheduler.refresh())
            save.assert_called_once()
            command.assert_not_called()

    def test_restored_future_reminder_expires_without_an_os_command(self):
        now = datetime(2026, 10, 28, 12, 0, 0)
        record = {'shutdown_record': {'deadline': (now + timedelta(seconds=60)).isoformat()}}
        with patch('utils.constants.load_config', return_value=record), \
                patch('utils.constants.update_config') as save, \
                patch('core.shutdown_scheduler.datetime') as wall_clock, \
                patch('core.shutdown_scheduler.time.monotonic', return_value=100) as clock, \
                patch.object(ShutdownScheduler, '_run') as command:
            wall_clock.now.return_value = now
            wall_clock.fromisoformat.side_effect = datetime.fromisoformat
            scheduler = ShutdownScheduler(persist=True)
            self.assertTrue(scheduler.restored)
            self.assertEqual(scheduler.remaining_seconds, 60)
            clock.return_value = 161

            self.assertTrue(scheduler.refresh())
            self.assertIsNone(scheduler.deadline)
            self.assertIsNone(scheduler._monotonic_deadline)
            self.assertFalse(scheduler.restored)
            save.assert_called_once_with({'shutdown_record': None})
            command.assert_not_called()

    def test_refresh_keeps_a_nonexpired_schedule_and_does_not_save(self):
        with patch('core.shutdown_scheduler.time.monotonic', return_value=100) as clock, \
                patch.object(self.scheduler, '_save_record') as save:
            self.scheduler.schedule(60)
            deadline = self.scheduler.deadline
            monotonic_deadline = self.scheduler._monotonic_deadline
            self.run.reset_mock()
            save.reset_mock()
            clock.return_value = 159

            self.assertFalse(self.scheduler.refresh())
            self.assertEqual(self.scheduler.deadline, deadline)
            self.assertEqual(self.scheduler._monotonic_deadline, monotonic_deadline)
            self.assertEqual(self.scheduler.remaining_seconds, 1)
            save.assert_not_called()
            self.run.assert_not_called()

    def setUp(self):
        self.scheduler = ShutdownScheduler()
        self.command = patch.object(self.scheduler, '_run')
        self.run = self.command.start()
        self.addCleanup(self.command.stop)

    def test_schedule_and_cancel(self):
        self.scheduler.schedule(3600)
        self.run.assert_called_once_with(['/s', '/t', '3600'])
        self.assertAlmostEqual(self.scheduler.remaining_seconds, 3600, delta=1)
        self.scheduler.cancel()
        self.run.assert_called_with(['/a'])
        self.assertIsNone(self.scheduler.deadline)

    def test_invalid_input_never_runs_a_command(self):
        for seconds in [0, -1, True, '3600', 2.5, 315360001]:
            with self.assertRaises(ValueError):
                self.scheduler.schedule(seconds)
        self.run.assert_not_called()

    def test_failed_schedule_keeps_existing_state(self):
        self.scheduler.schedule(3600)
        deadline = self.scheduler.deadline
        self.run.side_effect = OSError('Already scheduled')
        with self.assertRaises(OSError):
            self.scheduler.schedule(60)
        self.assertEqual(self.scheduler.deadline, deadline)

    def test_failed_cancel_keeps_countdown(self):
        self.scheduler.schedule(60)
        self.run.side_effect = OSError('Access denied')
        with self.assertRaises(OSError):
            self.scheduler.cancel()
        self.assertIsNotNone(self.scheduler.deadline)

    def test_cancel_already_canceled_windows_schedule_resets_display(self):
        self.scheduler.schedule(60)
        error = OSError('No shutdown is currently scheduled.')
        error.winerror = 1116
        self.run.side_effect = error
        self.scheduler.cancel()
        self.assertIsNone(self.scheduler.deadline)

    @patch('core.shutdown_scheduler.subprocess.run')
    def test_windows_errors_are_presented_in_english(self, run):
        run.return_value.returncode = 1190
        run.return_value.stderr = b'localized Windows error'
        with self.assertRaisesRegex(OSError, 'A shutdown is already scheduled'):
            ShutdownScheduler._run(['/s', '/t', '3600'])

    @patch('core.shutdown_scheduler.subprocess.run')
    def test_command_uses_windows_executable_and_argument_list(self, run):
        run.return_value.returncode = 0
        ShutdownScheduler._run(['/s', '/t', '3600'])
        args, kwargs = run.call_args
        self.assertTrue(args[0][0].lower().endswith('system32\\shutdown.exe'))
        self.assertEqual(args[0][1:], ['/s', '/t', '3600'])
        self.assertNotIn('shell', kwargs)


class BlockerTests(unittest.TestCase):
    def test_restart_stops_previous_monitor(self):
        blocker = AppBlocker()
        with patch.object(blocker, 'stop_monitoring') as stop, patch('core.app_blocker.threading.Thread'):
            blocker.start_monitoring(['Example.exe'])
            stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
