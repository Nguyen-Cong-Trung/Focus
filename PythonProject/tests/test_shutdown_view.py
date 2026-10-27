"""Exercise shutdown controls with real Tk widgets and mocked Windows commands."""
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import customtkinter as ctk

from core.shutdown_scheduler import ShutdownScheduler
from core.work import BackgroundWork
from ui.shutdown_view import ShutdownView


class ShutdownViewTests(unittest.TestCase):
    def setUp(self):
        self.root = ctk.CTk()
        self.root.withdraw()
        self.root._restoring = False
        self.root._closing = False
        self.work = BackgroundWork()
        self.root.run_background = self.work.submit
        self.scheduler = ShutdownScheduler(persist=False)
        self.command = patch.object(self.scheduler, '_run')
        self.run = self.command.start()
        self.message = patch('ui.shutdown_view.CTkMessagebox')
        self.messagebox = self.message.start()
        self.view = ShutdownView(self.root, self.scheduler)
        self.root.update_idletasks()

    def tearDown(self):
        self.work.close()
        self.view.destroy()
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.root.destroy()
        self.message.stop()
        self.command.stop()

    def settle(self):
        deadline = time.monotonic() + 3
        while self.view._busy and time.monotonic() < deadline:
            self.work.drain()
            self.root.update()
            time.sleep(.005)
        self.assertFalse(self.view._busy, 'Shutdown background work did not finish')

    def assert_editable(self):
        self.assertEqual(self.view.schedule_button.cget('state'), 'normal')
        for entry in self.view.entries:
            self.assertEqual(entry.cget('state'), 'normal')

    def test_confirmed_button_dispatches_selected_duration_and_locks_controls(self):
        self.view.hours.set('0')
        self.view.minutes.set('45')
        self.messagebox.return_value.get.return_value = 'Schedule shutdown'

        self.view.schedule_button.invoke()
        self.settle()

        self.run.assert_called_once_with(['/s', '/t', '2700'])
        self.assertIsNotNone(self.scheduler.deadline)
        self.assertEqual(self.view.schedule_button.cget('state'), 'disabled')
        for entry in self.view.entries:
            self.assertEqual(entry.cget('state'), 'disabled')

    def test_dismissing_confirmation_never_runs_a_windows_command(self):
        for response in ('Go back', None):
            with self.subTest(response=response):
                self.messagebox.return_value.get.return_value = response
                self.view.schedule_button.invoke()
                self.run.assert_not_called()
                self.assertIsNone(self.scheduler.deadline)
                self.assert_editable()

    def test_cancel_clears_schedule_and_reenables_controls(self):
        self.scheduler.schedule(3600)
        self.view._render()
        self.run.reset_mock()

        self.view._cancel()
        self.settle()

        self.run.assert_called_once_with(['/a'])
        self.assertIsNone(self.scheduler.deadline)
        self.assert_editable()
        self.view._preset(90)
        self.assertEqual(self.view.countdown.cget('text'), '01:30:00')

    def test_live_expiry_unlocks_controls_and_presets_without_windows_command(self):
        self.scheduler.schedule(60)
        self.view._render()
        self.run.reset_mock()
        self.scheduler.deadline = datetime.now() - timedelta(seconds=1)
        self.scheduler._monotonic_deadline = time.monotonic() - 1

        self.view._render()

        self.run.assert_not_called()
        self.assertIsNone(self.scheduler.deadline)
        self.assert_editable()
        self.view._preset(30)
        self.assertEqual(self.view.hours.get(), '0')
        self.assertEqual(self.view.minutes.get(), '30')
        self.assertEqual(self.view.countdown.cget('text'), '00:30:00')

    def test_windows_failure_shows_error_and_keeps_schedule_controls_available(self):
        self.run.side_effect = OSError('Windows denied permission')
        self.messagebox.return_value.get.return_value = 'Schedule shutdown'

        with self.assertLogs('core.work', level='ERROR'):
            self.view.schedule_button.invoke()
            self.settle()

        self.assertIsNone(self.scheduler.deadline)
        self.assert_editable()
        self.assertEqual(self.messagebox.call_args.kwargs['message'],
                         'Windows denied permission')

    def test_dispatch_exception_releases_busy_state_without_running_shutdown(self):
        self.root.run_background = Mock(side_effect=RuntimeError('Worker unavailable'))

        self.view._execute(lambda: self.scheduler.schedule(60))

        self.assertFalse(self.view._busy)
        self.assert_editable()
        self.run.assert_not_called()
        self.assertIn('Worker unavailable', self.messagebox.call_args.kwargs['message'])

    def test_rejected_dispatch_releases_busy_state_without_running_shutdown(self):
        self.root.run_background = Mock(return_value=None)

        self.view._execute(lambda: self.scheduler.schedule(60))

        self.assertFalse(self.view._busy)
        self.assert_editable()
        self.run.assert_not_called()
        self.messagebox.assert_called_once()
        self.assertTrue(self.messagebox.call_args.kwargs['message'])


if __name__ == '__main__':
    unittest.main()
