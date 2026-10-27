from ui.metrics import PRIMARY_CONTROL_HEIGHT, PRIMARY_FONT_SIZE
from ui.metrics import (
    CONTROL_FONT_SIZE, CONTROL_HEIGHT
)
from ui.design import MaterialFrame, set_window_brand
from ui.panels import fit_wrap
from ui.design import MaterialButton
from utils.constants import SEPARATOR_COLOR
import os
import sys
import customtkinter as ctk
from utils.constants import (BG_PRIMARY, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, 
                             APP_NAME, APP_SUITE, APP_VERSION, TEXT_MUTED, HOVER_BG, SEPARATOR_COLOR, INPUT_BG,
                             ACCENT_STATS, ACCENT_CUSTOM, ACCENT_HOVER_DARK, load_config, save_config)
from core.startup import set_run_on_startup, is_run_on_startup


class HowToUseDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        set_window_brand(self)
        self.title("How to use Focus")
        self.geometry("800x700")
        from utils.constants import BG_PRIMARY, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_CUSTOM
        self.configure(fg_color=BG_PRIMARY)
        self.transient(parent)
        self.grab_set()

        # Title
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header_frame, text="Your Focus guide", font=("Inter", 28, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(header_frame, text="Controls, blocking, backups and your daily rhythm.", font=("Inter", 14), text_color=TEXT_SECONDARY).pack(anchor="w")

        # Textbox for 1000+ words
        self.textbox = ctk.CTkTextbox(self, font=("Inter", 14), text_color=TEXT_PRIMARY, fg_color=BG_CARD, wrap="word")
        self.textbox.pack(fill="both", expand=True, padx=20, pady=10)

        guide_text = """FOCUS — SPERTULO UTILITY

FOCUS MODES
Create a mode with its own focus length, breaks, daily goal and blocklists. Each mode remembers its own enabled and disabled items. A goal of 0 means unlimited auto-flow. Stop the current session before editing its mode.

PLANNER
Choose a day in the week strip. Use the arrows to change weeks and Today to return. Type a task and press Enter for quick capture, or choose Plan task to set a date, optional 24-hour start time, priority, estimate, notes and a checklist. Open and Done filter the selected day. Click a task checkbox to finish or reopen it; expand its steps to check them individually. Edit lets you change details, move it to tomorrow or delete it.

Click the month/year button above the week to open the calendar. Select a month and type a year, then press Enter; or enter YYYY-MM-DD and choose Go to date to jump directly to a distant day. Click a calendar day to open that agenda. Dots mark days with open tasks. The task editor also offers Pick next to the date field. Cancel leaves your selected date unchanged.

Focus starts a session using the linked Focus Mode, or the current mode when no mode is linked. The time estimate belongs to your plan; the mode controls the actual focus length. Finish or stop an existing timer first. Tasks stay open until you mark them complete. Overdue and overlapping blocks are flagged without moving your schedule.

Reminders appear in the app and, when notifications are enabled and the tray is available, as Windows notifications. Focus must stay open (the system tray is fine). Today's due tasks are grouped into one reminder and are not repeated after restarting. Changing the date or start time rearms the reminder. Planner does not start timers, block apps or wake the computer automatically. Workspace backups include your tasks and checklist progress.

WHITELIST MODE
In Settings > Strict whitelist, maintain the shared list of websites and apps to block. When creating a mode, turn on Whitelist mode to fill both blocklists from these settings. Whitelist sessions also include the latest shared list when they start. This feature uses a preset blocklist; it does not create a network-wide allowlist.

BLOCKING AND LOCKED SESSIONS
Lists can be prepared while idle without activating blocking. Blocking runs during focus, including a paused focus, and is released during breaks or when a session ends. Website blocking needs administrator access.

Lock blocking prevents changing the active blocklists, stopping or skipping a focus early. Pause keeps the current restrictions. For an urgent exit, choose Emergency unblock and confirm End and unblock. This ends the session and records it as stopped. Quit also asks before ending a running session.

SOUND STUDIO
Mix ambient sounds and adjust their levels independently. Your sound library is in Sounds, below the built-in cards. Import mono/stereo PCM WAV files: 8, 16, 24 or 32 bit, up to 64 MB and 6 minutes. Different sample rates are converted for playback. Imports with the same name get separate names and files. Removing a recording detaches it from modes that use it.

TIMER AND HISTORY
Start, Pause and Resume control your session. Stop and Skip are recorded separately and do not count as completed focus blocks. Session History shows planned length and measured focus time. Pauses are excluded from measured time. Older sessions without a measured value show a dash. Statistics include measured time from incomplete sessions; older completed sessions use their planned duration.

TRAY AND SHORTCUT
With Keep working in the tray enabled, closing the window keeps your timer running and stops all sounds, including sounds still preparing. Double-click the Focus tray icon or launch Focus again to reopen the same app. Right-click for Open, Start/Pause, Stop session, Stop all sounds, Emergency unblock or Quit. Sound Studio also has a Stop all sounds button. If the tray icon is lost, the hidden window reopens so you can control the app. If the tray cannot start, closing uses the normal quit confirmation instead. The global shortcut is Ctrl + Shift + Space and can be enabled or disabled immediately in Settings.

SHUTDOWN TIMER
Choose a preset or enter hours/minutes, then confirm Schedule shutdown. Save your documents first: Windows may close applications when the countdown ends. Closing Focus does not cancel a scheduled shutdown. Cancel shutdown also clears schedules created outside this app.

When Focus reopens, it shows its last recorded shutdown time as unverified. Another program may have canceled the schedule, or the PC may have restarted. Use Cancel shutdown to clear any pending schedule before setting a new one. Restoring a workspace never schedules or cancels a Windows shutdown.

BACKUP AND RESTORE
Settings > Your data contains Create backup, Restore backup, Export modes and Import modes. A full backup includes settings, modes, session history and available recordings. Restoring creates a recovery backup first, validates the incoming data and rolls back if replacement fails. Windows sign-in settings and shutdown schedules are kept unchanged.

Mode exports do not include recordings or history. Imported names are adjusted to avoid replacing existing presets; references to personal recordings are reset to None. Restore/import is available only while the timer is idle.

DATA AND DIAGNOSTICS
Your data is stored in your Windows user profile, in .deepfocus. Database migrations create a pre-migration backup. Logs rotate in the logs folder so they stay small. A missing output device affects sound only; focus blocking continues and the app reports the audio error.
"""
        self.textbox.insert("0.0", guide_text)
        self.textbox.configure(state="disabled") # Make read-only

        # Close button
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 20))
        MaterialButton(btn_frame, text="Got it!", fg_color=ACCENT_CUSTOM, text_color="white", command=self.destroy, font=("Inter", PRIMARY_FONT_SIZE, "bold"), width=200, height=PRIMARY_CONTROL_HEIGHT).pack()


class ThemeCard(ctk.CTkFrame):
    """A small, clickable workspace preview with a stable selection border."""
    def __init__(self, master, title, bg_color, text_color, theme_name, command, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10, border_width=1,
                         border_color=SEPARATOR_COLOR, cursor="hand2", **kwargs)
        from ui.panels import label
        self.theme_name, self.command, self.is_active = theme_name, command, False
        dark = theme_name == "dark"
        preview = ctk.CTkFrame(self, height=94, fg_color=bg_color, corner_radius=7)
        preview.pack(fill="x", padx=10, pady=(10, 0))
        preview.pack_propagate(False)
        rail = ctk.CTkFrame(preview, fg_color="#1B222C" if dark else "#E8E7E4", width=40, corner_radius=0)
        rail.pack(side="left", fill="y")
        for i in range(3):
            ctk.CTkFrame(rail, fg_color="#E73A2E" if i == 0 else ("#47505E" if dark else "#C4C6C9"),
                         width=18, height=4, corner_radius=2).pack(pady=(15 if i == 0 else 9, 0), padx=11)
        page = ctk.CTkFrame(preview, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=14, pady=14)
        ctk.CTkFrame(page, width=70, height=5, corner_radius=2, fg_color=text_color).pack(anchor="w")
        ctk.CTkFrame(page, height=31, corner_radius=5, fg_color="#232B36" if dark else "#E8E7E4").pack(fill="x", pady=(10, 8))
        ctk.CTkFrame(page, width=36, height=5, corner_radius=2, fg_color="#E73A2E").pack(anchor="w")
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=14, pady=10)
        label(footer, title, 12, bold=True).pack(side="left")
        self.indicator = label(footer, "", 10, ACCENT_CUSTOM, True)
        self.indicator.pack(side="right")
        def bind_children(widget):
            widget.bind("<Button-1>", self._on_click)
            for child in widget.winfo_children():
                bind_children(child)
        bind_children(self)
        self.bind("<Enter>", lambda e: self.configure(border_color=TEXT_MUTED) if not self.is_active else None)
        self.bind("<Leave>", lambda e: self.configure(border_color=SEPARATOR_COLOR) if not self.is_active else None)

    def _on_click(self, event):
        self.command(self.theme_name)

    def set_active(self, active):
        self.is_active = active
        self.configure(border_color=ACCENT_CUSTOM if active else SEPARATOR_COLOR, border_width=1)
        self.indicator.configure(text="SELECTED" if active else "")


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, parent, on_theme_changed=None):
        super().__init__(parent, fg_color=BG_PRIMARY, corner_radius=0)
        from ui.panels import PageHeader, surface, label, rule
        from ui.design import brand_image
        self.on_theme_changed = on_theme_changed
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=28, pady=24)
        PageHeader(content, "MAKE IT YOURS", "Settings",
                   "Fine-tune the space where your best work happens.").pack(fill="x", pady=(0, 22))

        appearance = surface(content)
        appearance.pack(fill="x", pady=(0, 18))
        appearance.grid_columnconfigure(0, weight=1)
        label(appearance, "Appearance", 17, bold=True).grid(row=0, column=0, sticky="w", padx=22, pady=(18, 0))
        label(appearance, "Choose the light around your work.", 12, TEXT_SECONDARY).grid(row=1, column=0, sticky="w", padx=22, pady=(3, 16))
        previews = ctk.CTkFrame(appearance, fg_color="transparent")
        previews.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 20))
        previews.grid_columnconfigure((0, 1), weight=1, uniform="themes")
        self.light_card = ThemeCard(previews, "Daylight", "#F3F2F0", "#1E252F", "light", self.set_theme)
        self.light_card.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.dark_card = ThemeCard(previews, "Graphite", "#0B0E14", "#EFF2F7", "dark", self.set_theme)
        self.dark_card.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        preferences = surface(content)
        preferences.pack(fill="x", pady=(0, 18))
        label(preferences, "Workflow", 17, bold=True).pack(anchor="w", padx=22, pady=(18, 6))
        config = load_config()
        self.startup_var = ctk.BooleanVar(value=config.get("run_on_startup", False))
        self.hotkeys_var = ctk.BooleanVar(value=config.get("global_hotkeys", False))
        self.startup_switch = self._preference_row(preferences, "Launch at sign-in",
            "Have your workspace ready when Windows starts.", self.startup_var, self._toggle_startup)
        rule(preferences).pack(fill="x", padx=22)
        self.hotkeys_switch = self._preference_row(preferences, "Global keyboard shortcut",
            "Start or pause from anywhere with Ctrl + Shift + Space.", self.hotkeys_var, self._toggle_hotkeys)

        rule(preferences).pack(fill="x", padx=22)
        self.tray_var = ctk.BooleanVar(value=config.get('close_to_tray', True))
        self._preference_row(preferences, 'Keep working in the tray',
            'Closing the window keeps the timer running and stops all sounds. Quit from the tray menu.',
            self.tray_var, lambda: self._save_changes({'close_to_tray':self.tray_var.get()}))
        data = surface(content)
        data.pack(fill='x',pady=(0,18))
        label(data,'Your data',17,bold=True).pack(anchor='w',padx=22,pady=(18,6))
        self._action_row(data,'Back up workspace','Save modes, settings, recordings and session history.',
            'Create backup',lambda: self.winfo_toplevel().workspace_action('backup'))
        rule(data).pack(fill='x',padx=22)
        self._action_row(data,'Restore workspace','A recovery backup is created before your data is replaced.',
            'Restore backup',lambda: self.winfo_toplevel().workspace_action('restore'))
        rule(data).pack(fill='x',padx=22)
        self._action_row(data,'Share your modes','Export mode presets without history or personal recordings.',
            'Export modes',lambda: self.winfo_toplevel().workspace_action('export_modes'))
        rule(data).pack(fill='x',padx=22)
        self._action_row(data,'Bring in modes','Add imported presets without overwriting existing names.',
            'Import modes',lambda: self.winfo_toplevel().workspace_action('import_modes'))

        tools = surface(content)
        tools.pack(fill="x", pady=(0, 18))
        self.edit_hc_btn = self._action_row(tools, "Strict whitelist", "Manage the default list used by whitelist modes.",
                                          "Manage list", self._show_hardcore_dialog)
        rule(tools).pack(fill="x", padx=22)
        self._action_row(tools, "A little guidance", "Explore timer controls, focus modes and sound.",
                         "Open guide", self._open_how_to_use)
        creator = surface(content)
        creator.pack(fill='x', pady=(0, 18))
        self.about_button = self._action_row(creator, f'About {APP_NAME}',
            'Meet the creator and discover more tools from Spertulo Utility.',
            'About Focus', self._open_about)
        about = ctk.CTkFrame(content, fg_color="transparent")
        about.pack(fill="x", pady=(6, 4))
        label(about, "", image=brand_image(32)).pack(side="left", padx=(0, 12))
        label(about, APP_NAME, 12, bold=True).pack(side="left")
        label(about, f"Version {APP_VERSION}  ·  {APP_SUITE}", 11, TEXT_SECONDARY).pack(side="right")
        self.load_and_apply_theme()

    def _open_about(self):
        app = self.winfo_toplevel()
        if getattr(app, '_closing', False):
            return
        existing = getattr(self, '_about_dialog', None)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_set()
            return existing
        import json
        from ui.design import BRANDING
        from ui.about_dialog import AboutDialog
        try:
            profile = json.loads((BRANDING / 'creator.json').read_text(encoding='utf-8'))
            if not profile.get('name') or not profile.get('github_url'):
                raise ValueError('Missing creator details')
        except (OSError, ValueError, AttributeError):
            app.report_error('Creator information could not be loaded.')
            return
        self._about_dialog = AboutDialog(app, profile)
        return self._about_dialog

    def _preference_row(self, parent, title, description, variable, command):
        from ui.panels import label
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=16)
        row.grid_columnconfigure(0, weight=1)
        label(row, title, 13, bold=True).grid(row=0, column=0, sticky="w")
        detail = label(row, description, 12, TEXT_SECONDARY, justify="left")
        detail.grid(row=1, column=0, sticky="w", pady=(4, 0))
        toggle = ctk.CTkSwitch(row, text="", width=38, switch_width=36, switch_height=20,
                              variable=variable, progress_color=ACCENT_CUSTOM, command=command)
        toggle.grid(row=0, column=1, rowspan=2, padx=(20, 0), sticky="e")
        row.bind("<Configure>", lambda e: fit_wrap(detail,max(200,e.width-85)))
        return toggle

    def _action_row(self, parent, title, description, action, command):
        from ui.panels import label
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=18)
        row.grid_columnconfigure(0, weight=1)
        label(row, title, 13, bold=True).grid(row=0, column=0, sticky="w")
        detail = label(row, description, 12, TEXT_SECONDARY, justify="left")
        detail.grid(row=1, column=0, sticky="w", pady=(4, 0))
        button = ctk.CTkButton(row, text=action, width=120, height=CONTROL_HEIGHT, fg_color=INPUT_BG,
            hover_color=HOVER_BG, text_color=TEXT_PRIMARY, font=("Inter", CONTROL_FONT_SIZE), command=command)
        button.grid(row=0, column=1, rowspan=2, padx=(20, 0), sticky="e")
        row.bind("<Configure>", lambda e: fit_wrap(detail,max(180,e.width-160)))
        return button

    def load_and_apply_theme(self):
        try:
            config = load_config()
            theme = config.get("theme", "dark").lower()
            self._update_cards(theme)
        except Exception as e:
            print(f"Error loading config: {e}")
            self._update_cards("dark") # Fallback
        
    def _save_changes(self, changes):
        from CTkMessagebox import CTkMessagebox
        try:
            self.winfo_toplevel().update_settings(changes)
            return True
        except Exception as exc:
            CTkMessagebox(title='Could not save settings',message=str(exc),icon='cancel')
            self.refresh_preferences()
            return False

    def refresh_preferences(self):
        config = load_config()
        self.startup_var.set(config.get('run_on_startup',False))
        self.hotkeys_var.set(config.get('global_hotkeys',False))
        self.tray_var.set(config.get('close_to_tray',True))
        self._update_cards(config.get('theme','dark'))

    def set_theme(self, theme_name):
        if theme_name not in ('light','dark'): return
        if not self._save_changes({'theme':theme_name}): return
        ctk.set_appearance_mode(theme_name)
        self._update_cards(theme_name)
        if self.on_theme_changed: self.on_theme_changed()

    def _toggle_startup(self):
        from CTkMessagebox import CTkMessagebox
        app = self.winfo_toplevel()
        value = self.startup_var.get()
        self.startup_switch.configure(state='disabled')
        def done(ok):
            self.startup_switch.configure(state='normal')
            if not ok:
                self.startup_var.set(not value)
                CTkMessagebox(title='Startup preference',message='Windows could not update the sign-in setting.',icon='cancel')
            elif not self._save_changes({'run_on_startup':value}):
                app.run_background(lambda: set_run_on_startup(not value))
        app.run_background(lambda: set_run_on_startup(value),done,
            lambda error: (self.startup_switch.configure(state='normal'),app.report_error(str(error))))

    def _toggle_hotkeys(self):
        self._save_changes({'global_hotkeys':self.hotkeys_var.get()})

    def _show_hardcore_dialog(self):
        if not self.winfo_toplevel().allow_blocklist_edit(): return
        HardcoreDialog(self.winfo_toplevel())
        
    def _open_how_to_use(self):
        HowToUseDialog(self.winfo_toplevel())


    def _update_cards(self, active_theme):
        if active_theme == "light":
            self.light_card.set_active(True)
            self.dark_card.set_active(False)
        else:
            self.light_card.set_active(False)
            self.dark_card.set_active(True)

class HardcoreDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        set_window_brand(self)
        self.title("Strict whitelist")
        self.geometry("500x600")
        self.transient(parent)
        self.grab_set()
        
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 600) // 2
        self.geometry(f"+{int(x)}+{int(y)}")
        
        self.configure(fg_color=BG_PRIMARY)
        
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=30, pady=30)
        
        title_lbl = ctk.CTkLabel(main_frame, text="Strict whitelist", font=("Inter", 20, "bold"), text_color=TEXT_PRIMARY)
        title_lbl.pack(anchor="w", pady=(0, 5))
        
        desc_lbl = ctk.CTkLabel(main_frame, text="These items are forcefully blocked when 'Strict Whitelist' is enabled.", font=("Inter", 12), text_color=TEXT_SECONDARY)
        desc_lbl.pack(anchor="w", pady=(0, 20))
        
        config = load_config()
        sites = config.get("hardcore_sites", [])
        apps = config.get("hardcore_apps", [])
        
        ctk.CTkLabel(main_frame, text="Websites (One per line):", font=("Inter", 14, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        self.sites_box = ctk.CTkTextbox(main_frame, height=150, fg_color=INPUT_BG, text_color=TEXT_PRIMARY)
        self.sites_box.pack(fill="x", pady=(5, 15))
        self.sites_box.insert("1.0", "\n".join(sites))
        
        ctk.CTkLabel(main_frame, text="Applications (One per line):", font=("Inter", 14, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        self.apps_box = ctk.CTkTextbox(main_frame, height=150, fg_color=INPUT_BG, text_color=TEXT_PRIMARY)
        self.apps_box.pack(fill="x", pady=(5, 20))
        self.apps_box.insert("1.0", "\n".join(apps))
        
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")
        
        cancel_btn = MaterialButton(btn_frame, text="Cancel", fg_color=INPUT_BG, hover_color=HOVER_BG, text_color=TEXT_PRIMARY, command=self.destroy, height=CONTROL_HEIGHT, font=("Inter", CONTROL_FONT_SIZE))
        cancel_btn.pack(side="right", padx=(10, 0))
        
        save_btn = MaterialButton(btn_frame, text="Save", fg_color=ACCENT_CUSTOM, text_color="#ffffff", hover_color=ACCENT_HOVER_DARK, command=self._save, height=CONTROL_HEIGHT, font=("Inter", CONTROL_FONT_SIZE))
        save_btn.pack(side="right")
        
    def _save(self):
        from utils.validation import blocklist
        from CTkMessagebox import CTkMessagebox
        app = self.master.winfo_toplevel()
        if not app.allow_blocklist_edit(): return
        try:
            sites = blocklist(self.sites_box.get('1.0','end-1c').splitlines(),'website')
            apps = blocklist(self.apps_box.get('1.0','end-1c').splitlines(),'app')
            app.update_settings({'hardcore_sites':sites,'hardcore_apps':apps})
        except (ValueError,OSError) as exc:
            CTkMessagebox(title='Could not save list',message=str(exc),icon='cancel')
            return
        self.destroy()
