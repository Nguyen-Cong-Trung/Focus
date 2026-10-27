"""Coexistence with hosts entries owned by Windows/other applications."""
from pathlib import Path
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from core.site_blocker import SiteBlocker
from core.app_blocker import AppBlocker


class HostsCoexistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.hosts = Path(self.temp.name) / 'hosts'
        self.blocker = SiteBlocker()
        self.blocker.HOSTS_PATH = str(self.hosts)
        self.addCleanup(patch.stopall)
        patch.object(self.blocker, 'is_admin', return_value=True).start()
        patch.object(SiteBlocker, '_flush_dns').start()

    def test_other_apps_unicode_comments_crlf_and_no_final_newline_survive(self):
        original = '# Máy tính — VPN\r\n127.0.0.1 localhost\r\n10.0.0.1 company.local'.encode('utf-8')
        self.hosts.write_bytes(original)
        self.assertTrue(self.blocker.block(['example.com']))
        self.assertTrue(self.blocker.unblock())
        self.assertEqual(self.hosts.read_bytes(), original)

    def test_empty_and_carriage_return_terminated_files_round_trip_exactly(self):
        for original in (b'', b'127.0.0.1 localhost\r', b'127.0.0.1 localhost\r\n'):
            with self.subTest(original=original):
                self.hosts.write_bytes(original)
                self.assertTrue(self.blocker.block(['example.com']))
                self.assertTrue(self.blocker.unblock())
                self.assertEqual(self.hosts.read_bytes(), original)

    def test_reversed_or_nested_markers_cannot_delete_other_entries(self):
        start, end = self.blocker.BLOCK_START_MARKER, self.blocker.BLOCK_END_MARKER
        for original in (f'{end}\n10.0.0.1 vpn.local\n{start}\n',
                         f'{start}\n{start}\n127.0.0.1 blocked.test\n{end}\n10.0.0.1 vpn.local\n{end}\n'):
            with self.subTest(original=original):
                self.hosts.write_text(original)
                self.assertFalse(self.blocker.unblock())
                self.assertEqual(self.hosts.read_text(), original)

    def test_entries_added_by_another_app_below_our_section_keep_line_separation(self):
        self.hosts.write_bytes(b'127.0.0.1 localhost')
        self.assertTrue(self.blocker.block(['example.com']))
        with self.hosts.open('ab') as other_app:
            other_app.write(b'10.0.0.1 vpn.local\n')
        self.assertTrue(self.blocker.unblock())
        self.assertEqual(self.hosts.read_bytes(), b'127.0.0.1 localhost\n10.0.0.1 vpn.local\n')

    def test_emergency_cleanup_will_not_truncate_malformed_hosts_section(self):
        original = self.blocker.BLOCK_START_MARKER + '\n10.0.0.1 vpn.local\n'
        self.hosts.write_text(original)
        with patch.object(SiteBlocker, 'HOSTS_PATH', str(self.hosts)):
            SiteBlocker.force_unblock()
        self.assertEqual(self.hosts.read_text(), original)

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing modes')
    def test_other_writers_cannot_overwrite_hosts_mid_update(self):
        self.hosts.write_bytes(b'10.0.0.1 vpn.local\r\n')
        with self.blocker._writable_hosts() as owned:
            self.assertEqual(owned.read(), b'10.0.0.1 vpn.local\r\n')
            with self.assertRaises(PermissionError):
                with self.hosts.open('wb'):
                    pass
        self.assertEqual(self.hosts.read_bytes(), b'10.0.0.1 vpn.local\r\n')


class MonitorCoexistenceTests(unittest.TestCase):
    def test_stop_before_worker_starts_prevents_initial_process_action(self):
        blocker = AppBlocker()
        blocker.request_stop()
        with patch.object(blocker, 'kill_apps') as kill:
            blocker._monitor_loop(['Unrelated.exe'], .01)
        kill.assert_not_called()

    def test_switching_mode_does_not_resurrect_timed_out_old_monitor(self):
        blocker = AppBlocker()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        self.addCleanup(blocker.stop_monitoring)
        def action(names):
            if names == ['Old.exe']:
                entered.set()
                release.wait(2)
        with patch.object(blocker, 'kill_apps', side_effect=action):
            blocker.start_monitoring(['Old.exe'], interval=.01)
            self.assertTrue(entered.wait(1))
            old = blocker._monitor_thread
            # Simulate a Windows process call outliving the join timeout.
            with patch.object(old, 'join', return_value=None):
                blocker.start_monitoring(['New.exe'], interval=.01)
            release.set()
            old.join(.3)
            try:
                self.assertFalse(old.is_alive(), 'old mode continued killing after a switch')
            finally:
                blocker.stop_monitoring()
                old.join(2)


if __name__ == '__main__':
    unittest.main()
