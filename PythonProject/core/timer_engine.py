"""Pomodoro state machine advanced by the application's UI clock."""
import math
import logging
import time
from datetime import datetime
from utils.constants import TimerState
from data.models import FocusSession


class TimerEngine:
    def __init__(self, db=None):
        self.db = db
        self.state = TimerState.IDLE
        self.remaining_seconds = self.session_count = self.total_completed_today = 0
        self.focus_duration, self.short_break_duration, self.long_break_duration = 25, 5, 15
        self.sessions_before_long_break = 4
        self.auto_flow, self.target_goal = False, 4
        self._state_before_pause = self._deadline = self._session_started = None
        self.mode_name = "Default"
        self._focus_elapsed = 0.0
        self._focus_segment = None
        self.on_tick = self.on_state_change = self.on_session_complete = self.on_break_end = None

    @staticmethod
    def _notify(callback, *args):
        if callback is not None:
            try:
                callback(*args)
            except Exception:
                # A failed UI refresh must not leave an expired focus phase
                # active, or save the same completion again on every tick.
                logging.getLogger(__name__).exception('Timer callback failed')

    def _begin(self, state, minutes):
        self.state = state
        self.remaining_seconds = minutes * 60
        self._deadline = time.monotonic() + self.remaining_seconds
        self._state_before_pause = None
        if state == TimerState.FOCUSING:
            self._session_started = datetime.now()
            self._focus_elapsed = 0.0
            self._focus_segment = time.monotonic()
        self._notify(self.on_state_change, state)
        self._notify(self.on_tick, self.remaining_seconds)

    def start_focus(self):
        if self.state in (TimerState.IDLE, TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
            self._begin(TimerState.FOCUSING, self.focus_duration)

    def start_break(self, break_type):
        is_long = break_type == 'long_break'
        self._begin(TimerState.LONG_BREAK if is_long else TimerState.SHORT_BREAK,
                    self.long_break_duration if is_long else self.short_break_duration)

    def tick(self):
        if self.state in (TimerState.IDLE, TimerState.PAUSED):
            return
        remaining = max(0, math.ceil(self._deadline - time.monotonic()))
        if remaining != self.remaining_seconds:
            self.remaining_seconds = remaining
            self._notify(self.on_tick, remaining)
        if remaining:
            return
        if self.state == TimerState.FOCUSING:
            session = None
            try:
                session = self._save_session(True)
            finally:
                # A full/unwritable disk must not keep an expired focus phase
                # (and its OS blockers) active or retry it every clock tick.
                self.session_count += 1
                if session is not None:
                    self._notify(self.on_session_complete, session)
                self.start_break('long_break' if self.session_count % self.sessions_before_long_break == 0 else 'short_break')
        else:
            self._idle()
            self._notify(self.on_break_end)
            if self.auto_flow and (not self.target_goal or self.session_count < self.target_goal):
                self.start_focus()

    def _save_session(self, completed, outcome=None):
        elapsed = self._focus_elapsed
        if self._focus_segment is not None:
            elapsed += max(0, time.monotonic()-self._focus_segment)
        elapsed = min(self.focus_duration * 60, elapsed)
        session = FocusSession(start_time=self._session_started or datetime.now(),
                               end_time=datetime.now(), duration_minutes=self.focus_duration,
                               completed=completed, session_type='focus', elapsed_seconds=elapsed,
                               outcome=outcome or ('completed' if completed else 'stopped'), mode_name=self.mode_name)
        if self.db:
            self.db.save_session(session)
        return session

    def pause(self):
        if self.state not in (TimerState.IDLE, TimerState.PAUSED):
            self.tick()
            if self.state == TimerState.IDLE:
                return
            if self.state == TimerState.FOCUSING and self._focus_segment is not None:
                self._focus_elapsed += max(0, time.monotonic()-self._focus_segment)
                self._focus_segment = None
            self._state_before_pause = self.state
            self._paused_remaining = max(0, self._deadline - time.monotonic())
            self.state = TimerState.PAUSED
            self._notify(self.on_state_change, self.state)

    def resume(self):
        if self.state == TimerState.PAUSED:
            self.state = self._state_before_pause
            self._deadline = time.monotonic() + self._paused_remaining
            if self.state == TimerState.FOCUSING:
                self._focus_segment = time.monotonic()
            self._notify(self.on_state_change, self.state)

    def _idle(self):
        self.state = TimerState.IDLE
        self.remaining_seconds = 0
        self._deadline = None
        self._notify(self.on_state_change, self.state)
        self._notify(self.on_tick, 0)

    def stop(self):
        effective = self._state_before_pause if self.state == TimerState.PAUSED else self.state
        try:
            if effective == TimerState.FOCUSING:
                self._save_session(False)
        finally:
            self._idle()

    def skip(self):
        effective = self._state_before_pause if self.state == TimerState.PAUSED else self.state
        if effective == TimerState.FOCUSING:
            try:
                self._save_session(False, 'skipped')
            finally:
                self.start_break('short_break')
        elif effective in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
            self._idle()
            self._notify(self.on_break_end)

    def reset(self):
        self.stop()
        self.session_count = 0

    @staticmethod
    def _format_time(seconds):
        mins, secs = divmod(max(0, int(seconds)), 60)
        return f'{mins:02d}:{secs:02d}'

    def update_durations(self, focus_min, short_break_min, long_break_min, sessions=4, auto_flow=False, target_goal=4):
        values = (focus_min, short_break_min, long_break_min, sessions)
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in values):
            raise ValueError('Durations and sessions must be positive integers.')
        if self.state != TimerState.IDLE:
            raise ValueError('Stop the current timer before changing modes.')
        self.focus_duration, self.short_break_duration, self.long_break_duration = values[:3]
        self.sessions_before_long_break = sessions
        self.auto_flow, self.target_goal = auto_flow, max(0, int(target_goal))
