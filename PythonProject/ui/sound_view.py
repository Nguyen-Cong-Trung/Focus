from ui.design import MaterialFrame
from ui.panels import fit_wrap
from ui.design import MaterialButton
from utils.constants import SEPARATOR_COLOR, INPUT_BG, TEXT_PRIMARY, ACCENT_CUSTOM
import customtkinter as ctk
from utils.constants import BG_PRIMARY, BG_CARD, ACCENT_SOUND, ACCENT_HOVER_SOUND, SOUND_LABELS, SOUND_DESCRIPTIONS, TEXT_SECONDARY, HOVER_BG, ACCENT_DANGER, ACCENT_HOVER_DARK
from core.sound_engine import SoundEngine

class SoundCard(MaterialFrame):
    def __init__(self, parent, sound_type: str, sound_engine: SoundEngine, custom_name: str = None, custom_icon: str = None, custom_path: str = None):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=SEPARATOR_COLOR)
        self.sound_type = sound_type
        self.sound_engine = sound_engine
        self.custom_path = custom_path
        self._is_playing = False
        
        self.grid_columnconfigure(0, weight=1)
        
        icons = {
            "432hz_focus": "🎵",
            "binaural_alpha": "🎧",
            "binaural_gamma": "⚡",
            "brown_noise": "🌊",
            "pink_noise": "◌",
            "white_noise": "≋",
            "rain": "🌧"
        }
        icon = custom_icon if custom_icon else icons.get(sound_type, "🎵")
        
        # Hover effect
        def on_enter(e):
            self.configure(fg_color=HOVER_BG)
        def on_leave(e):
            self.configure(fg_color=BG_CARD)
            
        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)
        
        # Icon
        self.icon_label = ctk.CTkLabel(self, text=icon, font=("Inter", 36))
        self.icon_label.grid(row=0, column=0, pady=(20, 5))
        self.icon_label.bind("<Enter>", on_enter)
        self.icon_label.bind("<Leave>", on_leave)
        
        # Label
        label_text = custom_name if custom_name else SOUND_LABELS.get(sound_type, sound_type)
        self.name_label = ctk.CTkLabel(self, text=label_text, font=("Inter", 14, "bold"), height=28, corner_radius=0, wraplength=210)
        self.name_label.grid(row=1, column=0, pady=(0, 4), padx=18)
        self.name_label.bind("<Enter>", on_enter)
        self.name_label.bind("<Leave>", on_leave)

        self.description_label = ctk.CTkLabel(self,
            text=SOUND_DESCRIPTIONS.get(sound_type, 'Your imported WAV recording.'),
            font=('Inter', 11), text_color=TEXT_SECONDARY, height=50,
            corner_radius=0, wraplength=210, justify='center')
        self.description_label.grid(row=2, column=0, sticky='ew', padx=18, pady=(0, 12))
        def fit_description(event):
            available = max(100, self._reverse_widget_scaling(event.width) - 36)
            fit_wrap(self.name_label, available)
            fit_wrap(self.description_label, available)
        self.bind('<Configure>', fit_description, add='+')
        
        # Toggle Button
        self.toggle_btn = MaterialButton(
            self, text="▶ Play", fg_color=ACCENT_SOUND, hover_color=ACCENT_HOVER_SOUND, font=("Inter", 14, "bold"),
            command=self._toggle_play, height=35
        )
        self.toggle_btn.grid(row=3, column=0, pady=(0, 15), padx=20, sticky="ew")
        
        # Volume Slider
        self.vol_slider = ctk.CTkSlider(self, from_=0, to=100, command=self._on_volume_change, button_color=ACCENT_SOUND, progress_color=ACCENT_SOUND)
        self.vol_slider.set(50)
        self.vol_slider.grid(row=4, column=0, pady=(0, 5), padx=20, sticky="ew")
        
        # Volume Label
        self.vol_label = ctk.CTkLabel(self, text="50%", font=("Inter", 12), text_color=TEXT_SECONDARY)
        self.vol_label.grid(row=5, column=0, pady=(0, 15))
        self.vol_label.bind("<Enter>", on_enter)
        self.vol_label.bind("<Leave>", on_leave)

    def sync_playback(self):
        if getattr(self,'_pending',False): return
        self._is_playing = self.sound_engine.is_playing(self.sound_type)
        previous=getattr(self,'_playback_snapshot',None)
        volume=self.sound_engine.get_volume(self.sound_type)*100 if self._is_playing else None
        snapshot=(self._is_playing,volume)
        if previous==snapshot: return
        if previous is None or previous[0]!=self._is_playing:
            self.toggle_btn.configure(text='⏹ Stop' if self._is_playing else '▶ Play',
                fg_color=ACCENT_DANGER if self._is_playing else ACCENT_SOUND,
                hover_color=ACCENT_HOVER_DARK if self._is_playing else ACCENT_HOVER_SOUND)
        if self._is_playing:
            if abs(self.vol_slider.get()-volume)>.001: self.vol_slider.set(volume)
            text=f'{round(volume)}%'
            if self.vol_label.cget('text')!=text: self.vol_label.configure(text=text)
        self._playback_snapshot=snapshot

    def _toggle_play(self, stop_only=False):
        if getattr(self,'_pending',False): return
        app = self.winfo_toplevel()
        if app._restoring or app._closing: return
        self._pending = True
        self.toggle_btn.configure(state='disabled',text='Preparing…')
        self.vol_slider.configure(state='disabled')
        playing = stop_only or self.sound_engine.is_playing(self.sound_type)
        token = self.sound_engine.generation
        volume = self.vol_slider.get()/100
        def run():
            if playing: self.sound_engine.stop(self.sound_type)
            else: self.sound_engine.play(self.sound_type,volume,file_path=self.custom_path, generation=token)
        def finish(error=None):
            if not self.winfo_exists(): return
            self._pending = False
            self._playback_snapshot = None
            self.toggle_btn.configure(state='normal')
            self.vol_slider.configure(state='normal')
            self.sync_playback()
            if error: app.report_error('Audio could not start: '+str(error))
        app.run_background(run,lambda _:finish(),lambda exc:finish(exc),lane='audio')

    def _on_volume_change(self, value):
        val_int = int(value)
        self.vol_label.configure(text=f"{val_int}%")
        if self._is_playing:
            self.sound_engine.set_volume(self.sound_type, val_int / 100.0)

    def stop(self):
        self._toggle_play(stop_only=True)

class SoundView(ctk.CTkFrame):
    def __init__(self, parent, sound_engine: SoundEngine, db=None):
        super().__init__(parent, fg_color=BG_PRIMARY)
        self.sound_engine = sound_engine
        self.db = db

        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Title
        title_frame = ctk.CTkFrame(self, fg_color=BG_PRIMARY)
        title_frame.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 8))
        self.stop_all_button = MaterialButton(title_frame, text='Stop all sounds', width=136, height=36,
            fg_color=INPUT_BG, hover_color=HOVER_BG, text_color=TEXT_PRIMARY,
            command=lambda: self.winfo_toplevel().stop_all_sounds())
        self.stop_all_button.pack(side='right', padx=(16, 0))
        
        ctk.CTkLabel(title_frame, text="Sound Studio", font=("Inter", 28, "bold")).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Choose sounds to create a focused workspace", text_color=TEXT_SECONDARY).pack(anchor="w")
        
        from ui.panels import surface, label
        self.content_frame = ctk.CTkScrollableFrame(self, fg_color=BG_PRIMARY, corner_radius=0)
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(12, 20))
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.cards_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.cards_frame.grid(row=0, column=0, sticky="ew")
        self.cards = []
        self._sound_columns = None
        self._refresh_cards()
        self.cards_frame.bind("<Configure>", self._layout_cards, add="+")
        self.content_frame._parent_canvas.bind('<Configure>',self._layout_cards,add='+')

        sound_section = surface(self.content_frame)
        sound_section.grid(row=1, column=0, sticky="ew", padx=8, pady=(18, 8))
        sound_section.grid_columnconfigure(0, weight=1)
        sound_header = ctk.CTkFrame(sound_section, fg_color="transparent")
        sound_header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 16))
        sound_header.grid_columnconfigure(0, weight=1)
        label(sound_header, "Your sound library", 17, bold=True).grid(row=0, column=0, sticky="w")
        detail = label(sound_header, "Bring your own atmosphere. Import a WAV recording.", 12, TEXT_SECONDARY, justify="left")
        detail.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ctk.CTkButton(sound_header, text="Import WAV", width=116, height=34,
            fg_color=INPUT_BG, text_color=TEXT_PRIMARY, hover_color=HOVER_BG,
            font=("Inter", 12), command=self._import_sound).grid(row=0, column=1, rowspan=2, padx=(16, 0))
        sound_header.bind("<Configure>", lambda e: fit_wrap(detail,max(200,e.width-150)))
        self.sound_list_frame = ctk.CTkFrame(sound_section, fg_color="transparent")
        self.sound_list_frame.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 18))
        self.sound_list_frame.grid_columnconfigure(0, weight=1)
        self.refresh_sounds()
        
    def _refresh_cards(self):
        volumes = {card.sound_type: card.vol_slider.get() for card in self.cards}
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self.cards.clear()
        self._sound_columns = None
        
        from utils.constants import SOUND_TYPES as CONST_SOUND_TYPES
        
        sound_items = [(st, None, None, None) for st in CONST_SOUND_TYPES]
        
        if self.db:
            custom_sounds = self.db.get_all_custom_sounds()
            for cs in custom_sounds:
                sound_items.append((f"custom_{cs.id}", cs.name, cs.icon, cs.file_path))
                
        cols = 3 if self.cards_frame.winfo_width() >= 960 else 2
        for c in range(cols):
            self.cards_frame.grid_columnconfigure(c, weight=1, uniform="col")
            
        for i, (stype, c_name, c_icon, c_path) in enumerate(sound_items):
            card = SoundCard(self.cards_frame, stype, self.sound_engine, custom_name=c_name, custom_icon=c_icon, custom_path=c_path)
            row = i // cols
            col = i % cols
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            volume = volumes.get(stype, 50)
            card.vol_slider.set(volume)
            card.vol_label.configure(text=f"{int(volume)}%")
            card._is_playing = self.sound_engine.is_playing(stype)
            if card._is_playing:
                card.toggle_btn.configure(text="⏹ Stop", fg_color=ACCENT_DANGER, hover_color=ACCENT_HOVER_DARK)
            self.cards.append(card)

    def _layout_cards(self, event=None):
        width=self._reverse_widget_scaling(self.content_frame._parent_canvas.winfo_width())
        columns = 3 if width >= 960 else 2
        if self._sound_columns == columns:
            return
        self._sound_columns = columns
        for i in range(3):
            self.cards_frame.grid_columnconfigure(i, weight=1 if i < columns else 0, uniform="col" if i < columns else "")
        for i, card in enumerate(self.cards):
            card.grid_configure(row=i // columns, column=i % columns, padx=8, pady=8, sticky="nsew")

    def refresh_playback(self):
        for card in self.cards: card.sync_playback()

    def _library(self):
        from core.audio_library import AudioLibrary
        from pathlib import Path
        return AudioLibrary(self.db, Path(self.db.db_path).parent/'sounds')

    def _import_sound(self):
        from tkinter import filedialog
        app = self.winfo_toplevel()
        if app._restoring or app._closing: return
        path = filedialog.askopenfilename(title='Select PCM WAV file',filetypes=[('PCM WAV audio','*.wav')])
        if not path: return
        def done(_):
            self.refresh_sounds()
            self._refresh_cards()
        app.run_background(lambda:self._library().import_file(path),done)

    def refresh_sounds(self):
        for widget in self.sound_list_frame.winfo_children():
            widget.destroy()
            
        sounds = self.db.get_all_custom_sounds() if self.db else []
        if not sounds:
            lbl = ctk.CTkLabel(self.sound_list_frame, text="Your personal sound collection starts here.", text_color=TEXT_SECONDARY)
            lbl.grid(row=0, column=0, pady=20)
            return
            
        for i, sound in enumerate(sounds):
            self._create_sound_row(sound, i)
            
    def _create_sound_row(self, sound, row_idx):
        from CTkMessagebox import CTkMessagebox
        row = ctk.CTkFrame(self.sound_list_frame, fg_color="transparent")
        row.grid(row=row_idx * 2, column=0, sticky="ew", padx=12, pady=6)
        row.grid_columnconfigure(1, weight=1)
        
        icon_entry = ctk.CTkEntry(row, width=40, fg_color=INPUT_BG, border_width=1, border_color=SEPARATOR_COLOR)
        icon_entry.insert(0, sound.icon)
        icon_entry.grid(row=0, column=0, padx=(0, 10))
        
        name_entry = ctk.CTkEntry(row, fg_color=INPUT_BG, border_width=1, border_color=SEPARATOR_COLOR)
        name_entry.insert(0, sound.name)
        name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        def save_changes(s=sound, i_e=icon_entry, n_e=name_entry):
            s.icon = i_e.get()
            s.name = n_e.get()
            try:
                self.db.update_custom_sound(s)
            except ValueError as exc:
                CTkMessagebox(title="Could not rename sound",message=str(exc),icon="cancel")
                return
            CTkMessagebox(title="Success", message="Sound updated!", icon="check", option_1="OK")
            self._notify_app_sounds()
            
        save_btn = MaterialButton(row, text="Save", width=60, fg_color="transparent", border_width=1, border_color=ACCENT_CUSTOM, text_color=TEXT_PRIMARY, command=save_changes)
        save_btn.grid(row=0, column=2, padx=(0, 10))
        
        def delete_sound(s=sound):
            app = self.winfo_toplevel()
            if app._restoring or app._closing: return
            mode = app.active_mode()
            if mode and mode.auto_sound==f'custom_{s.id}' and not app.can_edit_mode(mode): return
            answer=CTkMessagebox(title='Remove recording',message='Remove this recording and detach it from any modes that use it?',
                icon='warning',option_1='Keep recording',option_2='Remove recording')
            if answer.get()!='Remove recording': return
            def run():
                self.sound_engine.forget(f'custom_{s.id}')
                self._library().remove(s)
            def done(_):
                self.refresh_sounds()
                self._notify_app_sounds()
                app._on_modes_changed()
            app.run_background(run,done,lane='audio')

        del_btn = MaterialButton(row, text="Remove", width=68, fg_color="transparent", text_color=ACCENT_DANGER, hover_color=HOVER_BG, command=delete_sound)
        del_btn.grid(row=0, column=3)
        
        # Separator
        sep = ctk.CTkFrame(self.sound_list_frame, height=1, fg_color=SEPARATOR_COLOR)
        sep.grid(row=row_idx * 2 + 1, column=0, sticky="ew", padx=12, pady=6)
        
    def _notify_app_sounds(self):
        self._refresh_cards()
