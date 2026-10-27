from ui.metrics import (
    COMPACT_CONTROL_HEIGHT, COMPACT_FONT_SIZE, HEADER_HEIGHT, NAV_COMPACT_FONT_SIZE, NAV_COMPACT_HEIGHT, NAV_FONT_SIZE, NAV_HEIGHT, SIDEBAR_COMPACT_BREAKPOINT, SIDEBAR_WIDTH
)
from ui.design import MaterialFrame
from ui.panels import fit_wrap
import queue
import os
import logging
import threading
import time
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from utils.constants import (BG_PRIMARY, BG_CARD, SIDEBAR_BG, SEPARATOR_COLOR,
                             TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT_COLOR, ICE, APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT, 
                             APP_SUITE, TimerState, load_config, save_config, update_config)
from core.timer_engine import TimerEngine
from core.shutdown_scheduler import ShutdownScheduler
from ui.shutdown_view import ShutdownView
from core.sound_engine import SoundEngine
from core.site_blocker import SiteBlocker
from core.app_blocker import AppBlocker
from core.health_reminder import HealthReminder
from data.database import DatabaseManager
from core.hotkeys import HotkeyManager

from ui.widgets import NavButton
from ui.design import load_design, brand_image, set_window_brand
from ui.timer_view import TimerView
from ui.blocker_view import BlockerView
from ui.sound_view import SoundView
from ui.stats_view import StatsView
from ui.history_view import HistoryView
from ui.planner_view import PlannerView
from ui.customizer_view import CustomizerView
from ui.settings_view import SettingsView

class DeepFocusApp(ctk.CTk):
    def _update_dimensions_event(self,event=None):
        # Toplevel bindings also receive Configure events from descendants.
        # A label/card resize does not change the dimensions of the root window.
        if event is not None and event.widget is not self: return
        return super()._update_dimensions_event(event)

    def __init__(self, instance_guard=None):
        # Apply the saved palette and CTk compatibility fixes before creating
        # any native window. CTk's constructor can otherwise paint its default
        # dark surface (and pump Windows events) before the saved light theme.
        config = load_config()
        theme = config.get('theme','dark')
        if theme not in ('light','dark','system'): theme='dark'
        load_design()
        ctk.set_appearance_mode(theme)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('SpertuloUtility.Focus')
        except (AttributeError, OSError):
            pass
        super().__init__(fg_color=BG_PRIMARY)
        self.withdraw()
        self.config = config
        self.instance_guard = instance_guard
        self._ready_shown = False
            
        self.title(APP_NAME)
        set_window_brand(self)
        width = min(WINDOW_WIDTH, max(900, self.winfo_screenwidth() - 80))
        height = min(WINDOW_HEIGHT, max(600, self.winfo_screenheight() - 120))
        self.geometry(f"{width}x{height}+40+20")
        self.minsize(900, 600)
        self.configure(fg_color=BG_PRIMARY)
        
        # Keep an opaque client surface. Mica/translucent composition can expose
        # unpainted black child rectangles during startup and Windows restores.
        
        # Init core components
        from core.work import BackgroundWork
        from core.blocking import BlockingCoordinator
        self.testing = os.environ.get('DEEPFOCUS_TESTING') == '1'
        self._closing = self._restoring = self._destroyed = self._data_busy = False
        self._audio_generation = 0
        self._audio_suspended = False
        self._auto_sound_owned = None
        self._previous_state = TimerState.IDLE
        self.work = BackgroundWork(report=self.report_error)
        self.db = DatabaseManager(active_mode_name=self.config.get('active_mode', 'Default'))
        self.timer_engine = TimerEngine(db=self.db)
        self.shutdown_scheduler = ShutdownScheduler(persist=not self.testing)
        self._ui_events = queue.SimpleQueue()
        self.sound_engine = SoundEngine()
        self.site_blocker = SiteBlocker()
        self.app_blocker = AppBlocker()
        self.blocking = BlockingCoordinator(self.site_blocker, self.app_blocker,
            lambda message: self._ui_events.put(lambda: self.report_error(message)))
        self.health_reminder = HealthReminder()
        
        # Hotkeys
        self.hotkeys = HotkeyManager()
        self.hotkeys.set_callback(lambda: self._ui_events.put(self._on_hotkey_pressed))
        if self.config.get("global_hotkeys", False):
            if not self.hotkeys.enable(self.config.get("global_hotkey_bind", "ctrl+shift+space")):
                self.config = update_config({"global_hotkeys":False})
                logging.getLogger(__name__).warning("Global shortcut unavailable at startup")
        
        # Persistent information bar and workspace navigation.
        from datetime import datetime
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.topbar = ctk.CTkFrame(self, fg_color=SIDEBAR_BG, height=HEADER_HEIGHT, corner_radius=0,
                                  border_width=1, border_color=SEPARATOR_COLOR)
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.topbar.grid_propagate(False)
        self.topbar.grid_rowconfigure(0, weight=1)
        self.topbar.grid_columnconfigure(1, weight=1)
        brand = self.header_brand = ctk.CTkFrame(self.topbar, fg_color="transparent", width=SIDEBAR_WIDTH, height=74)
        brand.grid(row=0, column=0, sticky="nsew")
        brand.grid_propagate(False)
        brand.grid_rowconfigure(0, weight=1)
        brand.grid_columnconfigure(1, weight=1)
        # Plain branding must not inherit the theme's rounded-label padding:
        # it consumes the text column and clips the title at Windows DPI scales.
        mark = ctk.CTkLabel(brand, text="", image=brand_image(46), width=46, height=46, corner_radius=0)
        mark.grid(row=0, column=0, padx=(22, 12))
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self.header_brand_title = ctk.CTkLabel(brand_text, text=APP_NAME, height=0, corner_radius=0,
            font=("Inter", 19, "bold"), text_color=TEXT_PRIMARY)
        self.header_brand_title.pack(anchor="w")
        self.header_brand_subtitle = ctk.CTkLabel(brand_text, text=APP_SUITE.upper(), height=0, corner_radius=0,
            font=("Inter", 9), text_color=TEXT_MUTED)
        self.header_brand_subtitle.pack(anchor="w", pady=(5, 0))
        route = ctk.CTkFrame(self.topbar, fg_color="transparent")
        route.grid(row=0, column=1, sticky="w", padx=24)
        ctk.CTkLabel(route, text="WORKSPACE", height=0, corner_radius=0,
            font=("Inter", 9, "bold"), text_color=TEXT_MUTED).pack(anchor="w")
        self.header_route = ctk.CTkLabel(route, text="Focus Timer", height=0, corner_radius=0,
            font=("Inter", 15, "bold"), text_color=TEXT_PRIMARY)
        self.header_route.pack(anchor="w", pady=(4, 0))
        self.header_status = ctk.CTkLabel(self.topbar, text="READY TO FOCUS", font=("Inter", 10, "bold"),
                                         text_color=ICE, fg_color=BG_CARD, corner_radius=10, width=150, height=34)
        self.header_status.grid(row=0, column=2, padx=18)
        date = ctk.CTkFrame(self.topbar, fg_color="transparent")
        date.grid(row=0, column=3, padx=(8, 26))
        ctk.CTkLabel(date, text=datetime.now().strftime("%a, %d %b").upper(), font=("Inter", 11), text_color=TEXT_SECONDARY).pack()
        self.sidebar_frame = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=SIDEBAR_BG)
        self.sidebar_frame.grid(row=1, column=0, sticky="nsew")
        self.sidebar_frame.pack_propagate(False)
        ctk.CTkLabel(self.sidebar_frame, text="WORKSPACE", font=("Inter", 10, "bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=28, pady=(26, 16))

        # --- Main Content Area ---
        # Add a subtle borderless container for the main views
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_PRIMARY)
        self.main_frame.grid(row=1, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.notice = ctk.CTkLabel(self.main_frame, text='', wraplength=620, justify='left',
            text_color=ICE, fg_color=BG_CARD, corner_radius=8, font=('Inter', 12))
        self.planner_banner = MaterialFrame(self.main_frame,fg_color=BG_CARD,corner_radius=10,
            border_width=1,border_color=SEPARATOR_COLOR)
        self.planner_banner.grid_columnconfigure(0,weight=1)
        self.planner_message = ctk.CTkLabel(self.planner_banner,text='',font=('Inter',12),
            text_color=ICE,justify='left',anchor='w',wraplength=380)
        self.planner_message.grid(row=0,column=0,sticky='ew',padx=14,pady=12)
        ctk.CTkButton(self.planner_banner,text='Open Planner',width=104,height=COMPACT_CONTROL_HEIGHT,
            command=lambda:self.show_view('planner'), font=("Inter", COMPACT_FONT_SIZE)).grid(row=0,column=1,padx=(0,8),pady=12)
        ctk.CTkButton(self.planner_banner,text='×',width=32,height=COMPACT_CONTROL_HEIGHT,
            command=self.planner_banner.pack_forget, font=("Inter", COMPACT_FONT_SIZE)).grid(row=0,column=2,padx=(0,12),pady=12)
        self.planner_banner.bind('<Configure>',lambda event:fit_wrap(self.planner_message,
            max(150,event.width-210)),add='+')
        
        try:
            from CTkToolTip import CTkToolTip
        except ImportError:
            CTkToolTip = None
            
        self.nav_buttons = {}
        nav_items = [
            ("timer", "Focus Timer", "⏱", "Start focusing with Pomodoro technique"),
            ("planner", "Planner", "", "Plan your week, schedule tasks and track checklists"),
            ("blocker", "Blocker", "🚫", "Block distracting websites and applications"),
            ("sound", "Sounds", "🔊", "Play ambient noise (Rain, White Noise, etc.)"),
            ("customizer", "Focus Modes", "🎨", "Configure Pomodoro modes and sessions"),
            ("shutdown", "Shutdown Timer", "◷", "Schedule or cancel a Windows shutdown"),
            ("stats", "Statistics", "📊", "View your productivity trends"),
            ("history", "Session History", "", "Review completed, stopped and skipped sessions"),
            ("settings", "Settings", "⚙", "Change theme and application settings"),
        ]
        for key, text, icon, tooltip_text in nav_items:
            self.nav_buttons[key] = NavButton(self.sidebar_frame, text=text, icon=key, 
                                              command=lambda k=key: self.show_view(k))
            self.nav_buttons[key].pack(fill="x", padx=16, pady=4)
            if CTkToolTip:
                CTkToolTip(self.nav_buttons[key], delay=0.5, message=tooltip_text)
        
        # Spacer
        spacer = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", height=0)
        spacer.pack(fill="both", expand=True)
        
        # Version Label
        self.version_label = ctk.CTkLabel(self.sidebar_frame, text=f"{APP_NAME}  •  v{APP_VERSION}", font=("Inter", 12), text_color=TEXT_MUTED)
        self.version_label.pack(side="bottom", pady=20)
        self._compact_nav = None
        self.sidebar_frame.bind("<Configure>",self._layout_sidebar,add="+")
        
        
        # Create views
        self.views = {
            "shutdown": ShutdownView(self.main_frame, self.shutdown_scheduler),
            "timer": TimerView(self.main_frame, self.timer_engine, self.health_reminder),
            "blocker": BlockerView(self.main_frame, self.site_blocker, self.app_blocker, self.db),
            "sound": SoundView(self.main_frame, self.sound_engine, self.db),
            "customizer": CustomizerView(self.main_frame, self.db),
            "stats": StatsView(self.main_frame, self.db),
            "history": HistoryView(self.main_frame, self.db),
            "planner": PlannerView(self.main_frame, self.db),
            "settings": SettingsView(self.main_frame, on_theme_changed=self._on_theme_changed),
        }
        
        # Wire customizer callback to sync mode dropdowns
        self.views["customizer"].on_modes_changed = self._on_modes_changed
        
        # Wire mode selection
        self.views["timer"].on_mode_selected = self._on_mode_selected
        self.views["blocker"].on_mode_selected = self._on_mode_selected
        
        # Sync mode dropdowns with current modes from DB
        self._sync_mode_dropdowns()
        
        # Apply initial active mode
        active_mode = self.config.get("active_mode", "Default")
        self._on_mode_selected(active_mode, is_initial_load=True)
        
        self._current_view = None
        self.show_view("timer")
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        from core.tray import TrayIcon
        from ui.design import BRANDING
        self.tray = TrayIcon(BRANDING / 'focus.ico', lambda action: self._ui_events.put(lambda: self._tray_action(action)))
        if not self.testing:
            self.after(250, lambda: self.run_background(self.tray.start))
            self.blocking.apply(False)
        self._last_slow_tick = 0
        self._last_planner_tick = 0
        
        # Wire up timer state changes to blockers
        self._original_on_state_change = self.timer_engine.on_state_change
        self.timer_engine.on_state_change = self._wrapped_on_state_change
        self._clock_job = self.after(100, self._poll_clock)
        self.after(50, self._show_ready)

    def _show_ready(self):
        if self._closing or self._destroyed: return
        # Finish the initial layout/paint queue once, rather than displaying
        # hundreds of child surfaces at different stages of construction.
        self.update_idletasks()
        self.deiconify()
        self._ready_shown = True

    def _layout_sidebar(self, event):
        compact = self.sidebar_frame._reverse_widget_scaling(self.winfo_height()) < SIDEBAR_COMPACT_BREAKPOINT
        if compact == self._compact_nav: return
        self._compact_nav = compact
        for button in self.nav_buttons.values():
            button.configure(height=NAV_COMPACT_HEIGHT if compact else NAV_HEIGHT)
            button.pack_configure(pady=2 if compact else 4)
            button.btn.configure(font=('Inter',NAV_COMPACT_FONT_SIZE if compact else NAV_FONT_SIZE))
        self.version_label.pack_configure(pady=10 if compact else 20)

    def _poll_clock(self):
        if self._destroyed:
            return
        try:
            for _ in range(100):
                try:
                    callback = self._ui_events.get_nowait()
                except queue.Empty:
                    break
                self._clock_step(callback)
                if self._destroyed: return
            self._clock_step(self.work.drain)
            self._clock_step(self._poll_window_state)
            if not self._closing and not self._restoring:
                self._clock_step(self.timer_engine.tick)
            if time.monotonic()-self._last_slow_tick >= 1:
                self._last_slow_tick = time.monotonic()
                self._clock_step(self.views['sound'].refresh_playback)
                status = self.timer_engine.state.value.replace('_',' ').title()
                remaining = self.timer_engine._format_time(self.timer_engine.remaining_seconds)
                self._clock_step(lambda: self.tray.update(f'{status} {remaining} · Blocking: {self.blocking.status}'))
            if not self._closing and not self._restoring and time.monotonic()-self._last_planner_tick >= 30:
                self._last_planner_tick = time.monotonic()
                self._clock_step(self._check_planner_reminders)
        except Exception:
            logging.getLogger(__name__).exception('UI clock callback failed')
            self.report_error('An operation failed. Please check the application log in the data folder.')
        finally:
            if not self._destroyed:
                self._clock_job = self.after(100, self._poll_clock)

    def _clock_step(self, callback):
        """A failing Windows/UI integration must not starve timer ticks."""
        try:
            callback()
        except Exception:
            logging.getLogger(__name__).exception('UI clock operation failed')
            try:
                self.report_error('An operation failed. Please check the application log in the data folder.')
            except Exception:
                logging.getLogger(__name__).exception('Could not display the operation error')

    def _poll_window_state(self):
        if self.instance_guard and self.instance_guard.consume_activation():
            self._tray_action('open')
        if (self._ready_shown and not self._closing and not self.tray.available
                and self.state() == 'withdrawn'):
            self.deiconify()
            self._audio_suspended = False
            self.report_error('The tray icon is unavailable. Focus has reopened so you can control it.')

    def run_background(self, function, success=None, error=None, lane='system'):
        return self.work.submit(function, success, error or (lambda exc: self.report_error(str(exc))), lane)

    def report_error(self, message):
        logging.getLogger(__name__).warning(message)
        if hasattr(self,"notice") and self.winfo_exists():
            self.notice.configure(text=message)
            self.notice.pack(side='bottom',fill='x',padx=28,pady=8)

    def report_callback_exception(self, *error):
        logging.getLogger(__name__).error('Interface error',exc_info=error)
        self.report_error('An operation failed. Please check the application log in the data folder.')

    def update_settings(self, changes):
        self.config = update_config(changes)
        if 'global_hotkeys' in changes:
            if self.config['global_hotkeys']:
                if not self.hotkeys.enable(self.config.get('global_hotkey_bind','ctrl+shift+space')):
                    self.config = update_config({'global_hotkeys':False})
                    raise OSError('The global shortcut could not be registered. Choose another shortcut or try again.')
            else:
                self.hotkeys.disable()
        if 'hardcore_sites' in changes or 'hardcore_apps' in changes:
            self.apply_blocking()
        return self.config

    def _sync_mode_dropdowns(self):
        """Sync mode dropdowns in Timer and Blocker with DB modes."""
        modes = self.db.get_all_modes()
        mode_names = [m.name for m in modes]
        active_mode = self.config.get("active_mode", "Default")
        if active_mode not in mode_names:
            active_mode = "Default"
        
        # Update Timer mode dropdown
        if hasattr(self.views["timer"], 'mode_dropdown'):
            self.views["timer"].mode_dropdown.configure(values=mode_names)
            if hasattr(self.views["timer"], 'mode_dropdown_plugin'):
                self.views["timer"].mode_dropdown_plugin.configure(values=mode_names)
            self.views["timer"].mode_var.set(active_mode)
        
        # Update Blocker mode dropdown
        if hasattr(self.views["blocker"], 'mode_dropdown'):
            self.views["blocker"].mode_dropdown.configure(values=mode_names)
            if hasattr(self.views["blocker"], 'mode_dropdown_plugin'):
                self.views["blocker"].mode_dropdown_plugin.configure(values=mode_names)
            self.views["blocker"].mode_var.set(active_mode)

    def _on_modes_changed(self):
        active = self.db.get_mode(self.db.active_mode_id) or self.db.get_mode_by_name('Default')
        self._sync_mode_dropdowns()
        if self.timer_engine.state == TimerState.IDLE:
            self._on_mode_selected(active.name)

    def _save_current_mode_items(self):
        # Blocker CRUD persists immediately to its owning mode; no global snapshot.
        return

    def _on_mode_selected(self, mode_name, is_initial_load=False):
        if self._restoring or self._closing:
            return
        if self.timer_engine.state != TimerState.IDLE:
            for key in ('timer','blocker'):
                self.views[key].mode_var.set(self.config.get('active_mode','Default'))
            self.report_error('Stop the current session before changing modes.')
            return
        mode = self.db.get_mode_by_name(mode_name) or self.db.get_mode_by_name('Default')
        changed = self.db.active_mode_id != mode.id
        self.db.set_active_mode(mode.id)
        self.update_settings({'active_mode':mode.name})
        self.timer_engine.update_durations(mode.focus_minutes,mode.short_break_minutes,
            mode.long_break_minutes,mode.sessions_before_long_break,mode.auto_flow,mode.target_goal)
        self.timer_engine.mode_name = mode.name
        if changed:
            self.timer_engine.session_count = 0
        self.views['timer']._on_tick(self.timer_engine.focus_duration*60)
        self.views['timer']._update_session_label()
        self.views['blocker']._refresh_list()
        for key in ('timer','blocker'):
            self.views[key].mode_var.set(mode.name)

    def active_mode(self):
        return self.db.get_mode(self.db.active_mode_id)

    def is_focus_phase(self):
        engine = self.timer_engine
        return engine.state == TimerState.FOCUSING or (engine.state == TimerState.PAUSED and engine._state_before_pause == TimerState.FOCUSING)

    def blocking_locked(self):
        mode = self.active_mode()
        return bool(mode and mode.dead_lock and self.is_focus_phase())

    def allow_blocklist_edit(self):
        if self._restoring or self._closing:
            return False
        if self.blocking_locked():
            self.report_error('Blocking is locked until this focus session ends. Use Emergency unblock if necessary.')
            return False
        return True

    def can_edit_mode(self, mode):
        if self._restoring or self._closing:
            return False
        if mode.id == self.db.active_mode_id and self.timer_engine.state != TimerState.IDLE:
            self.report_error('Stop the current session before editing or deleting its mode.')
            return False
        return True

    def apply_blocking(self):
        from utils.validation import blocklist
        sites = self.views['blocker'].get_enabled_sites()
        apps = self.views['blocker'].get_enabled_apps()
        mode = self.active_mode()
        if mode and mode.whitelist_mode:
            config = load_config()
            sites += config.get('hardcore_sites',[])
            apps += config.get('hardcore_apps',[])
        cleaned = []
        for values,kind in ((sites,'website'),(apps,'app')):
            valid = []
            for value in values:
                try:
                    valid += blocklist([value],kind)
                except ValueError:
                    self.report_error('An invalid blocklist entry was skipped. Edit the list to correct it.')
            cleaned.append(list(dict.fromkeys(valid)))
        self.blocking.apply(self.is_focus_phase(), *cleaned)

    def blocklist_changed(self):
        self.apply_blocking()

    def stop_focus(self):
        if self._closing or self._restoring:
            return
        if self.blocking_locked():
            self.report_error('This session is locked. Use Emergency unblock to end it early.')
            return
        self.timer_engine.stop()

    def skip_phase(self):
        if self._closing or self._restoring:
            return
        if self.blocking_locked():
            self.report_error('This session is locked until the focus countdown finishes.')
            return
        self.timer_engine.skip()

    def emergency_unblock(self):
        if self._closing or self._restoring:
            return
        answer = CTkMessagebox(title='Emergency unblock',icon='warning',
            message='End the current session and release all Focus blocks?',option_1='Go back',option_2='End and unblock')
        if answer.get() == 'End and unblock':
            self.timer_engine.stop()
            self.blocking.apply(False)

    def _on_theme_changed(self):
        """Force redraw of non-CTk elements that don't auto-update."""
        # Force progress bar redraw
        if hasattr(self.views["timer"], "progress_circle"):
            self.views["timer"].progress_circle._draw()
            
        # Force stats chart redraw
        if hasattr(self.views["stats"], "refresh_stats"):
            self.views["stats"].refresh_stats()
            

    def show_view(self, view_name: str):
        if self._current_view==view_name:
            return
        if self._current_view:
            self.views[self._current_view].pack_forget()
            self.nav_buttons[self._current_view].set_active(False)
            
        self._current_view = view_name
        self.nav_buttons[view_name].set_active(True)
        names = {"timer": "Focus Timer", "blocker": "Distraction Blocker", "sound": "Sound Studio",
                 "customizer": "Focus Modes", "shutdown": "Shutdown Timer", "stats": "Statistics", "history": "Session History", "settings": "Settings", "planner": "Planner"}
        self.header_route.configure(text=names[view_name])
        if view_name == "timer":
            self.views["timer"].refresh_summary()
        self.views[view_name].pack(fill="both", expand=True)
        
        if view_name == "stats":
            self.views["stats"].refresh_stats()
        elif view_name == "customizer":
            self.views["customizer"].refresh_modes()
        elif view_name == "history":
            self.views["history"].refresh()
        elif view_name == "planner":
            self.planner_banner.pack_forget()
            self.views["planner"].refresh()

    def _check_planner_reminders(self):
        from core.planner import PlannerStore
        tasks = PlannerStore(self.db).due()
        if tasks:
            first = tasks[0]
            message = f'{first.start_time} · {first.title}'
            if len(tasks)>1: message += f' · +{len(tasks)-1} more tasks'
            self.planner_reminder_message = message
            self.planner_message.configure(text='PLANNER  ·  '+message)
            self.planner_banner.pack(side='bottom',fill='x',padx=28,pady=8)
            self._show_notification('Your plan is ready',message)
        if self._current_view == 'planner' and not self.grab_current():
            self.views['planner'].refresh()
            
    def _show_notification(self, title, message):
        mode = self.active_mode()
        if mode and not mode.notifications: return
        self.run_background(lambda: self.tray.notify(title,message))

    def _wrapped_on_state_change(self, state):
        previous, self._previous_state = self._previous_state, state
        try:
            self.header_status.configure(text='READY TO FOCUS' if state==TimerState.IDLE else state.value.replace('_',' ').upper())
            if self._original_on_state_change:
                self._original_on_state_change(state)
        except Exception:
            logging.getLogger(__name__).exception('Timer view callback failed')
        if state == TimerState.FOCUSING:
            self._on_focus_start()
            if previous != TimerState.PAUSED:
                self._show_notification('Focus','Time to focus.')
        elif state in (TimerState.SHORT_BREAK,TimerState.LONG_BREAK,TimerState.IDLE):
            self._on_focus_end()
            if state != TimerState.IDLE and previous != TimerState.PAUSED:
                self._show_notification('Focus','Time for a break. Your distractions have been released.')

    def _on_focus_start(self):
        # Blocking is independent of audio success and never waits for synthesis.
        self.apply_blocking()
        if getattr(self, '_audio_suspended', False):
            return
        mode = self.active_mode()
        if not mode or mode.auto_sound == 'none' or self.sound_engine.is_playing(mode.auto_sound):
            return
        self._audio_generation += 1
        generation = self._audio_generation
        audio_token = self.sound_engine.generation
        sound_type = mode.auto_sound
        path = None
        if sound_type.startswith('custom_'):
            path = next((s.file_path for s in self.db.get_all_custom_sounds() if f'custom_{s.id}'==sound_type),None)
            if path is None:
                self.report_error('The background recording is missing. Choose another sound in this mode.')
                return
        def play():
            if generation != self._audio_generation: return None
            started = self.sound_engine.play(sound_type,mode.auto_sound_volume,file_path=path,
                generation=audio_token)
            if started is False:
                return None
            stream = self.sound_engine.playback_handle(sound_type)
            if generation != self._audio_generation:
                self.sound_engine.stop(sound_type, expected_stream=stream)
                return None
            return stream
        def finished(stream):
            if stream is not None and generation == self._audio_generation:
                self._auto_sound_owned = (sound_type, stream)
            elif stream is not None:
                self.run_background(lambda: self.sound_engine.stop(sound_type, expected_stream=stream),lane='audio')
        self.run_background(play,finished,lambda exc: self.report_error('Background sound could not start: '+str(exc)),lane='audio')

    def _on_focus_end(self):
        self.blocking.apply(False)
        self._audio_generation += 1
        owned, self._auto_sound_owned = self._auto_sound_owned, None
        if owned:
            sound_type, stream = owned
            self.run_background(lambda: self.sound_engine.stop(sound_type, expected_stream=stream),lane='audio')

    def _on_hotkey_pressed(self):
        if self._closing or self._restoring:
            return
        timer_view = self.views.get("timer")
        if timer_view and hasattr(timer_view, '_pause_resume'):
            timer_view._pause_resume()

    def toggle_mini_player(self):
        self.is_mini = not getattr(self, "is_mini", False)
        if self.is_mini:
            self.show_view("timer")
            self.normal_geometry = self.geometry()
            self.sidebar_frame.grid_remove()
            self.topbar.grid_remove()
            self.attributes("-topmost", True)
            self.minsize(360, 420)
            self.geometry("380x460")
        else:
            self.sidebar_frame.grid()
            self.topbar.grid()
            self.attributes("-topmost", False)
            self.minsize(900, 600)
            self.geometry(self.normal_geometry)
        self.views["timer"].set_compact(self.is_mini)

    def _tray_action(self, action):
        if self._closing: return
        if action == 'open':
            self._audio_suspended = False
            self.deiconify()
            self.lift()
            self.focus_force()
        elif action == 'toggle':
            self._on_hotkey_pressed()
        elif action == 'stop':
            self.stop_focus()
        elif action == 'stop_sounds':
            self.stop_all_sounds()
        elif action == 'emergency':
            self._tray_action('open')
            self.emergency_unblock()
        elif action == 'quit':
            self._tray_action('open')
            self._quit()

    def stop_all_sounds(self):
        if self._closing:
            return
        self._audio_generation += 1
        self._auto_sound_owned = None
        self.sound_engine.request_stop_all()
        self.run_background(lambda: self.sound_engine.stop_all(invalidate=False),
            lambda _: self.views['sound'].refresh_playback(), lane='audio')

    def _on_close(self):
        if self._restoring or self._closing: return
        self._audio_suspended = True
        self.stop_all_sounds()
        if self.config.get('close_to_tray',True) and self.tray.available and not self.testing:
            self.withdraw()
        else:
            self._quit()
            if not self._closing:
                self._audio_suspended = False

    def _quit(self):
        if self._closing or self._restoring: return
        if self._data_busy:
            self.report_error('Please wait for the current data operation to finish before quitting.')
            return
        if self.timer_engine.state != TimerState.IDLE:
            answer = CTkMessagebox(title='Quit Focus',icon='warning',
                message='End the current session, unblock distractions and quit?',option_1='Keep focusing',option_2='End and quit')
            if answer.get() != 'End and quit': return
        self._closing = True
        self._audio_generation += 1
        self._auto_sound_owned = None
        self.sound_engine.request_stop_all(close=True)
        try:
            self.timer_engine.stop()
        except Exception:
            logging.getLogger(__name__).exception('Could not finish the last session during quit')
        try:
            self.notice.configure(text='Finishing background operations and releasing blocks…')
            self.notice.pack(side='bottom',fill='x',padx=28,pady=8)
        except Exception:
            logging.getLogger(__name__).exception('Could not show shutdown progress')
        def finish():
            try:
                self.shutdown_resources()
            finally:
                self._ui_events.put(self._destroy_app)
        threading.Thread(target=finish,daemon=True,name='shutdown-cleanup').start()

    def shutdown_resources(self):
        """Try every release even if another resource fails; safe after a crash."""
        for name, release in (('audio', self.sound_engine.close),
                              ('workers', self.work.close),
                              ('blocking', self.blocking.close),
                              ('hotkeys', self.hotkeys.disable),
                              ('tray', self.tray.stop)):
            try:
                release()
            except Exception:
                logging.getLogger(__name__).exception('Could not release %s during shutdown', name)

    def _destroy_app(self):
        self._destroyed = True
        try:
            if hasattr(self,'_clock_job'):
                self.after_cancel(self._clock_job)
        finally:
            self.destroy()

    def workspace_action(self, action):
        from tkinter import filedialog
        from core.backup import BackupManager
        from utils.constants import DB_DIR
        if self._restoring or self._closing or self._data_busy: return
        if action in ('restore','import_modes') and self.timer_engine.state != TimerState.IDLE:
            self.report_error('Stop the current session before restoring or importing data.')
            return
        if action in ('backup','export_modes'):
            suffix = '.zip' if action=='backup' else '.json'
            path = filedialog.asksaveasfilename(title='Save Focus backup' if action=='backup' else 'Export focus modes',
                defaultextension=suffix,initialfile='Focus-'+time.strftime('%Y%m%d-%H%M')+suffix,
                filetypes=[('Focus backup','*.zip')] if action=='backup' else [('Focus modes','*.json')])
        else:
            path = filedialog.askopenfilename(title='Restore workspace' if action=='restore' else 'Import focus modes',
                filetypes=[('Focus backup','*.zip')] if action=='restore' else [('Focus modes','*.json')])
        if not path: return
        if action=='restore':
            answer = CTkMessagebox(title='Restore workspace',icon='warning',
                message='Replace modes, settings, recordings and history with this backup? Your current workspace will be backed up first. Windows shutdown schedules and sign-in settings are not changed.',
                option_1='Go back',option_2='Restore workspace')
            if answer.get()!='Restore workspace': return
        # Native dialogs run a nested Tk loop: timer/hotkey state can change
        # while the user is choosing a file or confirming a restore.
        if self._restoring or self._closing or self._data_busy:
            return
        if action in ('restore', 'import_modes') and self.timer_engine.state != TimerState.IDLE:
            self.report_error('Stop the current session before restoring or importing data.')
            return
        progress = ctk.CTkToplevel(self)
        set_window_brand(progress)
        progress.title('Focus')
        progress.geometry('430x130')
        progress.transient(self)
        progress.grab_set()
        progress.protocol('WM_DELETE_WINDOW',lambda: None)
        ctk.CTkLabel(progress,text='Working on your data…',font=('Inter',17,'bold')).pack(pady=(25,8))
        ctk.CTkLabel(progress,text='Please keep Focus open.',font=('Inter',12)).pack()
        self._data_busy = True
        self._restoring = action in ("restore", "import_modes")
        if action == 'restore':
            self.stop_all_sounds()
        def run():
            if action=='restore': self.sound_engine.cleanup()
            return operation(path)
        def done(result=None,error=None):
            self._restoring = self._data_busy = False
            progress.grab_release()
            progress.destroy()
            if error:
                self.report_error(str(error))
                return
            if action=='restore':
                self.reload_workspace()
                text='Workspace restored. Recovery backup: '+result['backup']
                if result['missing_sounds']: text+=' · Missing recordings were detached from their modes.'
            elif action=='import_modes':
                self._on_modes_changed()
                self.views['customizer'].refresh_modes()
                text=f'Imported {result} modes. Existing presets were kept.'
            else:
                text='Saved: '+str(result)
            self.report_error(text)
        try:
            manager = BackupManager(self.db,DB_DIR)
            operation = {'backup':manager.export_workspace,'export_modes':manager.export_modes,
                         'restore':manager.restore_workspace,'import_modes':manager.import_modes}[action]
            future = self.run_background(run,lambda result: done(result),lambda exc: done(error=exc))
            if future is None:
                done(error=RuntimeError('The data operation could not start. Please try again after reopening Focus.'))
        except Exception as exc:
            done(error=exc)

    def reload_workspace(self):
        self.config = load_config()
        self.db = DatabaseManager(self.db.db_path,self.config.get('active_mode','Default'))
        self.planner_banner.pack_forget()
        self.timer_engine.db = self.db
        self.timer_engine.session_count = 0
        for view in self.views.values():
            if hasattr(view,'db'): view.db = self.db
        self._auto_sound_owned = None
        self._on_modes_changed()
        self.views['sound']._refresh_cards()
        self.views['sound'].refresh_sounds()
        self.views['settings'].refresh_preferences()
        ctk.set_appearance_mode(self.config.get('theme','dark'))
        self._on_theme_changed()
        if self.config.get('global_hotkeys'):
            if not self.hotkeys.enable(self.config.get('global_hotkey_bind','ctrl+shift+space')):
                self.update_settings({'global_hotkeys':False})
        else:
            self.hotkeys.disable()
