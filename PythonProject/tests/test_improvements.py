"""Behavioral regressions, with temporary storage and no OS/UI automation."""
import json
import os
from pathlib import Path
import sqlite3
import struct
import tempfile
import threading
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import wave
import zipfile

import utils.constants as constants
from data.database import DatabaseManager
from data.models import FocusMode, BlockedItem, FocusSession
from core.audio_library import AudioLibrary, inspect_wav
from core.backup import BackupManager
from core.blocking import BlockingCoordinator
from core.timer_engine import TimerEngine
from core.shutdown_scheduler import ShutdownScheduler
from core.sound_engine import SoundEngine
from core.work import BackgroundWork
from core.tray import TrayIcon
from utils.validation import hostname, application, blocklist


def wav(path, width=2, rate=22050, frames=100):
    with wave.open(str(path),'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(width)
        file.setframerate(rate)
        file.writeframes((b'\x80' if width==1 else b'\0'*width)*frames)


class StorageFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.folder=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        for name,value in (('DB_DIR',str(self.folder)),('CONFIG_PATH',str(self.folder/'config.json'))):
            patcher=patch.object(constants,name,value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.db=DatabaseManager(self.folder/'data.sqlite3')


class ModeStorageTests(StorageFixture):
    def test_empty_list_stays_empty_after_reopening(self):
        for row in self.db.get_blocked_items(): self.db.delete_blocked_item(row.id)
        reopened=DatabaseManager(self.db.db_path)
        self.assertEqual(reopened.get_blocked_items(),[])

    def test_modes_keep_independent_lists_and_disabled_states(self):
        original=self.db.active_mode_id
        item=self.db.get_blocked_items()[0]
        self.db.toggle_blocked_item(item.id,False)
        other=self.db.save_mode(FocusMode(name='Other',blocked_sites='["https://Example.com/path"]'))
        self.db.set_active_mode(other)
        self.assertEqual([x.value for x in self.db.get_blocked_items()],['example.com'])
        self.db.set_active_mode(original)
        self.assertFalse(self.db.get_blocked_items()[0].enabled)

    def test_editing_mode_updates_its_lists_without_global_overwrite(self):
        ident=self.db.save_mode(FocusMode(name='Work'))
        self.db.set_active_mode(ident)
        mode=self.db.get_mode(ident)
        mode.blocked_apps='["Game.exe"]'
        mode.focus_minutes=42
        self.db.update_mode(mode)
        self.assertEqual([r.value for r in self.db.get_blocked_items()],['Game.exe'])
        reopened=DatabaseManager(self.db.db_path,'Work')
        self.assertEqual(reopened.get_mode(ident).focus_minutes,42)

    def test_auto_sound_roundtrips(self):
        ident=self.db.save_mode(FocusMode(name='Music',auto_sound='rain',auto_sound_volume=.17))
        self.assertEqual(self.db.get_mode(ident).auto_sound,'rain')
        self.assertEqual(self.db.get_mode(ident).auto_sound_volume,.17)

    def test_duplicate_names_are_validation_errors(self):
        self.db.save_mode(FocusMode(name='Writing'))
        with self.assertRaisesRegex(ValueError,'already exists'):
            self.db.save_mode(FocusMode(name='writing'))

    def test_duplicate_domains_are_not_added_twice(self):
        self.db.add_blocked_item(BlockedItem(value='HTTPS://WWW.Example.com/page'))
        self.db.add_blocked_item(BlockedItem(value='www.example.com'))
        self.assertEqual(sum(r.value=='www.example.com' for r in self.db.get_blocked_items()),1)

    def test_migration_backups_and_preserves_legacy_empty_list(self):
        path=self.folder/'legacy.sqlite3'
        with sqlite3.connect(path) as conn:
            conn.execute('CREATE TABLE blocked_items(id INTEGER PRIMARY KEY,name TEXT,item_type TEXT,value TEXT,enabled INTEGER)')
        conn.close()
        migrated=DatabaseManager(path)
        self.assertEqual(migrated.get_blocked_items(),[])
        self.assertTrue(list((self.folder/'backups').glob('pre-migration-*.sqlite3')))

    def test_history_filters_and_includes_measured_incomplete_time(self):
        self.db.save_session(FocusSession(completed=False,elapsed_seconds=40,outcome='skipped',mode_name='Work'))
        self.db.save_session(FocusSession(completed=True,elapsed_seconds=60,outcome='completed'))
        self.assertEqual(len(self.db.get_sessions(outcome='skipped')),1)
        self.assertAlmostEqual(self.db.get_total_focus_hours(),100/3600)
        self.assertEqual(self.db.get_today_stats().completed_sessions,1)


class ConfigTests(StorageFixture):
    def test_patch_does_not_overwrite_unrelated_saved_preferences(self):
        constants.update_config({'hardcore_sites':['latest.example'],'global_hotkeys':True})
        constants.update_config({'active_mode':'Work'})
        config=constants.load_config()
        self.assertEqual(config['hardcore_sites'],['latest.example'])
        self.assertTrue(config['global_hotkeys'])

    def test_hotkey_change_applies_to_running_manager(self):
        from ui.app import DeepFocusApp
        app=NS(hotkeys=Mock())
        app.hotkeys.enable.return_value=True
        DeepFocusApp.update_settings(app,{'global_hotkeys':True})
        app.hotkeys.enable.assert_called_once()
        DeepFocusApp.update_settings(app,{'global_hotkeys':False})
        app.hotkeys.disable.assert_called_once()

    def test_shutdown_reminder_survives_restart_without_claiming_verification(self):
        first=ShutdownScheduler(persist=True)
        with patch.object(first,'_run'):
            first.schedule(120)
        second=ShutdownScheduler(persist=True)
        self.assertTrue(second.restored)
        self.assertGreater(second.remaining_seconds,100)
        with patch.object(second,'_run'):
            second.cancel()
        self.assertIsNone(ShutdownScheduler(persist=True).deadline)

    def test_shutdown_reports_accepted_os_command_when_reminder_save_fails(self):
        scheduler=ShutdownScheduler(persist=True)
        with patch.object(scheduler,'_run'), patch('utils.constants.update_config',side_effect=OSError('Read-only folder')):
            with self.assertRaisesRegex(OSError,'Windows accepted'):
                scheduler.schedule(120)
        self.assertIsNotNone(scheduler.deadline)


class BlockingTests(unittest.TestCase):
    def test_idle_or_break_never_starts_a_blocker(self):
        sites,apps=Mock(),Mock()
        controller=BlockingCoordinator(sites,apps)
        self.addCleanup(controller.close)
        controller.apply(False,['example.com'],['Game.exe']).result(2)
        sites.block.assert_not_called()
        apps.start_monitoring.assert_not_called()
        sites.unblock.assert_called()

    def test_one_blocker_failure_does_not_prevent_the_other(self):
        sites,apps=Mock(),Mock()
        sites.block.side_effect=OSError('Permission denied')
        controller=BlockingCoordinator(sites,apps)
        self.addCleanup(controller.close)
        with self.assertLogs('core.blocking',level='ERROR'):
            controller.apply(True,['example.com'],['Game.exe']).result(2)
        apps.start_monitoring.assert_called_once_with(['Game.exe'],interval=5)

    def test_stale_enable_cannot_start_apps_after_stop_requested(self):
        entered,release=threading.Event(),threading.Event()
        sites,apps=Mock(),Mock()
        def block(_):
            entered.set()
            release.wait(2)
            return True
        sites.block.side_effect=block
        controller=BlockingCoordinator(sites,apps)
        self.addCleanup(controller.close)
        pending=controller.apply(True,['example.com'],['Game.exe'])
        self.assertTrue(entered.wait(2))
        stopped=controller.apply(False)
        release.set()
        pending.result(2)
        stopped.result(2)
        apps.start_monitoring.assert_not_called()

    def test_audio_failure_does_not_skip_blocking(self):
        from ui.app import DeepFocusApp
        app=NS(apply_blocking=Mock(),active_mode=lambda:FocusMode(auto_sound='rain'),sound_engine=Mock(),
               _audio_generation=0,report_error=Mock())
        app.sound_engine.is_playing.return_value=False
        app.sound_engine.play.side_effect=RuntimeError('Audio unavailable')
        def run(function,success,error,lane):
            try: success(function())
            except RuntimeError as exc: error(exc)
        app.run_background=run
        DeepFocusApp._on_focus_start(app)
        app.apply_blocking.assert_called_once()
        app.report_error.assert_called_once()

    def test_locked_focus_blocks_stop_skip_and_edits_but_not_breaks(self):
        from ui.app import DeepFocusApp
        app=NS(active_mode=lambda:FocusMode(dead_lock=True),timer_engine=TimerEngine(),
               _restoring=False,_closing=False,report_error=Mock())
        app.is_focus_phase=lambda:DeepFocusApp.is_focus_phase(app)
        app.blocking_locked=lambda:DeepFocusApp.blocking_locked(app)
        app.timer_engine.start_focus()
        DeepFocusApp.stop_focus(app)
        DeepFocusApp.skip_phase(app)
        self.assertFalse(DeepFocusApp.allow_blocklist_edit(app))
        self.assertEqual(app.timer_engine.state,constants.TimerState.FOCUSING)
        app.timer_engine.pause()
        self.assertTrue(app.blocking_locked())
        app.timer_engine.start_break('short_break')
        self.assertTrue(DeepFocusApp.allow_blocklist_edit(app))


class MeasuredTimeTests(unittest.TestCase):
    @patch('core.timer_engine.time.monotonic',return_value=100)
    def test_pauses_excluded_and_skip_is_not_completion(self,clock):
        db=Mock()
        engine=TimerEngine(db)
        engine.start_focus()
        clock.return_value=110
        engine.pause()
        clock.return_value=910
        engine.resume()
        clock.return_value=930
        engine.skip()
        saved=db.save_session.call_args.args[0]
        self.assertEqual(saved.elapsed_seconds,30)
        self.assertEqual(saved.outcome,'skipped')
        self.assertFalse(saved.completed)


class InputTests(unittest.TestCase):
    def test_domains_normalized_and_bad_inputs_rejected(self):
        self.assertEqual(hostname('https://YouTube.com/watch?v=1'),'youtube.com')
        self.assertEqual(blocklist(['example.com','EXAMPLE.com/x'],'website'),['example.com'])
        for value in ('file:///etc/hosts','bad domain','https://user:pass@example.com','bad..example'):
            with self.assertRaises(ValueError): hostname(value)
        for value in ('*.exe',r'C:\\Game.exe','/IM Game.exe'):
            with self.assertRaises(ValueError): application(value)


class AudioLibraryTests(StorageFixture):
    def test_same_filename_imports_are_independent_and_remove_detaches_modes(self):
        source=self.folder/'rain.wav'
        wav(source)
        library=AudioLibrary(self.db,self.folder/'sounds')
        first=library.import_file(source)
        second=library.import_file(source)
        sounds=self.db.get_all_custom_sounds()
        self.assertEqual(len(sounds),2)
        self.assertNotEqual(sounds[0].file_path,sounds[1].file_path)
        mode_id=self.db.save_mode(FocusMode(name='Music',auto_sound=f'custom_{first}'))
        library.remove(next(s for s in sounds if s.id==first))
        self.assertEqual(self.db.get_mode(mode_id).auto_sound,'none')
        self.assertTrue(Path(next(s.file_path for s in sounds if s.id==second)).exists())

    def test_invalid_wav_does_not_add_a_database_record(self):
        source=self.folder/'bad.wav'
        source.write_bytes(b'not a WAV file'*8)
        with self.assertRaises(ValueError): AudioLibrary(self.db,self.folder/'sounds').import_file(source)
        self.assertEqual(self.db.get_all_custom_sounds(),[])

    def test_pcm_widths_and_resampling_decode_without_audio_device(self):
        engine=SoundEngine()
        for width in (1,2,3,4):
            source=self.folder/f'{width}.wav'
            wav(source,width=width)
            buffer=engine._load_wav_buffer(source)
            self.assertEqual(buffer.shape,(200,2))
            self.assertTrue((buffer==0).all())


class BackupTests(StorageFixture):
    def test_restore_rolls_database_back_if_settings_cannot_be_saved(self):
        manager=BackupManager(self.db,self.folder)
        self.db.save_mode(FocusMode(name='Archived'))
        archive=self.folder/'saved.zip'
        manager.export_workspace(archive)
        self.db.delete_mode(self.db.get_mode_by_name('Archived').id)
        self.db.save_mode(FocusMode(name='Current'))
        attempts=[]
        def save(changes):
            attempts.append(changes)
            if len(attempts)==1: raise OSError('Disk unavailable')
            return constants.update_config(changes)
        with patch('core.backup.update_config',side_effect=save):
            with self.assertRaises(OSError): manager.restore_workspace(archive)
        self.assertIsNotNone(self.db.get_mode_by_name('Current'))
        self.assertIsNone(self.db.get_mode_by_name('Archived'))

    def test_backup_cannot_overwrite_its_own_database(self):
        manager=BackupManager(self.db,self.folder)
        with self.assertRaises(ValueError): manager.export_workspace(self.db.db_path)
        with self.assertRaises(ValueError): manager.export_modes(self.db.db_path)
        self.assertIsNotNone(self.db.get_mode_by_name('Default'))

    def test_backup_restore_recovers_modes_recordings_and_history(self):
        source=self.folder/'recording.wav'
        wav(source)
        AudioLibrary(self.db,self.folder/'sounds').import_file(source)
        self.db.save_mode(FocusMode(name='Saved',focus_minutes=43))
        self.db.save_session(FocusSession(completed=True,elapsed_seconds=30,outcome='completed'))
        constants.update_config({'theme':'light','shutdown_record':{'deadline':'2099-01-01T00:00:00'}})
        manager=BackupManager(self.db,self.folder)
        archive=self.folder/'workspace.zip'
        manager.export_workspace(archive)
        self.db.delete_mode(self.db.get_mode_by_name('Saved').id)
        constants.update_config({'theme':'dark'})
        result=manager.restore_workspace(archive)
        self.assertEqual(self.db.get_mode_by_name('Saved').focus_minutes,43)
        self.assertEqual(len(self.db.get_sessions()),1)
        self.assertEqual(constants.load_config()['theme'],'light')
        self.assertEqual(constants.load_config()['shutdown_record']['deadline'],'2099-01-01T00:00:00')
        self.assertTrue(Path(result['backup']).is_file())
        self.assertTrue(Path(self.db.get_all_custom_sounds()[0].file_path).is_file())

    def test_mode_import_avoids_name_collisions_and_keeps_disabled_items(self):
        row=self.db.get_blocked_items()[0]
        self.db.toggle_blocked_item(row.id,False)
        manager=BackupManager(self.db,self.folder)
        file=self.folder/'modes.json'
        manager.export_modes(file)
        manager.import_modes(file)
        modes=self.db.get_all_modes()
        self.assertEqual(len(modes),2)
        added=next(m for m in modes if not m.is_default)
        self.db.set_active_mode(added.id)
        self.assertFalse(next(r for r in self.db.get_blocked_items() if r.value==row.value).enabled)

    def test_invalid_backup_cannot_change_current_database(self):
        file=self.folder/'invalid.zip'
        with zipfile.ZipFile(file,'w') as archive:
            archive.writestr('manifest.json',json.dumps({'format':'not-deep-focus'}))
        with self.assertRaises((ValueError,KeyError)):
            BackupManager(self.db,self.folder).restore_workspace(file)
        self.assertIsNotNone(self.db.get_mode_by_name('Default'))

    def test_bad_mode_import_is_all_or_nothing(self):
        file=self.folder/'bad-modes.json'
        file.write_text(json.dumps({'format':'deep-focus-modes','version':1,'modes':[
            {'name':'Good'},{'name':'Bad','focus_minutes':0}]}),encoding='utf-8')
        with self.assertRaises(ValueError): BackupManager(self.db,self.folder).import_modes(file)
        self.assertIsNone(self.db.get_mode_by_name('Good'))


class BackgroundTests(unittest.TestCase):
    def test_result_callbacks_are_drained_by_caller_not_worker(self):
        work=BackgroundWork()
        self.addCleanup(work.close)
        observed=[]
        work.submit(lambda:42,lambda value:observed.append((value,threading.get_ident()))).result(2)
        work.drain()
        self.assertEqual(observed,[(42,threading.get_ident())])

    @patch.dict(os.environ,{'DEEPFOCUS_TESTING':'1'})
    def test_tray_is_disabled_in_tests_and_never_hides_window_on_failure(self):
        tray=TrayIcon('unused.ico',Mock())
        self.assertFalse(tray.start())
        self.assertFalse(tray.available)


class HostsTests(unittest.TestCase):
    def test_url_blocking_preserves_unrelated_hosts_and_unblock_restores_them(self):
        from core.site_blocker import SiteBlocker
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
            hosts=Path(folder)/'hosts'
            original='127.0.0.1 localhost\n10.0.0.1 internal.example\n'
            hosts.write_text(original)
            blocker=SiteBlocker()
            blocker.HOSTS_PATH=str(hosts)
            with patch.object(blocker,'is_admin',return_value=True),patch.object(blocker,'_flush_dns'):
                self.assertTrue(blocker.block(['https://Example.com/a']))
                self.assertIn('127.0.0.1 example.com',hosts.read_text())
                self.assertTrue(blocker.unblock())
            self.assertEqual(hosts.read_text(),original)

    def test_unmatched_marker_cannot_delete_unrelated_hosts(self):
        from core.site_blocker import SiteBlocker
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
            hosts=Path(folder)/'hosts'
            original=SiteBlocker.BLOCK_START_MARKER+'\n10.0.0.1 internal.example\n'
            hosts.write_text(original)
            blocker=SiteBlocker()
            blocker.HOSTS_PATH=str(hosts)
            self.assertFalse(blocker.unblock())
            self.assertEqual(hosts.read_text(),original)


if __name__=='__main__': unittest.main()
