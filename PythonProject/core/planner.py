"""Persistent day plans; reminders never start timers or blocking automatically."""
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
import json


@dataclass
class PlanTask:
    id: int | None = None
    title: str = ''
    day: str = field(default_factory=lambda: date.today().isoformat())
    start_time: str = ''
    minutes: int = 25
    priority: str = 'Normal'
    notes: str = ''
    checklist: list = field(default_factory=list)
    mode_id: int | None = None
    completed: bool = False
    reminder: bool = True
    reminded_at: str = ''
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


def validate_task(task):
    task.title = task.title.strip()
    if not 1 <= len(task.title) <= 160:
        raise ValueError('Give your task a title of 1–160 characters.')
    try:
        task.day = date.fromisoformat(task.day).isoformat()
    except (ValueError, TypeError):
        raise ValueError('Use a valid date in YYYY-MM-DD format.') from None
    task.start_time = task.start_time.strip()
    if task.start_time:
        try:
            task.start_time = datetime.strptime(task.start_time, '%H:%M').strftime('%H:%M')
        except ValueError:
            raise ValueError('Use a valid 24-hour time, such as 09:30, or leave it empty.') from None
    if isinstance(task.minutes, bool) or not isinstance(task.minutes, int) or not 1 <= task.minutes <= 720:
        raise ValueError('Estimated time must be between 1 and 720 minutes.')
    if task.priority not in ('Low', 'Normal', 'High'):
        raise ValueError('Choose Low, Normal or High priority.')
    if not isinstance(task.notes, str) or len(task.notes) > 10000:
        raise ValueError('Keep notes within 10,000 characters.')
    if not isinstance(task.checklist, list) or len(task.checklist) > 50:
        raise ValueError('A task can contain up to 50 checklist steps.')
    clean = []
    for step in task.checklist:
        if not isinstance(step, dict) or not isinstance(step.get('text'), str):
            raise ValueError('Each checklist step needs a description.')
        text = step['text'].strip()
        if not 1 <= len(text) <= 200:
            raise ValueError('Keep each checklist step within 200 characters.')
        clean.append({'text': text, 'done': bool(step.get('done', False))})
    task.checklist = clean
    return task


class PlannerStore:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _task(row):
        values = dict(row)
        values['checklist'] = json.loads(values['checklist'])
        for key in ('completed', 'reminder'):
            values[key] = bool(values[key])
        return PlanTask(**values)

    def get(self, ident):
        with self.db.connection() as conn:
            row = conn.execute('SELECT * FROM planner_tasks WHERE id=?', (ident,)).fetchone()
        return self._task(row) if row else None

    def list(self, start, end=None):
        with self.db.connection() as conn:
            rows = conn.execute("""SELECT * FROM planner_tasks WHERE day BETWEEN ? AND ?
                ORDER BY day,completed,CASE WHEN start_time='' THEN 1 ELSE 0 END,start_time,
                CASE priority WHEN 'High' THEN 0 WHEN 'Normal' THEN 1 ELSE 2 END,id""", (start,end or start)).fetchall()
        return [self._task(row) for row in rows]

    def save(self, task):
        task = validate_task(task)
        with self.db.connection() as conn:
            if task.mode_id is not None and not conn.execute('SELECT 1 FROM focus_modes WHERE id=?', (task.mode_id,)).fetchone():
                raise ValueError('That Focus Mode was removed. Choose another mode.')
            old = conn.execute('SELECT * FROM planner_tasks WHERE id=?', (task.id,)).fetchone() if task.id else None
            if task.id and old is None:
                raise ValueError('This task no longer exists.')
            if old and (old['day'],old['start_time'],old['reminder']) != (task.day,task.start_time,int(task.reminder)):
                task.reminded_at = ''
            values = asdict(task)
            values.pop('id')
            values['checklist'] = json.dumps(task.checklist)
            if old:
                conn.execute('UPDATE planner_tasks SET '+','.join(f'{key}=?' for key in values)+' WHERE id=?', (*values.values(),task.id))
            else:
                task.id = conn.execute('INSERT INTO planner_tasks ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')', tuple(values.values())).lastrowid
        return task.id

    def complete(self, ident, completed):
        with self.db.connection() as conn:
            conn.execute('UPDATE planner_tasks SET completed=? WHERE id=?', (bool(completed),ident))

    def step(self, ident, index, completed):
        # Read and write in the same transaction to preserve other step edits.
        with self.db.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT checklist FROM planner_tasks WHERE id=?', (ident,)).fetchone()
            if not row: return
            steps = json.loads(row['checklist'])
            if not 0 <= index < len(steps): return
            steps[index]['done'] = bool(completed)
            conn.execute('UPDATE planner_tasks SET checklist=? WHERE id=?', (json.dumps(steps),ident))

    def delete(self, ident):
        with self.db.connection() as conn:
            conn.execute('DELETE FROM planner_tasks WHERE id=?', (ident,))

    def due(self, now=None):
        now = now or datetime.now()
        # Only today's tasks, once per scheduled time. No stale notification flood.
        with self.db.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            rows = conn.execute("""SELECT * FROM planner_tasks WHERE day=? AND start_time<>''
                AND start_time<=? AND completed=0 AND reminder=1 AND reminded_at=''
                ORDER BY start_time,id""", (now.date().isoformat(), now.strftime('%H:%M'))).fetchall()
            if rows:
                conn.executemany('UPDATE planner_tasks SET reminded_at=? WHERE id=?',
                    [(now.isoformat(),row['id']) for row in rows])
        return [self._task(row) for row in rows]

    @staticmethod
    def conflicts(tasks):
        """Find overlapping scheduled tasks without rejecting intentional overlaps."""
        scheduled = [t for t in tasks if t.start_time and not t.completed]
        overlaps = set()
        for i, left in enumerate(scheduled):
            start = datetime.fromisoformat(f'{left.day}T{left.start_time}')
            end = start + timedelta(minutes=left.minutes)
            for right in scheduled[i+1:]:
                other = datetime.fromisoformat(f'{right.day}T{right.start_time}')
                if start < other+timedelta(minutes=right.minutes) and other < end:
                    overlaps.update((left.id,right.id))
        return overlaps
