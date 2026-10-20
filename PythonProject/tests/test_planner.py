"""Planner persistence, scheduling, migration and backup behavior."""
from datetime import datetime
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import utils.constants as constants
from data.database import DatabaseManager, SCHEMA_VERSION
from data.models import FocusMode
from core.planner import PlanTask, PlannerStore
from core.backup import BackupManager


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        for key,value in (('DB_DIR',str(self.folder)),('CONFIG_PATH',str(self.folder/'settings.json'))):
            patcher=patch.object(constants,key,value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.db=DatabaseManager(self.folder/'workspace.db')
        self.store=PlannerStore(self.db)

    def test_task_and_steps_survive_restart_and_completion_is_reversible(self):
        task=PlanTask(title='  Write proposal  ',day='2026-10-19',start_time='9:05',minutes=60,
            notes='Outline first',priority='High',checklist=[{'text':' Draft ','done':False}])
        ident=self.store.save(task)
        self.store.step(ident,0,True)
        self.store.complete(ident,True)
        reopened=PlannerStore(DatabaseManager(self.db.db_path)).get(ident)
        self.assertEqual((reopened.title,reopened.start_time,reopened.notes),('Write proposal','09:05','Outline first'))
        self.assertTrue(reopened.completed)
        self.assertEqual(reopened.checklist,[{'text':'Draft','done':True}])
        self.store.complete(ident,False)
        self.assertFalse(self.store.get(ident).completed)
        self.assertTrue(self.store.get(ident).checklist[0]['done'])

    def test_validation_is_atomic(self):
        for changes in ({'title':' '},{'day':'2026-02-30'},{'start_time':'25:00'},
                {'minutes':0},{'minutes':721},{'minutes':True},{'priority':'Urgent'},
                {'checklist':[{'text':'x'*201}]},{'checklist':[{'bad':'step'}]}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.store.save(replace(PlanTask(title='Task'),**changes))
        self.assertEqual(self.store.list('0001-01-01','9999-12-31'),[])

    def test_agenda_orders_time_before_anytime_and_completed_last(self):
        for title,time,priority,done in [('Anytime low','','Low',False),('Later','14:00','Normal',False),
                ('Early','08:00','Normal',False),('Done','07:00','High',True),('Anytime high','','High',False)]:
            self.store.save(PlanTask(title=title,day='2026-10-19',start_time=time,priority=priority,completed=done))
        self.store.save(PlanTask(title='Other day',day='2026-10-20'))
        self.assertEqual([t.title for t in self.store.list('2026-10-19')],['Early','Later','Anytime high','Anytime low','Done'])

    def test_reminder_once_after_restart_and_rearmed_only_when_schedule_changes(self):
        ident=self.store.save(PlanTask(title='Task',day='2026-10-19',start_time='09:00'))
        self.assertEqual(self.store.due(datetime(2026,10,19,8,59)),[])
        self.assertEqual([t.id for t in self.store.due(datetime(2026,10,19,9,0))],[ident])
        reopened=PlannerStore(DatabaseManager(self.db.db_path))
        self.assertEqual(reopened.due(datetime(2026,10,19,10,0)),[])
        task=reopened.get(ident)
        task.title='Renamed'
        reopened.save(task)
        self.assertEqual(reopened.due(datetime(2026,10,19,10,0)),[])
        task.start_time='10:30'
        reopened.save(task)
        self.assertEqual(reopened.due(datetime(2026,10,19,10,29)),[])
        self.assertEqual(len(reopened.due(datetime(2026,10,19,10,30))),1)

    def test_reminders_ignore_other_dates_completed_unscheduled_and_disabled(self):
        for task in [PlanTask(title='Past',day='2026-10-18',start_time='09:00'),
                PlanTask(title='Future',day='2026-10-20',start_time='09:00'),
                PlanTask(title='Done',day='2026-10-19',start_time='09:00',completed=True),
                PlanTask(title='Silent',day='2026-10-19',start_time='09:00',reminder=False),
                PlanTask(title='Anytime',day='2026-10-19')]:
            self.store.save(task)
        self.assertEqual(self.store.due(datetime(2026,10,19,15,0)),[])

    def test_conflicts_allow_adjacent_blocks_and_ignore_completed(self):
        tasks=[PlanTask(id=1,title='First',day='2026-10-19',start_time='09:00',minutes=60),
            PlanTask(id=2,title='Adjacent',day='2026-10-19',start_time='10:00',minutes=25),
            PlanTask(id=3,title='Overlap',day='2026-10-19',start_time='09:40',minutes=10),
            PlanTask(id=4,title='Done',day='2026-10-19',start_time='09:00',completed=True)]
        self.assertEqual(self.store.conflicts(tasks),{1,3})

    def test_deleted_mode_does_not_delete_task_and_cannot_be_silently_selected(self):
        mode_id=self.db.save_mode(FocusMode(name='Writing'))
        ident=self.store.save(PlanTask(title='Write',mode_id=mode_id))
        self.db.delete_mode(mode_id)
        task=self.store.get(ident)
        self.assertEqual(task.title,'Write')
        with self.assertRaisesRegex(ValueError,'removed'):
            self.store.save(task)
        task.mode_id=None
        self.store.save(task)

    def test_conflicts_cross_midnight_without_colliding_on_different_dates(self):
        tasks=[PlanTask(id=1,title='Night',day='2026-10-19',start_time='23:30',minutes=60),
            PlanTask(id=2,title='Next day',day='2026-10-20',start_time='00:15',minutes=25),
            PlanTask(id=3,title='Different day',day='2026-10-21',start_time='00:15',minutes=25)]
        self.assertEqual(self.store.conflicts(tasks),{1,2})

    def test_v2_upgrade_preserves_data_and_keeps_recoverable_snapshot(self):
        original=self.db.get_mode_by_name('Default').id
        with self.db.connection() as conn:
            conn.execute('DROP TABLE planner_tasks')
            conn.execute('PRAGMA user_version=2')
        upgraded=DatabaseManager(self.db.db_path)
        self.assertEqual(upgraded.get_mode_by_name('Default').id,original)
        self.assertEqual(PlannerStore(upgraded).list('2026-10-19'),[])
        with upgraded.connection() as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],SCHEMA_VERSION)
        backup=list((self.folder/'backups').glob('pre-migration-*.sqlite3'))
        self.assertEqual(len(backup),1)
        with closing(sqlite3.connect(backup[0])) as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],2)

    def test_workspace_backup_restores_task_checklist_and_reminder_state(self):
        ident=self.store.save(PlanTask(title='Keep me',day='2026-10-19',start_time='09:00',
            checklist=[{'text':'Saved step','done':True}]))
        self.store.due(datetime(2026,10,19,10,0))
        manager=BackupManager(self.db,self.folder)
        target=self.folder/'backup.zip'
        manager.export_workspace(target)
        self.store.delete(ident)
        manager.restore_workspace(target)
        restored=PlannerStore(DatabaseManager(self.db.db_path)).get(ident)
        self.assertEqual(restored.title,'Keep me')
        self.assertTrue(restored.checklist[0]['done'])
        self.assertTrue(restored.reminded_at)


if __name__=='__main__':
    unittest.main()
