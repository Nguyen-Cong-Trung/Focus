from ui.dropdown import FocusDropdown
from ui.panels import fit_wrap
from ui.design import MaterialFrame
from ui.design import MaterialButton
from utils.constants import SEPARATOR_COLOR
import json
import sqlite3
from typing import Callable, Optional
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from utils.constants import (BG_PRIMARY, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, 
                             TEXT_MUTED, HOVER_BG, SEPARATOR_COLOR, INPUT_BG,
                             INPUT_BTN_COLOR, INPUT_BTN_HOVER, ACCENT_CUSTOM, ACCENT_STATS, ACCENT_BREAK,
                             load_config, save_config, ACCENT_DANGER)
from data.database import DatabaseManager
from data.models import FocusMode


class ModeDialog(ctk.CTkToplevel):
    def __init__(self, parent, db: DatabaseManager, mode: Optional[FocusMode] = None, on_save: Callable = None):
        super().__init__(parent)
        self.db = db
        self.mode = mode
        self.on_save_callback = on_save
        
        self.title("Edit Mode" if mode else "Create New Mode")
        self.geometry("620x720")
        self.minsize(560, 580)
        self.configure(fg_color=BG_PRIMARY)
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        from ui.panels import PageHeader, rule
        from ui.design import set_window_brand
        set_window_brand(self)
        header = PageHeader(self, "DESIGN YOUR RHYTHM", "Edit focus mode" if mode else "A new way to focus",
                            "Set your timing, distractions and atmosphere.")
        header.pack(fill="x", padx=28, pady=(24, 18))
        self.actions = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0)
        self.actions.pack(side="bottom", fill="x")
        rule(self.actions).pack(side="top", fill="x")
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color=BG_PRIMARY, corner_radius=0)
        self.main_frame.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        

        
        # Form fields
        self.name_entry = self._create_entry("Mode Name", "e.g. Study, Work, Focus")
        
        time_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        time_frame.pack(fill="x", pady=10)
        
        self.focus_entry = self._create_entry("Focus / minutes", "25", time_frame, side="left", width=100)
        self.sessions_entry = self._create_entry("Sessions", "4", time_frame, side="left", width=100, padx=(10, 0))
        
        break_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        break_frame.pack(fill="x", pady=10)
        
        self.short_break_entry = self._create_entry("Short break / minutes", "5", break_frame, side="left", width=100)
        self.long_break_entry = self._create_entry("Long break / minutes", "15", break_frame, side="left", width=100, padx=(10, 0))
        
        self.whitelist_var = ctk.BooleanVar(value=False)
        self.whitelist_switch = ctk.CTkSwitch(
            self.main_frame, text="Whitelist mode", variable=self.whitelist_var,
            text_color=TEXT_PRIMARY, progress_color=ACCENT_CUSTOM,
            command=self._on_whitelist_changed)
        self.whitelist_switch.pack(anchor="w", pady=(12, 4))
        ctk.CTkLabel(self.main_frame,
            text="Fill blocked websites and apps from Settings > Strict whitelist.",
            font=("Inter", 11), text_color=TEXT_SECONDARY, wraplength=510,
            justify="left").pack(anchor="w", pady=(0, 6))

        self.sites_box = self._create_textbox("Blocked Websites (one per line)")
        self.apps_box = self._create_textbox("Blocked Applications (one per line)")
        
        self.dead_lock_var = ctk.BooleanVar(value=False)
        self.dead_lock_switch = ctk.CTkSwitch(
            self.main_frame, text="Lock blocking until the session ends", 
            variable=self.dead_lock_var, text_color=TEXT_PRIMARY,
            progress_color=ACCENT_CUSTOM
        )
        self.dead_lock_switch.pack(anchor="w", pady=(15, 5))
        
        self.notif_var = ctk.BooleanVar(value=True)
        self.notif_switch = ctk.CTkSwitch(
            self.main_frame, text="Session and break notifications", 
            variable=self.notif_var, text_color=TEXT_PRIMARY,
            progress_color=ACCENT_CUSTOM
        )
        self.notif_switch.pack(anchor="w", pady=(5, 5))
        
        self.auto_flow_var = ctk.BooleanVar(value=False)
        self.auto_flow_switch = ctk.CTkSwitch(
            self.main_frame, text="Start the next session automatically", 
            variable=self.auto_flow_var, text_color=TEXT_PRIMARY,
            progress_color=ACCENT_CUSTOM
        )
        self.auto_flow_switch.pack(anchor="w", pady=(5, 5))
        
        goal_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        goal_frame.pack(fill="x", pady=(10, 20))
        self.target_goal_entry = self._create_entry("Target Goal (Sessions)", "4", goal_frame, side="left", width=150, padx=(10, 0))
        
        # Audio Section
        audio_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        audio_frame.pack(fill="x", pady=(15, 5))
        
        ctk.CTkLabel(audio_frame, text="Auto-play Background Sound:", font=("Inter", 12), text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 5))
        from utils.constants import SOUND_TYPES, SOUND_LABELS
        sound_options = ["None"] + [SOUND_LABELS.get(s, s) for s in SOUND_TYPES]
        
        self.custom_sounds_map = {}
        for cs in self.db.get_all_custom_sounds():
            lbl = f"{cs.icon} {cs.name}"
            self.custom_sounds_map[lbl] = f"custom_{cs.id}"
            sound_options.append(lbl)
        self.sound_var = ctk.StringVar(value="None")
        self.sound_dropdown = FocusDropdown(
            audio_frame, menu_title="BACKGROUND SOUND", values=sound_options, variable=self.sound_var,
            fg_color=INPUT_BG, button_color=INPUT_BG, button_hover_color=HOVER_BG, text_color=TEXT_PRIMARY
        )
        self.sound_dropdown.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(audio_frame, text="Sound Volume:", font=("Inter", 12), text_color=TEXT_SECONDARY).pack(anchor="w")
        self.volume_slider = ctk.CTkSlider(audio_frame, from_=0.0, to=1.0, progress_color=ACCENT_CUSTOM)
        self.volume_slider.pack(fill="x", pady=(5, 5))
        self.volume_slider.set(0.5)

        # Populate if editing
        if mode:
            self.name_entry.insert(0, mode.name)
            self.focus_entry.insert(0, str(mode.focus_minutes))
            self.sessions_entry.insert(0, str(mode.sessions_before_long_break))
            self.short_break_entry.insert(0, str(mode.short_break_minutes))
            self.long_break_entry.insert(0, str(mode.long_break_minutes))
            
            try:
                sites = json.loads(mode.blocked_sites)
                if sites:
                    self.sites_box.insert("1.0", "\n".join(sites))
            except: pass
            
            try:
                apps = json.loads(mode.blocked_apps)
                if apps:
                    self.apps_box.insert("1.0", "\n".join(apps))
            except: pass
            
            self.dead_lock_var.set(mode.dead_lock)
            self.notif_var.set(mode.notifications)
            self.auto_flow_var.set(mode.auto_flow)
            self.whitelist_var.set(mode.whitelist_mode)
            self.target_goal_entry.insert(0, str(mode.target_goal))
            
            if hasattr(mode, 'auto_sound') and mode.auto_sound != 'none':
                from utils.constants import SOUND_LABELS
                if mode.auto_sound.startswith("custom_"):
                    cs_id = int(mode.auto_sound.split("_")[1])
                    for cs in self.db.get_all_custom_sounds():
                        if cs.id == cs_id:
                            self.sound_var.set(f"{cs.icon} {cs.name}")
                            break
                else:
                    lbl = SOUND_LABELS.get(mode.auto_sound, mode.auto_sound)
                    self.sound_var.set(lbl)
            if hasattr(mode, 'auto_sound_volume'):
                self.volume_slider.set(mode.auto_sound_volume)
        else:
            self.focus_entry.insert(0, "25")
            self.sessions_entry.insert(0, "4")
            self.short_break_entry.insert(0, "5")
            self.long_break_entry.insert(0, "15")
            self.target_goal_entry.insert(0, "4")
            
        btn_frame = ctk.CTkFrame(self.actions, fg_color="transparent")
        btn_frame.pack(fill="x", padx=28, pady=16)
        
        cancel_btn = MaterialButton(
            btn_frame, text="Cancel", height=38, fg_color="transparent", 
            border_width=1, border_color=TEXT_MUTED, text_color=TEXT_PRIMARY,
            hover_color=HOVER_BG, command=self.destroy
        )
        cancel_btn.pack(side="right", padx=(10, 0))
        
        save_btn = MaterialButton(
            btn_frame, text="Save mode", height=38, fg_color=ACCENT_CUSTOM, 
            text_color="white", hover_color=INPUT_BTN_HOVER, command=self._save
        )
        save_btn.pack(side="right")
        
    def _on_whitelist_changed(self):
        if not self.whitelist_var.get():
            return
        config = load_config()
        for textbox, key in ((self.sites_box, "hardcore_sites"), (self.apps_box, "hardcore_apps")):
            textbox.delete("1.0", "end")
            textbox.insert("1.0", "\n".join(config.get(key, [])))

    def _create_entry(self, label_text, placeholder, parent=None, side="top", width=None, padx=0):
        if parent is None:
            parent = self.main_frame
        
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        if side == "top":
            frame.pack(fill="x", pady=10, padx=padx)
        else:
            column = len(parent.winfo_children()) - 1
            parent.grid_columnconfigure(column, weight=1, uniform="form_fields")
            frame.grid(row=0, column=column, sticky="ew", padx=(0, 5) if column == 0 else (5, 0))
            
        label = ctk.CTkLabel(frame, text=label_text, font=("Inter", 12), text_color=TEXT_SECONDARY)
        label.pack(anchor="w", pady=(0, 5))
        
        kwargs = {"height": 40, "corner_radius": 8, "font": ("Inter", 14), "placeholder_text": placeholder, "fg_color": INPUT_BG, "border_color": SEPARATOR_COLOR, "text_color": TEXT_PRIMARY}
        if width:
            kwargs["width"] = width
            
        entry = ctk.CTkEntry(frame, **kwargs)
        entry.pack(fill="x")
        return entry
        
    def _create_textbox(self, label_text):
        frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame.pack(fill="x", pady=10)
        
        label = ctk.CTkLabel(frame, text=label_text, font=("Inter", 12), text_color=TEXT_SECONDARY)
        label.pack(anchor="w", pady=(0, 5))
        
        textbox = ctk.CTkTextbox(frame, height=80, fg_color=INPUT_BG, border_color=SEPARATOR_COLOR, border_width=1, text_color=TEXT_PRIMARY)
        textbox.pack(fill="x")
        return textbox

    def _save(self):
        if self.mode and not self.winfo_toplevel().master.can_edit_mode(self.mode):
            return
        name = self.name_entry.get().strip()
        if not name:
            CTkMessagebox(title="Error", message="Mode name is required.", icon="cancel", justify="center")
            return
            
        try:
            focus = int(self.focus_entry.get())
            sessions = int(self.sessions_entry.get())
            short_break = int(self.short_break_entry.get())
            long_break = int(self.long_break_entry.get())
            
            if focus <= 0 or sessions <= 0 or short_break <= 0 or long_break <= 0:
                raise ValueError
        except ValueError:
            CTkMessagebox(title="Error", message="Time and session values must be positive integers.", icon="cancel", justify="center")
            return
            
        sites_text = self.sites_box.get("1.0", "end-1c")
        apps_text = self.apps_box.get("1.0", "end-1c")
        
        sites_list = [s.strip() for s in sites_text.split("\n") if s.strip()]
        apps_list = [a.strip() for a in apps_text.split("\n") if a.strip()]
        
        try:
            target_goal = int(self.target_goal_entry.get().strip() or "4")
        except ValueError:
            CTkMessagebox(title="Invalid daily goal", message="Enter a whole number from 0 to 1440.", icon="cancel")
            return

        from utils.constants import SOUND_TYPES, SOUND_LABELS
        sound_lbl = self.sound_var.get()
        auto_sound = 'none'
        if sound_lbl in self.custom_sounds_map:
            auto_sound = self.custom_sounds_map[sound_lbl]
        else:
            for k, v in SOUND_LABELS.items():
                if v == sound_lbl:
                    auto_sound = k
                    break
                
        new_mode = FocusMode(
            id=self.mode.id if self.mode else None,
            name=name,
            focus_minutes=focus,
            short_break_minutes=short_break,
            long_break_minutes=long_break,
            sessions_before_long_break=sessions,
            blocked_sites=json.dumps(sites_list),
            blocked_apps=json.dumps(apps_list),
            dead_lock=self.dead_lock_var.get(),
            notifications=self.notif_var.get(),
            is_default=self.mode.is_default if self.mode else False,
            auto_flow=self.auto_flow_var.get(),
            whitelist_mode=self.whitelist_var.get(),
            target_goal=target_goal,
            auto_sound=auto_sound,
            auto_sound_volume=self.volume_slider.get()
        )
        
        try:
            if self.mode:
                self.db.update_mode(new_mode)
            else:
                self.db.save_mode(new_mode)
        except (ValueError, sqlite3.Error) as exc:
            CTkMessagebox(title='Could not save mode',message=str(exc),icon='cancel')
            return

        if self.on_save_callback:
            self.on_save_callback()
            
        self.destroy()

class CustomizerView(ctk.CTkScrollableFrame):
    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent, fg_color=BG_PRIMARY)
        self.db = db
        self.on_modes_changed: Callable = None
        
        from ui.panels import PageHeader, surface, label
        self.grid_columnconfigure(0, weight=1)
        header = PageHeader(self, "YOUR WORKING RHYTHM", "Focus Modes",
                            "Different work. Different pace. Find the rhythm that fits.")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 24))
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 16))
        self.mode_count = label(toolbar, "YOUR MODES", 10, TEXT_SECONDARY, True)
        self.mode_count.pack(side="left")
        MaterialButton(toolbar, text="+ New mode", width=132, height=38,
            fg_color=ACCENT_CUSTOM, text_color="white", hover_color=INPUT_BTN_HOVER,
            font=("Inter", 12, "bold"), corner_radius=8, command=self._create_mode).pack(side="right")
        self.list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 22))
        self._mode_cards = []
        self._mode_columns = None
        self.list_frame.bind("<Configure>", self._layout_modes)
        self._parent_canvas.bind('<Configure>',self._layout_modes,add='+')

        self.refresh_modes()

    def _layout_modes(self, event=None):
        # Measure available viewport space, not the requested width of the cards
        # themselves; otherwise a wide two-column layout can prevent collapsing.
        width = self._reverse_widget_scaling(self._parent_canvas.winfo_width())-56
        columns = 2 if width >= 840 else 1
        if columns == self._mode_columns:
            return
        self._mode_columns = columns
        self.list_frame.grid_columnconfigure(0, weight=1, uniform="modes")
        self.list_frame.grid_columnconfigure(1, weight=1 if columns == 2 else 0, uniform="modes" if columns == 2 else "")
        for index, card in enumerate(self._mode_cards):
            card.grid(row=index//columns, column=index%columns, sticky="nsew",
                      padx=(0, 8) if columns == 2 and index%2 == 0 else ((8, 0) if columns == 2 else 0), pady=(0, 16))

    def _create_mode(self):
        ModeDialog(self.winfo_toplevel(), self.db, on_save=self._on_mode_saved)
        
    def _edit_mode(self, mode):
        if not self.winfo_toplevel().can_edit_mode(mode): return
        ModeDialog(self.winfo_toplevel(), self.db, mode=mode, on_save=self._on_mode_saved)
        
    def _delete_mode(self, mode):
        if not self.winfo_toplevel().can_edit_mode(mode): return
        msg = CTkMessagebox(title="Confirm Delete", message=f"Are you sure you want to delete the mode '{mode.name}'?",
                            icon="warning", option_1="Cancel", option_2="Delete", justify="center")
        if msg.get() == "Delete":
            self.db.delete_mode(mode.id)
            self._on_mode_saved()
            
    def _on_mode_saved(self):
        self.refresh_modes()
        if self.on_modes_changed:
            self.on_modes_changed()
            
    def get_mode_names(self) -> list[str]:
        return [mode.name for mode in self.db.get_all_modes()]
        
    def refresh_modes(self):
        from ui.panels import label, surface, rule
        from utils.constants import ICE
        modes = self.db.get_all_modes()
        if getattr(self,'_rendered_modes',None)==modes: return
        self._rendered_modes=modes
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self._mode_cards = []
        self.mode_count.configure(text=f"YOUR MODES  /  {len(modes):02d}")
        for index, mode in enumerate(modes):
            card = surface(self.list_frame)
            self._mode_cards.append(card)
            card.grid_columnconfigure(0, weight=1)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 12))
            top.grid_columnconfigure(0, weight=1)
            label(top, "ESSENTIAL" if mode.is_default else "CUSTOM RHYTHM", 9, ICE, True).grid(row=0, column=0, sticky="w")
            label(top, f"{index+1:02d}", 13, TEXT_MUTED).grid(row=0, column=1, sticky="e")
            title = label(top, mode.name, 20, bold=True, justify="left", wraplength=310)
            title.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
            top.bind("<Configure>", lambda e, t=title: fit_wrap(t,max(200,e.width-15)))

            metrics = ctk.CTkFrame(card, fg_color="transparent")
            metrics.grid(row=1, column=0, sticky="ew", padx=22, pady=(8, 18))
            metrics.grid_columnconfigure((0, 1, 2), weight=1, uniform="timing")
            for col, (caption, minutes) in enumerate((("FOCUS", mode.focus_minutes), ("SHORT BREAK", mode.short_break_minutes), ("LONG BREAK", mode.long_break_minutes))):
                cell = ctk.CTkFrame(metrics, fg_color="transparent")
                cell.grid(row=0, column=col, sticky="ew")
                label(cell, caption, 9, TEXT_SECONDARY, True).pack(anchor="w")
                number = ctk.CTkFrame(cell, fg_color="transparent")
                number.pack(anchor="w", pady=(6, 0))
                label(number, str(minutes), 28, bold=True).pack(side="left")
                label(number, "min", 10, TEXT_SECONDARY).pack(side="left", padx=(5, 0), pady=(10, 0))
            # A restrained timing strip visualizes the work / recovery balance.
            rhythm = ctk.CTkFrame(card, height=4, fg_color="transparent")
            rhythm.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 14))
            for col, value in enumerate((mode.focus_minutes, mode.short_break_minutes, mode.long_break_minutes)):
                rhythm.grid_columnconfigure(col, weight=max(1, value))
                ctk.CTkFrame(rhythm, width=0, height=4, corner_radius=2,
                    fg_color=ACCENT_CUSTOM if col == 0 else (ICE if col == 1 else SEPARATOR_COLOR)).grid(row=0, column=col, sticky="ew", padx=(0, 3))
            label(card, f"Long break after {mode.sessions_before_long_break} focus blocks  ·  Goal {mode.target_goal}",
                  11, TEXT_SECONDARY).grid(row=3, column=0, sticky="w", padx=22, pady=(0, 14))
            rule(card).grid(row=4, column=0, sticky="ew", padx=22)
            footer = ctk.CTkFrame(card, fg_color="transparent")
            footer.grid(row=5, column=0, sticky="ew", padx=22, pady=12)
            footer.grid_columnconfigure(0, weight=1)
            flags = []
            if mode.auto_flow: flags.append("Auto flow")
            if mode.whitelist_mode: flags.append("Whitelist")
            if mode.dead_lock: flags.append("Locked")
            label(footer, " / ".join(flags) or ("Built-in preset" if mode.is_default else "Manual flow"), 10, TEXT_SECONDARY).grid(row=0, column=0, sticky="w")
            if not mode.is_default:
                ctk.CTkButton(footer, text="Edit", width=54, height=28, fg_color=INPUT_BG,
                    text_color=TEXT_PRIMARY, hover_color=HOVER_BG, font=("Inter", 11),
                    command=lambda m=mode: self._edit_mode(m)).grid(row=0, column=1, padx=(8, 4))
                ctk.CTkButton(footer, text="Delete", width=54, height=28, fg_color="transparent",
                    text_color=TEXT_SECONDARY, hover_color=HOVER_BG, font=("Inter", 11),
                    command=lambda m=mode: self._delete_mode(m)).grid(row=0, column=2)
        self._mode_columns = None
        self._layout_modes()

