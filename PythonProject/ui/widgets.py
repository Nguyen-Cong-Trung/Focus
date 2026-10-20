from ui.design import MaterialFrame
from ui.design import MaterialButton
import math
import customtkinter as ctk
from typing import Optional, Callable
from utils.constants import BG_PRIMARY, BG_CARD, ACCENT_FOCUS, ACCENT_STATS, TEXT_PRIMARY, TEXT_SECONDARY, HOVER_BG, TEXT_MUTED, INPUT_BG, resolve_color, SEPARATOR_COLOR, SELECTED_BG, SELECTED_BORDER

class CircularProgressBar(ctk.CTkCanvas):
    """
    A circular progress bar widget that shows time remaining.
    """
    def __init__(self, parent, size: int = 250, width: int = 12, bg_color=BG_PRIMARY, track_color=INPUT_BG, progress_color: str = ACCENT_FOCUS, text_color=TEXT_PRIMARY):
        resolved_bg = resolve_color(bg_color)
        super().__init__(parent, width=size, height=size, bg=resolved_bg, highlightthickness=0)
        self.size = size
        self.width = width
        self.bg_color_raw = bg_color
        self.track_color_raw = track_color
        self.progress_color = progress_color
        self.text_color = text_color
        
        self.time_text = "25:00"
        self.state_text = "READY"
        self.progress = 1.0
        # Canvas geometry is in pixels. Positive Tk font sizes use DPI-scaled points.
        self._font_sizes = {}
        
        self._draw()

    def set_state(self, time_str: str, state_str: str, progress: float):
        self.time_text = time_str
        self.state_text = state_str
        self.progress = progress
        self._draw()

    def set_color(self, progress_color: str):
        """Update the arc color and redraw."""
        self.progress_color = progress_color
        self._draw()

    def _draw(self):
        resolved_bg = resolve_color(self.bg_color_raw)
        resolved_track = resolve_color(self.track_color_raw)
        resolved_prog = resolve_color(self.progress_color)
        resolved_text = resolve_color(self.text_color)
        static_key=(self.size,self.width,resolved_bg,resolved_track,
            resolve_color(TEXT_MUTED),resolve_color(INPUT_BG),ctk.get_appearance_mode())
        draw_key=(static_key,resolved_prog,resolved_text,self.time_text,self.state_text,self.progress)
        if getattr(self,'_draw_key',None)==draw_key: return
        self._draw_key=draw_key
        rebuild=getattr(self,'_static_key',None)!=static_key
        self._static_key=static_key
        if rebuild:
            self.delete('all')
            self.configure(bg=resolved_bg)
        else:
            self.delete('clock-dynamic')
        p = 17
        if rebuild:
            for i in range(60):
                angle = math.radians(i * 6 - 90)
                outer = self.size / 2 - 3
                inner = outer - (7 if i % 5 == 0 else 3)
                self.create_line(self.size/2 + inner*math.cos(angle), self.size/2 + inner*math.sin(angle),
                                 self.size/2 + outer*math.cos(angle), self.size/2 + outer*math.sin(angle),
                                 fill=resolve_color(TEXT_MUTED if i % 5 == 0 else INPUT_BG), width=1,tags='clock-static')
        center = self.size / 2
        radius = self.size / 2 - p
        
        bbox = (p, p, self.size - p, self.size - p)
        
        # Recessed instrument track, with a low shadow and a thin upper rim.
        if rebuild:
            shadow_box = (bbox[0], bbox[1]+3, bbox[2], bbox[3]+3)
            self.create_oval(shadow_box, outline=resolve_color(("#D4D3D0", "#07090C")), width=self.width+6,tags='clock-static')
            self.create_oval(bbox, outline=resolved_track, width=self.width+2,tags='clock-static')
            self.create_arc((bbox[0]-4, bbox[1]-4, bbox[2]+4, bbox[3]+4), start=18, extent=145,
                             style="arc", outline=resolve_color(("#FFFFFF", "#343C49")), width=1,tags='clock-static')
        
        # Draw progress arc
        if self.progress >= 1.0:
            self.create_oval(bbox, outline=resolved_prog, width=self.width,tags='clock-dynamic')
        elif self.progress > 0:
            extent = self.progress * 360
            self.create_arc(
                bbox, start=90, extent=-extent, style="arc", 
                outline=resolved_prog, width=self.width,tags='clock-dynamic'
            )
            
            # Draw small circle dot at the end
            angle = math.radians(90 - extent)
            dot_x = center + radius * math.cos(angle)
            dot_y = center - radius * math.sin(angle)
            dot_radius = self.width * 0.8
            self.create_oval(
                dot_x - dot_radius, dot_y - dot_radius,
                dot_x + dot_radius, dot_y + dot_radius,
                fill=resolved_prog, outline=resolved_prog,tags='clock-dynamic'
            )
            
        # Draw text
        time_item = self.create_text(
            center, center - self.size * 0.06,
            text=self.time_text,
            font=('Inter', -max(1,int(self.size * 0.22)), 'bold'), tags=('timer-time','clock-dynamic'),
            fill=resolved_text,
            justify="center"
        )
        
        state_item = self.create_text(
            center, center + self.size * 0.17,
            text=self.state_text,
            font=('Inter', -max(10,int(self.size * 0.048)), 'bold'), tags=('timer-state','clock-dynamic'),
            fill=resolve_color(TEXT_SECONDARY),
            justify="center"
        )
        safe_radius = max(1, radius - self.width / 2 - 12)
        self._fit_text(time_item, int(self.size * 0.22), center, safe_radius)
        self._fit_text(state_item, max(10, int(self.size * 0.048)), center, safe_radius)

    def _fit_text(self, item, preferred, center, radius):
        """Measure actual glyph bounds, including padding, inside the circular face."""
        key=(self.itemcget(item,'text'),preferred,center,radius)
        if key in self._font_sizes:
            self.itemconfigure(item,font=('Inter',-self._font_sizes[key],'bold'))
            return
        low, high, best = 1, max(1, preferred), 1
        while low <= high:
            pixels = (low + high) // 2
            # Reconfiguring a named Tk font broadcasts world/geometry changes.
            # An immutable font on this canvas item keeps the fit local.
            self.itemconfigure(item, font=('Inter',-pixels,'bold'))
            x0, y0, x1, y1 = self.bbox(item)
            fits = all(math.hypot(x-center, y-center) <= radius
                       for x in (x0, x1) for y in (y0, y1))
            if fits:
                best, low = pixels, pixels + 1
            else:
                high = pixels - 1
        self.itemconfigure(item,font=('Inter',-best,'bold'))
        if len(self._font_sizes)>=256: self._font_sizes.clear()
        self._font_sizes[key]=best

class StatCard(MaterialFrame):
    """
    A card widget showing a stat value with label.
    """
    def __init__(self, parent, title: str, value: str, icon: str = "", accent_color: str = ACCENT_STATS):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=SEPARATOR_COLOR)
        
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        
        # Icon
        from ui.design import nav_icon
        icon_key = "stats" if icon in ("📅", "📈") else "timer"
        self.icon_label = ctk.CTkLabel(self, text="", image=nav_icon(icon_key),
                                      width=36, height=36, fg_color=INPUT_BG, corner_radius=10)
        self.icon_label.grid(row=0, column=0, rowspan=2, padx=(15, 10), pady=15, sticky="w")
        
        # Value
        self.value_label = ctk.CTkLabel(
            self, text=value, font=("Inter", 28, "bold"), text_color=TEXT_PRIMARY
        )
        self.value_label.grid(row=0, column=1, padx=(0, 15), pady=(15, 0), sticky="w")
        
        # Title
        self.title_label = ctk.CTkLabel(
            self, text=title, font=("Inter", 12), text_color=TEXT_SECONDARY
        )
        self.title_label.grid(row=1, column=1, padx=(0, 15), pady=(0, 15), sticky="nw")
        
        # Hover effect
        def on_enter(e):
            self.configure(fg_color=HOVER_BG)
        def on_leave(e):
            self.configure(fg_color=BG_CARD)
            
        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)
        
        for child in self.winfo_children():
            child.bind("<Enter>", on_enter)
            child.bind("<Leave>", on_leave)

    def update_value(self, value: str):
        """Update the value label text."""
        self.value_label.configure(text=value)

class NavButton(ctk.CTkFrame):
    """Quiet outlined navigation with the Paddock red selection rail."""
    def __init__(self, parent, text, icon, command=None, accent_color=ACCENT_FOCUS):
        from ui.design import nav_icon
        super().__init__(parent, fg_color="transparent", height=47)
        self.pack_propagate(False)
        self._icon_key = icon
        self._accent_color = accent_color
        self.indicator = ctk.CTkFrame(self, width=3, fg_color="transparent", corner_radius=2)
        self.indicator.pack(side="left", fill="y", pady=12, padx=(0, 5))
        self.btn = MaterialButton(self, text=text, image=nav_icon(icon), compound="left", anchor="w",
            command=command, fg_color=("#F5F4F2", "#0E131C"), hover_color=HOVER_BG,
            text_color=TEXT_SECONDARY, font=("Inter", 14), corner_radius=10,
            border_width=1, border_color=SEPARATOR_COLOR, height=46)
        self.btn.pack(side="left", fill="both", expand=True)

    def set_active(self, active):
        from ui.design import nav_icon
        self.btn.configure(fg_color=SELECTED_BG if active else ("#F5F4F2", "#0E131C"),
                           border_color=SELECTED_BORDER if active else SEPARATOR_COLOR,
                           text_color=TEXT_PRIMARY if active else TEXT_SECONDARY,
                           image=nav_icon(self._icon_key, active))
        self.indicator.configure(fg_color=self._accent_color if active else "transparent")
