from ui.metrics import (
    CONTROL_FONT_SIZE, LARGE_CONTROL_HEIGHT, PAGE_TITLE_SIZE, PRIMARY_CONTROL_HEIGHT, PRIMARY_FONT_SIZE
)
from ui.dropdown import FocusDropdown
from ui.design import MaterialFrame
from ui.design import MaterialButton
import customtkinter as ctk
from utils.constants import BG_PRIMARY, BG_CARD, ACCENT_FOCUS, ACCENT_BREAK, ACCENT_DANGER, TimerState, INPUT_BG, INPUT_BTN_COLOR, INPUT_BTN_HOVER, TEXT_SECONDARY, HOVER_BG, TEXT_PRIMARY, ACCENT_HOVER_DARK, SEPARATOR_COLOR, ICE
from core.timer_engine import TimerEngine
from core.health_reminder import HealthReminder
from data.models import FocusSession
from ui.widgets import CircularProgressBar

class TimerView(ctk.CTkFrame):
    """
    Main Pomodoro timer interface.
    """
    def __init__(self, parent, timer_engine: TimerEngine, health_reminder: HealthReminder):
        super().__init__(parent, fg_color=BG_PRIMARY)
        self.timer_engine, self.health_reminder = timer_engine, health_reminder
        self.on_mode_selected = None
        self._planned_task = ''
        self._compact = False
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=28, pady=(22, 16))
        self.title_label = ctk.CTkLabel(self.header_frame, text="Focus Timer", font=("Inter", PAGE_TITLE_SIZE, "bold"), text_color=TEXT_PRIMARY)
        self.title_label.pack(side="left")
        self.mode_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.mode_frame.pack(side="right")
        self.mode_var = ctk.StringVar(value="Default")
        self.mode_dropdown = FocusDropdown(self.mode_frame, values=["Default"], variable=self.mode_var,
            command=self._on_mode_changed, fg_color=BG_CARD, button_color=BG_CARD,
            button_hover_color=HOVER_BG, text_color=TEXT_PRIMARY, font=("Inter", 13),
            width=170, height=40, corner_radius=10)
        self.mode_dropdown.pack(side="left", padx=(0, 10))
        self.mini_btn = MaterialButton(self.header_frame, text="Mini", width=54, height=LARGE_CONTROL_HEIGHT,
            fg_color=BG_CARD, hover_color=HOVER_BG, text_color=TEXT_SECONDARY,
            border_width=1, border_color=SEPARATOR_COLOR, command=self._toggle_mini_player, font=("Inter", CONTROL_FONT_SIZE))
        self.mini_btn.pack(side="right", padx=(10, 0))

        self.insights_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.insights_frame.pack(side="bottom", fill="x", padx=28, pady=(0, 24))
        self.insights_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="insights")
        self.summary_values = []
        for i, (label, value) in enumerate((("FOCUS BLOCK", "25 min"), ("SHORT BREAK", "5 min"), ("COMPLETED TODAY", "0"))):
            card = MaterialFrame(self.insights_frame, fg_color=BG_CARD, corner_radius=12,
                                border_width=1, border_color=SEPARATOR_COLOR)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i==0 else 6, 0 if i==2 else 6))
            ctk.CTkLabel(card, text=label, font=("Inter", 10, "bold"), text_color=TEXT_SECONDARY).pack(anchor="w", padx=18, pady=(13, 0))
            number = ctk.CTkLabel(card, text=value, font=("Inter", 23, "bold"), text_color=TEXT_PRIMARY)
            number.pack(anchor="w", padx=18, pady=(0, 12))
            self.summary_values.append(number)

        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(side="bottom", pady=(8, 20))
        buttons = [("Start focus", self._start_focus), ("Pause", self._pause_resume),
                   ("Stop", self._stop), ("Skip", self._skip)]
        controls = []
        for i, (text, command) in enumerate(buttons):
            button = MaterialButton(self.bottom_frame, text=text, command=command, width=156 if i==0 else 114,
                height=PRIMARY_CONTROL_HEIGHT, corner_radius=10, font=("Inter", PRIMARY_FONT_SIZE, "bold"),
                fg_color=ACCENT_FOCUS if i==0 else BG_CARD,
                hover_color=ACCENT_HOVER_DARK if i==0 else HOVER_BG,
                text_color="#FFFFFF" if i==0 else TEXT_PRIMARY,
                border_width=0 if i==0 else 1, border_color=SEPARATOR_COLOR)
            controls.append(button)
        self.start_btn, self.pause_btn, self.stop_btn, self.skip_btn = controls
        self.start_btn.pack(side="left", padx=6)

        self.center_frame = MaterialFrame(self, fg_color=BG_CARD, corner_radius=16,
                                       border_width=1, border_color=SEPARATOR_COLOR)
        self.center_frame.pack(fill="both", expand=True, padx=28, pady=(0, 10))
        self.hero_copy = ctk.CTkFrame(self.center_frame, fg_color="transparent", width=275, height=265)
        self.hero_copy.pack_propagate(False)
        self.hero_copy.place(relx=0.055, rely=0.5, anchor="w")
        self.phase_label = ctk.CTkLabel(self.hero_copy, text="BUILT FOR DEEP WORK", font=("Inter", 10, "bold"), text_color=ICE)
        self.phase_label.pack(anchor="w", pady=(6, 14))
        self.hero_title = ctk.CTkLabel(self.hero_copy, text="One session.\nFull attention.",
            justify="left", anchor="w", wraplength=260, font=("Inter", 30, "bold"), text_color=TEXT_PRIMARY)
        self.hero_title.pack(anchor="w")
        self.hero_description = ctk.CTkLabel(self.hero_copy, text="Clear the noise. Choose one task.\nGive it your full attention.", wraplength=260,
            justify="left", font=("Inter", 14), text_color=TEXT_SECONDARY)
        self.hero_description.pack(anchor="w", pady=(12, 16))
        self.session_label = ctk.CTkLabel(self.hero_copy, text="0 / 4 sessions completed",
            font=("Inter", 12), text_color=ICE)
        self.session_label.pack(anchor="w")
        self.tip_label = ctk.CTkLabel(self.hero_copy, text="", justify="left", wraplength=260,
                                     font=("Inter", 11), text_color=TEXT_SECONDARY)
        self.tip_label.pack(anchor="w", pady=(8, 0))
        self.progress_circle = CircularProgressBar(self.center_frame, size=292, width=6, bg_color=BG_CARD)
        self.progress_circle.place(relx=0.75, rely=0.5, anchor="center")
        self.bind("<Configure>", self._layout_hero)
        self.center_frame.bind("<Configure>", self._layout_hero)
        self.timer_engine.on_tick = self._on_tick_callback
        self.timer_engine.on_state_change = self._on_state_change_callback
        self.timer_engine.on_session_complete = self._on_session_complete_callback
        self.timer_engine.on_break_end = self._on_break_end_callback
        self._update_session_label()
        self.refresh_summary()

    def refresh_summary(self):
        self.summary_values[0].configure(text=f"{self.timer_engine.focus_duration} min")
        self.summary_values[1].configure(text=f"{self.timer_engine.short_break_duration} min")
        db = self.timer_engine.db
        self.summary_values[2].configure(text=str(db.get_today_stats().completed_sessions if db else 0))

    def _layout_hero(self, event=None):
        narrow = self.center_frame.winfo_width() < 740
        if getattr(self, '_narrow_hero', None) != narrow:
            self._narrow_hero = narrow
            self.hero_copy.configure(width=200 if narrow else 275, height=240 if narrow else 265)
            self.hero_title.configure(font=("Inter", 24 if narrow else 30, "bold"), wraplength=190 if narrow else 260)
            self.hero_description.configure(font=("Inter", 12 if narrow else 14), wraplength=190 if narrow else 270)
            self.tip_label.configure(wraplength=190 if narrow else 260)
        position=(self._compact,narrow)
        if getattr(self,'_hero_position',None)!=position:
            self._hero_position=position
            if self._compact:
                self.hero_copy.place_forget()
                self.progress_circle.place(relx=0.5,rely=0.5,anchor='center')
            else:
                self.hero_copy.place(relx=0.055,rely=0.5,anchor='w')
                self.progress_circle.place(relx=0.78 if narrow else 0.76,rely=0.5,anchor='center')
        if self._compact:
            size = 228
        else:
            size = min(236 if narrow else 292, max(220, int(self.center_frame.winfo_width()*0.40)), max(220, self.center_frame.winfo_height()-30))
        if self.progress_circle.size != size:
            self.progress_circle.size = size
            self.progress_circle.configure(width=size, height=size)
            self.progress_circle._draw()
        show_insights = not self._compact and self.winfo_height() >= 585
        if show_insights and not self.insights_frame.winfo_manager():
            self.insights_frame.pack(side="bottom", fill="x", padx=28, pady=(0, 24), before=self.bottom_frame)
        elif not show_insights and self.insights_frame.winfo_manager():
            self.insights_frame.pack_forget()

    def set_compact(self, compact):
        self._compact = compact
        if compact:
            self.mode_frame.pack_forget()
            self.title_label.configure(text="Focus", font=("Inter", 20, "bold"))
            self.header_frame.pack_configure(padx=18, pady=(12, 8))
            self.center_frame.pack_configure(padx=18)
            self.bottom_frame.pack_configure(pady=(8, 16))
            self.mini_btn.configure(text="Expand")
        else:
            self.mode_frame.pack(side="right", before=self.mini_btn)
            self.title_label.configure(text="Focus Timer", font=("Inter", PAGE_TITLE_SIZE, "bold"))
            self.header_frame.pack_configure(padx=28, pady=(22, 16))
            self.center_frame.pack_configure(padx=28)
            self.bottom_frame.pack_configure(pady=(8, 20))
            self.mini_btn.configure(text="Mini")
        for button in (self.start_btn, self.pause_btn, self.stop_btn, self.skip_btn):
            button.configure(width=86 if compact else 114)
        self._layout_hero()

    def _add_hover(self, btn, default_color, hover_color):
        def on_enter(e):
            btn.configure(fg_color=hover_color)
        def on_leave(e):
            btn.configure(fg_color=default_color)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    def _on_mode_changed(self, new_mode: str):
        if hasattr(self, 'on_mode_selected') and self.on_mode_selected:
            self.on_mode_selected(new_mode)

    def _update_session_label(self):
        count = self.timer_engine.session_count
        total = getattr(self.timer_engine, 'sessions_before_long_break', 4)
        text=f"{count} / {total} sessions completed"
        if self.session_label.cget('text')!=text: self.session_label.configure(text=text)

    def _on_tick_callback(self, remaining: int):
        self._on_tick(remaining)

    def _on_tick(self, remaining: int):
        total = self.timer_engine.focus_duration * 60
        if hasattr(self.timer_engine, 'state'):
            state = self.timer_engine.state
            effective = self.timer_engine._state_before_pause if state == TimerState.PAUSED else state
            if effective == TimerState.FOCUSING:
                total = self.timer_engine.focus_duration * 60
            elif effective == TimerState.SHORT_BREAK:
                total = self.timer_engine.short_break_duration * 60
            elif effective == TimerState.LONG_BREAK:
                total = self.timer_engine.long_break_duration * 60
        
        progress = 1.0
        if total > 0:
            progress = max(0.0, 1.0 - (remaining / total))
        
        time_str = self.timer_engine._format_time(remaining)
        
        state_str = "READY"
        if state == TimerState.FOCUSING:
            state_str = "FOCUS"
        elif state == TimerState.SHORT_BREAK:
            state_str = "SHORT BREAK"
        elif state == TimerState.LONG_BREAK:
            state_str = "LONG BREAK"
        elif state == TimerState.PAUSED:
            state_str = "PAUSED"
            
        if state == TimerState.IDLE:
            time_str = self.timer_engine._format_time(self.timer_engine.focus_duration * 60)
            progress = 1.0
            
        self.progress_circle.set_state(time_str, state_str, progress)
        self._update_session_label()
        for widget,text in zip(self.summary_values,(f'{self.timer_engine.focus_duration} min',f'{self.timer_engine.short_break_duration} min')):
            if widget.cget('text')!=text: widget.configure(text=text)

    def _on_state_change_callback(self, state: TimerState):
        self._on_state_change(state)

    def _on_state_change(self, state: TimerState):
        if state == TimerState.IDLE:
            self.set_planned_task('')
        self._update_session_label()
        
        self.start_btn.pack_forget()
        self.pause_btn.pack_forget()
        self.stop_btn.pack_forget()
        self.skip_btn.pack_forget()
        self.tip_label.configure(text="")
        copy = {
            TimerState.IDLE: ("BUILT FOR DEEP WORK", "One session.\nFull attention."),
            TimerState.FOCUSING: ("FOCUS SESSION", "Stay with it.\nYou are in flow."),
            TimerState.SHORT_BREAK: ("SHORT RECOVERY", "Step back.\nReturn fresh."),
            TimerState.LONG_BREAK: ("LONG RECOVERY", "A deeper reset.\nWell earned."),
            TimerState.PAUSED: ("SESSION PAUSED", "Take a breath.\nResume focus."),
        }
        phase, title = copy[state]
        self.phase_label.configure(text=phase)
        self.hero_title.configure(text=title)
        
        if state == TimerState.IDLE:
            self.start_btn.pack(side="left", padx=10)
            self.progress_circle.set_color(ACCENT_FOCUS)
            time_str = self.timer_engine._format_time(self.timer_engine.remaining_seconds)
            self._on_tick(0)
            
        elif state == TimerState.FOCUSING:
            self.pause_btn.configure(text="Pause")
            self.pause_btn.pack(side="left", padx=10)
            self.stop_btn.pack(side="left", padx=10)
            self.skip_btn.pack(side="left", padx=10)
            self.progress_circle.set_color(ACCENT_FOCUS)
            self._on_tick(self.timer_engine.remaining_seconds)
            
        elif state in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
            self.stop_btn.pack(side="left", padx=10)
            self.skip_btn.pack(side="left", padx=10)
            self.progress_circle.set_color(ACCENT_BREAK)
            status = "SHORT BREAK" if state == TimerState.SHORT_BREAK else "LONG BREAK"
            self._on_tick(self.timer_engine.remaining_seconds)
            
            # Show health tip
            tip = self.health_reminder.get_next_tip()
            self.tip_label.configure(text=f"💡 Tip: {tip}")
            
        elif state == TimerState.PAUSED:
            self.pause_btn.configure(text="Resume")
            self.pause_btn.pack(side="left", padx=10)
            self.stop_btn.pack(side="left", padx=10)
            self.skip_btn.pack(side="left", padx=10)
            self._on_tick(self.timer_engine.remaining_seconds)

    def _on_session_complete_callback(self, session: FocusSession):
        self._on_session_complete(session)

    def _on_session_complete(self, session: FocusSession):
        self._update_session_label()
        self.refresh_summary()
        
    def _on_break_end_callback(self):
        self._on_break_end()

    def _on_break_end(self):
        self._on_state_change(self.timer_engine.state)

    def set_planned_task(self, title):
        self._planned_task = title
        shown = title[:87]+'…' if len(title)>88 else title
        self.hero_description.configure(text='Working on: '+shown if title else
            'Clear the noise. Choose one task.\nGive it your full attention.')

    def _start_focus(self):
        app = self.winfo_toplevel()
        if not app._restoring and not app._closing:
            self.timer_engine.start_focus()

    def _pause_resume(self):
        app = self.winfo_toplevel()
        if app._restoring or app._closing:
            return
        if self.timer_engine.state == TimerState.PAUSED:
            self.timer_engine.resume()
        elif self.timer_engine.state == TimerState.IDLE:
            self.timer_engine.start_focus()
        else:
            self.timer_engine.pause()

    def _stop(self):
        self.winfo_toplevel().stop_focus()

    def _skip(self):
        self.winfo_toplevel().skip_phase()

    def _toggle_mini_player(self):
        # We need to reach the main app to toggle window state
        app = self.winfo_toplevel()
        if hasattr(app, 'toggle_mini_player'):
            app.toggle_mini_player()
