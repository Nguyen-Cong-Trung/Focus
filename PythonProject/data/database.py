"""Transactional, mode-scoped SQLite storage with recoverable migrations."""
import json
import sqlite3
import time
from contextlib import contextmanager, closing
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from utils.constants import DB_PATH, DEFAULT_BLOCKED_SITES, DEFAULT_BLOCKED_APPS
from utils.validation import blocklist, validate_mode
from data.models import FocusSession, BlockedItem, DailyStats, FocusMode, CustomSound

SCHEMA_VERSION = 3


class DatabaseManager:
    def __init__(self, db_path=None, active_mode_name='Default'):
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        if Path(self.db_path).exists() and Path(self.db_path).stat().st_size:
            with closing(sqlite3.connect(self.db_path)) as conn:
                version = conn.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("This workspace needs a newer Focus version.")
            if version < SCHEMA_VERSION:
                folder = Path(self.db_path).parent / 'backups'
                folder.mkdir(exist_ok=True)
                self.backup_to(folder / f'pre-migration-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}.sqlite3')
        self.init_db(active_mode_name)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def backup_to(self, target):
        with closing(sqlite3.connect(self.db_path)) as source, closing(sqlite3.connect(str(target))) as dest:
            self.backup_connection(source, dest)

    @staticmethod
    def backup_connection(source, destination, timeout=10.0):
        """Bound SQLite's busy retry loop when another app holds the database.

        Connection timeout does not bound Connection.backup(), which otherwise
        retries busy/locked pages forever (including on a source read lock).
        """
        deadline = time.monotonic() + timeout
        def progress(status, remaining, total):
            if time.monotonic() >= deadline and status != sqlite3.SQLITE_DONE:
                raise TimeoutError('The workspace is busy in another application. Close it and try again.')
        source.backup(destination, pages=256, progress=progress, sleep=.05)

    def init_db(self, active_mode_name='Default'):
        with self.connection() as conn:
            legacy = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='blocked_items'").fetchone() is not None
            conn.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS focus_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, start_time TEXT, end_time TEXT,
                    duration_minutes INTEGER, completed INTEGER, session_type TEXT);
                CREATE TABLE IF NOT EXISTS focus_modes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                    focus_minutes INTEGER DEFAULT 25, short_break_minutes INTEGER DEFAULT 5,
                    long_break_minutes INTEGER DEFAULT 15, sessions_before_long_break INTEGER DEFAULT 4,
                    blocked_sites TEXT DEFAULT '[]', blocked_apps TEXT DEFAULT '[]',
                    dead_lock INTEGER DEFAULT 0, notifications INTEGER DEFAULT 1, is_default INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS blocked_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, item_type TEXT,
                    value TEXT, enabled INTEGER DEFAULT 1);
                CREATE TABLE IF NOT EXISTS custom_sounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                    icon TEXT DEFAULT '🎵', file_path TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS planner_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                    day TEXT NOT NULL, start_time TEXT DEFAULT '', minutes INTEGER DEFAULT 25,
                    priority TEXT DEFAULT 'Normal', notes TEXT DEFAULT '', checklist TEXT DEFAULT '[]',
                    mode_id INTEGER, completed INTEGER DEFAULT 0, reminder INTEGER DEFAULT 1,
                    reminded_at TEXT DEFAULT '', created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_planner_day ON planner_tasks(day,completed,start_time);
            """)
            additions = {
                'focus_modes': {'auto_flow':'INTEGER DEFAULT 0', 'whitelist_mode':'INTEGER DEFAULT 0',
                    'target_goal':'INTEGER DEFAULT 4', 'auto_sound':"TEXT DEFAULT 'none'",
                    'auto_sound_volume':'REAL DEFAULT 0.5', 'lists_initialized':'INTEGER DEFAULT 0'},
                'blocked_items': {'mode_id':'INTEGER'},
                'focus_sessions': {'elapsed_seconds':'REAL', 'outcome':"TEXT DEFAULT ''", 'mode_name':"TEXT DEFAULT ''"}}
            for table, fields in additions.items():
                present = {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
                for field, definition in fields.items():
                    if field not in present:
                        conn.execute(f'ALTER TABLE {table} ADD COLUMN {field} {definition}')
            if not conn.execute('SELECT 1 FROM focus_modes WHERE is_default=1').fetchone():
                conn.execute("""INSERT INTO focus_modes(name,is_default,blocked_sites,blocked_apps)
                    VALUES ('Default',1,?,?)""", (json.dumps(DEFAULT_BLOCKED_SITES), json.dumps(DEFAULT_BLOCKED_APPS)))
            active = conn.execute('SELECT id FROM focus_modes WHERE name=?', (active_mode_name,)).fetchone()
            self.active_mode_id = active['id'] if active else conn.execute('SELECT id FROM focus_modes WHERE is_default=1').fetchone()['id']
            unassigned = conn.execute('SELECT 1 FROM blocked_items WHERE mode_id IS NULL').fetchone()
            if unassigned:
                conn.execute('UPDATE blocked_items SET mode_id=? WHERE mode_id IS NULL', (self.active_mode_id,))
                self._sync_lists(conn, self.active_mode_id)
                conn.execute('UPDATE focus_modes SET lists_initialized=1 WHERE id=?', (self.active_mode_id,))
            elif legacy and not conn.execute('SELECT 1 FROM blocked_items').fetchone():
                # An intentionally empty legacy list is not a request to restore defaults.
                conn.execute("UPDATE focus_modes SET lists_initialized=1,blocked_sites='[]',blocked_apps='[]' WHERE id=?", (self.active_mode_id,))
            conn.execute("UPDATE focus_sessions SET outcome=CASE WHEN completed=1 THEN 'completed' ELSE 'stopped' END WHERE outcome='' OR outcome IS NULL")
            conn.execute('CREATE INDEX IF NOT EXISTS idx_items_mode ON blocked_items(mode_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_start ON focus_sessions(start_time)')
            conn.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
        self.set_active_mode(self.active_mode_id)

    def set_active_mode(self, mode_id):
        with self.connection() as conn:
            mode = conn.execute('SELECT * FROM focus_modes WHERE id=?', (mode_id,)).fetchone()
            if mode is None:
                raise ValueError('This mode no longer exists.')
            if not mode['lists_initialized']:
                self._replace_lists(conn, mode_id, json.loads(mode['blocked_sites']), json.loads(mode['blocked_apps']))
        self.active_mode_id = mode_id

    @staticmethod
    def _sync_lists(conn, mode_id):
        rows = list(conn.execute('SELECT item_type,value FROM blocked_items WHERE mode_id=? ORDER BY id', (mode_id,)))
        conn.execute('UPDATE focus_modes SET blocked_sites=?,blocked_apps=? WHERE id=?',
            (json.dumps([r['value'] for r in rows if r['item_type']=='website']),
             json.dumps([r['value'] for r in rows if r['item_type']=='app']), mode_id))

    @staticmethod
    def _replace_lists(conn, mode_id, sites, apps):
        old = {(r['item_type'], r['value'].casefold()):r['enabled'] for r in conn.execute('SELECT * FROM blocked_items WHERE mode_id=?', (mode_id,))}
        conn.execute('DELETE FROM blocked_items WHERE mode_id=?', (mode_id,))
        for kind, values in (('website',sites),('app',apps)):
            for value in values:
                conn.execute('INSERT INTO blocked_items(name,item_type,value,enabled,mode_id) VALUES (?,?,?,?,?)',
                             (value,kind,value,old.get((kind,value.casefold()),1),mode_id))
        conn.execute('UPDATE focus_modes SET lists_initialized=1 WHERE id=?', (mode_id,))
        DatabaseManager._sync_lists(conn,mode_id)

    def get_blocked_items(self, item_type=None):
        with self.connection() as conn:
            sql = 'SELECT * FROM blocked_items WHERE mode_id=?'
            args = [self.active_mode_id]
            if item_type:
                sql += ' AND item_type=?'
                args.append(item_type)
            return [BlockedItem(id=r['id'],name=r['name'],item_type=r['item_type'],value=r['value'],enabled=bool(r['enabled']))
                    for r in conn.execute(sql+' ORDER BY id',args)]

    def add_blocked_item(self,item):
        item.value = blocklist([item.value],item.item_type)[0]
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            existing = conn.execute('SELECT id FROM blocked_items WHERE mode_id=? AND item_type=? AND lower(value)=lower(?)',
                                    (self.active_mode_id,item.item_type,item.value)).fetchone()
            if existing:
                return existing['id']
            ident = conn.execute('INSERT INTO blocked_items(name,item_type,value,enabled,mode_id) VALUES (?,?,?,?,?)',
                (item.value,item.item_type,item.value,int(item.enabled),self.active_mode_id)).lastrowid
            self._sync_lists(conn,self.active_mode_id)
            return ident

    def update_blocked_item(self,item):
        item.value = blocklist([item.value],item.item_type)[0]
        with self.connection() as conn:
            conn.execute('UPDATE blocked_items SET name=?,item_type=?,value=?,enabled=? WHERE id=? AND mode_id=?',
                (item.value,item.item_type,item.value,int(item.enabled),item.id,self.active_mode_id))
            self._sync_lists(conn,self.active_mode_id)

    def delete_blocked_item(self,item_id):
        with self.connection() as conn:
            conn.execute('DELETE FROM blocked_items WHERE id=? AND mode_id=?',(item_id,self.active_mode_id))
            self._sync_lists(conn,self.active_mode_id)

    def toggle_blocked_item(self,item_id,enabled):
        with self.connection() as conn:
            conn.execute('UPDATE blocked_items SET enabled=? WHERE id=? AND mode_id=?',(int(enabled),item_id,self.active_mode_id))

    @staticmethod
    def _row_to_mode(row):
        fields = FocusMode.__dataclass_fields__
        values = {k:row[k] for k in fields if k in row.keys()}
        for key in ('dead_lock','notifications','is_default','auto_flow','whitelist_mode'):
            if key in values: values[key] = bool(values[key])
        return FocusMode(**values)

    def get_all_modes(self):
        with self.connection() as conn:
            return [self._row_to_mode(r) for r in conn.execute('SELECT * FROM focus_modes ORDER BY is_default DESC,name')]

    def get_mode_by_name(self,name):
        with self.connection() as conn:
            row=conn.execute('SELECT * FROM focus_modes WHERE name=? COLLATE NOCASE',(name,)).fetchone()
            return self._row_to_mode(row) if row else None

    def get_mode(self,mode_id):
        with self.connection() as conn:
            row=conn.execute('SELECT * FROM focus_modes WHERE id=?',(mode_id,)).fetchone()
            return self._row_to_mode(row) if row else None

    def _write_mode(self,mode,create):
        validate_mode(mode)
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT 1 FROM focus_modes WHERE lower(name)=lower(?) AND id!=?',(mode.name,mode.id or -1)).fetchone():
                raise ValueError('A mode with that name already exists. Choose another name.')
            keys=[k for k in FocusMode.__dataclass_fields__ if k not in ('id','is_default')]
            vals=[int(getattr(mode,k)) if isinstance(getattr(mode,k),bool) else getattr(mode,k) for k in keys]
            if create:
                ident=conn.execute(f"INSERT INTO focus_modes ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",vals).lastrowid
            else:
                ident=mode.id
                conn.execute('UPDATE focus_modes SET '+','.join(k+'=?' for k in keys)+' WHERE id=? AND is_default=0',vals+[ident])
            self._replace_lists(conn,ident,json.loads(mode.blocked_sites),json.loads(mode.blocked_apps))
            return ident

    def save_mode(self,mode):
        return self._write_mode(mode,True)

    def update_mode(self,mode):
        if mode.id and not mode.is_default:
            self._write_mode(mode,False)

    def delete_mode(self,mode_id):
        with self.connection() as conn:
            if conn.execute('SELECT 1 FROM focus_modes WHERE id=? AND is_default=1',(mode_id,)).fetchone(): return
            conn.execute('DELETE FROM blocked_items WHERE mode_id=?',(mode_id,))
            conn.execute('DELETE FROM focus_modes WHERE id=?',(mode_id,))

    def update_mode_blocked_items(self,mode_id,sites,apps):
        sites=blocklist(json.loads(sites),'website')
        apps=blocklist(json.loads(apps),'app')
        with self.connection() as conn:
            self._replace_lists(conn,mode_id,sites,apps)

    def get_all_custom_sounds(self):
        with self.connection() as conn:
            return [CustomSound(**dict(r)) for r in conn.execute('SELECT * FROM custom_sounds ORDER BY name')]

    def save_custom_sound(self,sound):
        with self.connection() as conn:
            return conn.execute('INSERT INTO custom_sounds(name,icon,file_path) VALUES (?,?,?)',(sound.name,sound.icon,sound.file_path)).lastrowid

    def update_custom_sound(self,sound):
        if not sound.name.strip(): raise ValueError('Sound name is required.')
        try:
            with self.connection() as conn:
                conn.execute('UPDATE custom_sounds SET name=?,icon=?,file_path=? WHERE id=?',(sound.name.strip(),sound.icon,sound.file_path,sound.id))
        except sqlite3.IntegrityError:
            raise ValueError('A sound with that name already exists.') from None

    def delete_custom_sound(self,sound_id):
        with self.connection() as conn:
            conn.execute("UPDATE focus_modes SET auto_sound='none' WHERE auto_sound=?",(f'custom_{sound_id}',))
            conn.execute('DELETE FROM custom_sounds WHERE id=?',(sound_id,))

    def save_session(self,session):
        with self.connection() as conn:
            return conn.execute('INSERT INTO focus_sessions(start_time,end_time,duration_minutes,completed,session_type,elapsed_seconds,outcome,mode_name)\n                VALUES (?,?,?,?,?,?,?,?)',(session.start_time.isoformat() if session.start_time else None,
                session.end_time.isoformat() if session.end_time else None,session.duration_minutes,int(session.completed),session.session_type,
                session.elapsed_seconds,session.outcome or ('completed' if session.completed else 'stopped'),session.mode_name)).lastrowid

    @staticmethod
    def _session(row):
        return FocusSession(id=row['id'],start_time=datetime.fromisoformat(row['start_time']) if row['start_time'] else None,
            end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,duration_minutes=row['duration_minutes'],
            completed=bool(row['completed']),session_type=row['session_type'],elapsed_seconds=row['elapsed_seconds'],
            outcome=row['outcome'],mode_name=row['mode_name'])

    def get_sessions(self,limit=50,offset=0,outcome='all'):
        with self.connection() as conn:
            where='' if outcome=='all' else ' WHERE outcome=?'
            args=[] if outcome=='all' else [outcome]
            return [self._session(r) for r in conn.execute('SELECT * FROM focus_sessions'+where+' ORDER BY start_time DESC,id DESC LIMIT ? OFFSET ?',args+[limit,offset])]

    def get_sessions_by_date(self,date_str):
        with self.connection() as conn:
            return [self._session(r) for r in conn.execute('SELECT * FROM focus_sessions WHERE date(start_time)=? ORDER BY start_time',(date_str,))]

    def get_today_sessions(self):
        return self.get_sessions_by_date(datetime.now().date().isoformat())

    def _day_stats(self,date):
        stats=DailyStats(date=date)
        for session in self.get_sessions_by_date(date):
            if session.session_type!='focus': continue
            stats.total_sessions+=1
            stats.completed_sessions+=int(session.completed)
            stats.total_focus_minutes+=(session.elapsed_seconds if session.elapsed_seconds is not None else
                                        (session.duration_minutes*60 if session.completed else 0))/60
        return stats

    def get_today_stats(self):
        return self._day_stats(datetime.now().date().isoformat())

    def _get_stats_for_days(self,days):
        today=datetime.now().date()
        return [self._day_stats((today-timedelta(days=i)).isoformat()) for i in reversed(range(days))]

    def get_weekly_stats(self): return self._get_stats_for_days(7)
    def get_monthly_stats(self): return self._get_stats_for_days(30)

    def get_total_focus_hours(self):
        with self.connection() as conn:
            return conn.execute("SELECT COALESCE(SUM(COALESCE(elapsed_seconds,CASE WHEN completed=1 THEN duration_minutes*60 ELSE 0 END)),0)/3600.0 FROM focus_sessions WHERE session_type='focus'").fetchone()[0]

    def get_streak(self):
        with self.connection() as conn:
            dates={r[0] for r in conn.execute("SELECT DISTINCT date(start_time) FROM focus_sessions WHERE completed=1 AND session_type='focus'")}
        day=datetime.now().date()
        if day.isoformat() not in dates: day-=timedelta(days=1)
        streak=0
        while day.isoformat() in dates:
            streak+=1
            day-=timedelta(days=1)
        return streak
