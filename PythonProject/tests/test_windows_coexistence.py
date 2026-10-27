"""Safe coexistence coverage: no real hooks, shutdowns, startup edits or tray UI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.hotkeys import HotkeyManager
from core.instance import SingleInstance
from core.shutdown_scheduler import ShutdownScheduler
from core.startup import is_run_on_startup, set_run_on_startup
from core.tray import TrayIcon


class ShortcutCoexistenceTests(unittest.TestCase):
    @patch('core.hotkeys.keyboard.remove_hotkey')
    @patch('core.hotkeys.keyboard.add_hotkey')
    def test_shortcut_does_not_consume_other_apps_keys_and_removes_only_its_handle(self, add, remove):
        own_registration = object()
        add.return_value = own_registration
        manager = HotkeyManager()
        self.assertTrue(manager.enable('ctrl+shift+space'))
        self.assertFalse(add.call_args.kwargs['suppress'])
        # A held shortcut must not repeatedly start/pause the focus session.
        self.assertTrue(add.call_args.kwargs['trigger_on_release'])
        manager.disable()
        remove.assert_called_once_with(own_registration)

    @patch('core.hotkeys.keyboard.remove_hotkey')
    @patch('core.hotkeys.keyboard.add_hotkey', return_value=object())
    def test_enabling_same_shortcut_is_idempotent(self, add, remove):
        manager = HotkeyManager()
        manager.enable('ctrl+shift+space')
        manager.enable('ctrl+shift+space')
        add.assert_called_once()
        remove.assert_not_called()
        manager.disable()

    @patch('core.hotkeys.keyboard.remove_hotkey')
    @patch('core.hotkeys.keyboard.add_hotkey', return_value=object())
    @patch('core.hotkeys.threading.Thread')
    def test_callback_queued_before_disable_cannot_toggle_session_later(self, thread, add, remove):
        manager = HotkeyManager()
        callback = Mock()
        manager.set_callback(callback)
        manager.enable()
        add.call_args.args[1]()
        deferred = thread.call_args.kwargs
        manager.disable()
        deferred['target'](*deferred['args'])
        callback.assert_not_called()

    @patch('core.hotkeys.keyboard.remove_hotkey')
    @patch('core.hotkeys.keyboard.add_hotkey')
    def test_failed_rebind_cannot_leave_old_shortcut_active(self, add, remove):
        add.side_effect = [object(), ValueError('invalid shortcut')]
        manager = HotkeyManager()
        callback = Mock()
        manager.set_callback(callback)
        manager.enable()
        old_hook = add.call_args.args[1]
        with self.assertLogs('core.hotkeys', level='ERROR'):
            self.assertFalse(manager.enable('not-a-real-key'))
        with patch('core.hotkeys.threading.Thread') as thread:
            old_hook()
        thread.assert_not_called()
        self.assertFalse(manager._enabled)
        callback.assert_not_called()

    @patch('core.hotkeys.keyboard.remove_hotkey')
    @patch('core.hotkeys.keyboard.add_hotkey', return_value=object())
    def test_failed_hook_removal_is_retried_without_reactivating_callback(self, add, remove):
        remove.side_effect = [OSError('listener stopping'), None]
        manager = HotkeyManager()
        manager.enable()
        old_hook = add.call_args.args[1]
        with self.assertLogs('core.hotkeys', level='ERROR'):
            manager.disable()
        with patch('core.hotkeys.threading.Thread') as thread:
            old_hook()
        thread.assert_not_called()
        manager.disable()
        self.assertEqual(remove.call_count, 2)
        self.assertEqual(manager._registrations, [])


class StartupRegistryTests(unittest.TestCase):
    @patch('core.startup.winreg.CloseKey')
    @patch('core.startup.winreg.QueryValueEx', side_effect=FileNotFoundError())
    @patch('core.startup.winreg.OpenKey', return_value=object())
    def test_missing_sign_in_value_closes_registry_handle_and_uses_read_access(self, opened, query, close):
        import winreg
        self.assertFalse(is_run_on_startup())
        self.assertEqual(opened.call_args.args[3], winreg.KEY_QUERY_VALUE)
        close.assert_called_once_with(opened.return_value)

    @patch('core.startup.winreg.CloseKey')
    @patch('core.startup.winreg.SetValueEx', side_effect=PermissionError('read-only policy'))
    @patch('core.startup.winreg.CreateKeyEx', return_value=object())
    def test_denied_startup_write_releases_handle(self, opened, write, close):
        import winreg
        with self.assertLogs('core.startup', level='ERROR'):
            self.assertFalse(set_run_on_startup(True))
        self.assertEqual(opened.call_args.args[3], winreg.KEY_SET_VALUE)
        close.assert_called_once_with(opened.return_value)

    @patch('core.startup.winreg.OpenKey', side_effect=FileNotFoundError())
    def test_disabling_startup_without_run_key_is_already_successful(self, opened):
        self.assertTrue(set_run_on_startup(False))

    @patch('core.startup.winreg.CloseKey')
    @patch('core.startup.winreg.SetValueEx')
    @patch('core.startup.winreg.CreateKeyEx', return_value=object())
    def test_frozen_startup_uses_real_executable_not_mutable_argv(self, opened, write, close):
        with patch('core.startup.sys.frozen', True, create=True), \
                patch('core.startup.sys.executable', r'C:\Apps\Focus\Focus.exe'), \
                patch('core.startup.sys.argv', ['another-app.exe']):
            self.assertTrue(set_run_on_startup(True))
        self.assertEqual(write.call_args.args[4], r'"C:\Apps\Focus\Focus.exe"')
        close.assert_called_once()

    @patch('core.startup.winreg.CloseKey')
    @patch('core.startup.winreg.SetValueEx')
    @patch('core.startup.winreg.CreateKeyEx', return_value=object())
    def test_pyw_source_startup_explicitly_uses_windowed_python(self, opened, write, close):
        with patch('core.startup.sys.executable', r'C:\Python\python.exe'), \
                patch('core.startup.sys.argv', [r'C:\Focus\main.pyw']), \
                patch('core.startup.Path.is_file', return_value=True):
            self.assertTrue(set_run_on_startup(True))
        self.assertEqual(write.call_args.args[4], r'"C:\Python\pythonw.exe" "C:\Focus\main.pyw"')


class TrayCoexistenceTests(unittest.TestCase):
    def test_failed_balloon_delivery_marks_tray_unavailable_for_window_recovery(self):
        tray = TrayIcon('unused.ico', Mock())
        tray.available = True
        tray._data = SimpleNamespace(szInfoTitle='', szInfo='', dwInfoFlags=0, uFlags=7)
        tray._shell = Mock()
        tray._shell.Shell_NotifyIconW.return_value = False
        tray._ctypes = Mock()
        self.assertFalse(tray.notify('Timer', 'Session completed'))
        self.assertFalse(tray.available)
        self.assertEqual(tray._data.uFlags, 7)

    def test_tray_notifications_stop_after_shutdown_begins(self):
        tray = TrayIcon('unused.ico', Mock())
        tray.stop()
        tray.available = True  # Simulate a worker completing a delayed icon add.
        tray._shell = Mock()
        self.assertFalse(tray.notify('Timer', 'Must not appear'))
        tray._shell.Shell_NotifyIconW.assert_not_called()

    @patch.dict(os.environ, {'DEEPFOCUS_TESTING': '0'})
    def test_repeated_start_does_not_create_multiple_worker_threads(self):
        class ControlledTray(TrayIcon):
            calls = 0
            def _run(self):
                self.calls += 1
                self.available = True
                self._ready.set()
                self._stopping.wait(2)
                self.available = False
        tray = ControlledTray('unused.ico', Mock())
        try:
            self.assertTrue(tray.start())
            self.assertTrue(tray.start())
            self.assertEqual(tray.calls, 1)
        finally:
            tray.stop()
        self.assertFalse(tray.available)
        self.assertFalse(tray.thread.is_alive())
        self.assertFalse(tray.start())

    @patch.dict(os.environ, {'DEEPFOCUS_TESTING': '0'})
    def test_stop_before_window_exists_prevents_late_worker_from_adding_icon(self):
        class DelayedTray(TrayIcon):
            def _run(self):
                self._stopping.wait(2)
                self.available = not self._stopping.is_set()
                self._ready.set()
        tray = DelayedTray('unused.ico', Mock())
        # Don't wait for the public start timeout while checking the race.
        thread = threading.Thread(target=tray.start)
        thread.start()
        try:
            for _ in range(100):
                if tray.thread is not None:
                    break
                threading.Event().wait(.005)
            tray.stop()
        finally:
            thread.join(3)
        self.assertFalse(tray.available)
        self.assertFalse(thread.is_alive())
        self.assertFalse(tray.thread.is_alive())


class ShutdownCoexistenceTests(unittest.TestCase):
    def test_existing_windows_shutdown_is_not_canceled_to_replace_it(self):
        scheduler = ShutdownScheduler()
        error = OSError('another application scheduled shutdown')
        error.winerror = 1190
        with patch.object(scheduler, '_run', side_effect=error) as command:
            with self.assertRaises(OSError):
                scheduler.schedule(60)
        self.assertIsNone(scheduler.deadline)
        command.assert_called_once_with(['/s', '/t', '60'])

    def test_cancel_denied_by_windows_keeps_own_reminder(self):
        scheduler = ShutdownScheduler()
        with patch.object(scheduler, '_run') as command:
            scheduler.schedule(60)
            deadline = scheduler.deadline
            command.side_effect = PermissionError('Windows policy')
            with self.assertRaises(PermissionError):
                scheduler.cancel()
        self.assertEqual(scheduler.deadline, deadline)

    def test_resume_after_elapsed_countdown_clears_only_reminder(self):
        scheduler = ShutdownScheduler()
        with patch.object(scheduler, '_run') as command, \
                patch('core.shutdown_scheduler.time.monotonic', return_value=100) as clock:
            scheduler.schedule(60)
            command.reset_mock()
            clock.return_value = 4000
            self.assertTrue(scheduler.refresh())
            command.assert_not_called()
            self.assertIsNone(scheduler.deadline)


@unittest.skipUnless(os.name == 'nt', 'Windows native named objects')
class NativeConcurrentLaunchTests(unittest.TestCase):
    def test_six_processes_share_one_primary_and_activation_then_release_workspace(self):
        script = (
            'import json,sys; from core.instance import SingleInstance; '
            'guard=SingleInstance(sys.argv[1]); '
            'print(json.dumps({"primary":guard.is_primary}),flush=True); '
            'sys.stdin.readline(); guard.close()'
        )
        processes = []
        with tempfile.TemporaryDirectory() as folder:
            try:
                for _ in range(6):
                    processes.append(subprocess.Popen(
                        [sys.executable, '-B', '-c', script, folder],
                        cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW))
                values = [json.loads(process.stdout.readline()) for process in processes]
                self.assertEqual(sum(value['primary'] for value in values), 1)
                observer = SingleInstance(folder)
                try:
                    self.assertFalse(observer.is_primary)
                    self.assertTrue(observer.activate())
                    self.assertTrue(observer.consume_activation())
                finally:
                    observer.close()
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.stdin.write('\n')
                        process.stdin.flush()
                    stdout, stderr = process.communicate(timeout=8)
                    self.assertEqual(process.returncode, 0, stderr)
            fresh = SingleInstance(folder)
            try:
                self.assertTrue(fresh.is_primary)
            finally:
                fresh.close()


if __name__ == '__main__':
    unittest.main()
