"""Real temporary SQLite concurrency; no personal workspace access."""
from contextlib import contextmanager, closing
from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest

from data.database import DatabaseManager
from core.planner import PlannerStore, PlanTask


class DataCoexistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = DatabaseManager(Path(self.temp.name) / 'workspace.db')
        self.planner = PlannerStore(self.db)

    def concurrent_after_read(self, operation, prefix):
        first_read, second_read, release = threading.Event(), threading.Event(), threading.Event()
        original = self.db.connection
        errors, results = [], []

        class Cursor:
            def __init__(self, rows): self.rows = rows
            def fetchone(self): return self.rows[0] if self.rows else None
            def fetchall(self): return self.rows

        class Proxy:
            def __init__(self, connection): self.connection = connection
            def __getattr__(self, name): return getattr(self.connection, name)
            def execute(self, sql, args=()):
                cursor = self.connection.execute(sql, args)
                if sql.startswith(prefix):
                    rows = cursor.fetchall()  # Snapshot finalized before the competing writer.
                    if threading.current_thread().name == 'first':
                        first_read.set()
                        if not release.wait(3): raise TimeoutError('test did not release first read')
                    else:
                        second_read.set()
                    return Cursor(rows)
                return cursor

        @contextmanager
        def connection():
            with original() as conn:
                yield Proxy(conn)
        self.db.connection = connection

        def run(index):
            try: results.append(operation(index))
            except BaseException as error: errors.append(error)
        first = threading.Thread(target=run, args=(0,), name='first')
        second = threading.Thread(target=run, args=(1,), name='second')
        try:
            first.start()
            self.assertTrue(first_read.wait(2))
            second.start()
            # Unfixed code lets the second writer finish before the first;
            # a write transaction intentionally blocks its read until release.
            second_read.wait(.2)
        finally:
            release.set()
            first.join(3)
            if second.ident is not None: second.join(3)
            self.db.connection = original
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(errors, [])
        return results

    def test_simultaneous_checklist_edits_do_not_lose_the_other_step(self):
        task = PlanTask(title='Both edits', checklist=[{'text': 'one'}, {'text': 'two'}])
        self.planner.save(task)
        self.concurrent_after_read(lambda index: self.planner.step(task.id, index, True),
                                   'SELECT checklist FROM planner_tasks')
        self.assertEqual([s['done'] for s in self.planner.get(task.id).checklist], [True, True])

    def test_simultaneous_reminder_polls_return_a_task_only_once(self):
        now = datetime(2026, 10, 28, 12, 0)
        self.planner.save(PlanTask(title='One reminder', day=now.date().isoformat(), start_time='11:30'))
        results = self.concurrent_after_read(lambda _: self.planner.due(now), 'SELECT * FROM planner_tasks WHERE day=')
        self.assertEqual(sum(len(result) for result in results), 1)

    def test_external_database_lock_cannot_hang_backup_forever(self):
        target = Path(self.temp.name) / 'locked.db'
        with closing(sqlite3.connect(target)) as lock:
            lock.execute('CREATE TABLE occupied(value)')
            lock.commit()
            lock.execute('BEGIN EXCLUSIVE')
            start = time.monotonic()
            source = sqlite3.connect(self.db.db_path, timeout=.1)
            dest = sqlite3.connect(target, timeout=.1)
            try:
                with self.assertRaisesRegex(TimeoutError, 'busy in another application'):
                    DatabaseManager.backup_connection(source, dest, timeout=.15)
            finally:
                source.close()
                dest.close()
            self.assertLess(time.monotonic() - start, 2)
            lock.rollback()
        self.db.backup_to(target)
        with closing(sqlite3.connect(target)) as check:
            self.assertEqual(check.execute('PRAGMA integrity_check').fetchone()[0], 'ok')


if __name__ == '__main__':
    unittest.main()
