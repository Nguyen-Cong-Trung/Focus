from ui.metrics import (
    CONTROL_FONT_SIZE, CONTROL_HEIGHT
)
from ui.design import MaterialFrame
from ui.design import MaterialButton
from utils.constants import SEPARATOR_COLOR
import customtkinter as ctk
from utils.constants import BG_PRIMARY, BG_SECONDARY, BG_CARD, ACCENT_STATS, TEXT_PRIMARY, TEXT_SECONDARY, resolve_color, ACCENT_FOCUS, ACCENT_BREAK, SEPARATOR_COLOR
from data.database import DatabaseManager
from ui.widgets import StatCard

class StatsView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent, fg_color=BG_PRIMARY)
        self.db = db
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Title
        title_frame = ctk.CTkFrame(self, fg_color=BG_PRIMARY)
        title_frame.grid(row=0, column=0, sticky="nw", padx=28, pady=(24, 12))
        
        title_label = ctk.CTkLabel(title_frame, text="Productivity Statistics", font=("Inter", 28, "bold"))
        title_label.pack(side="left")
        
        # Stat cards
        cards_frame = ctk.CTkFrame(self, fg_color=BG_PRIMARY)
        cards_frame.grid(row=1, column=0, sticky="ew", padx=22, pady=10)
        
        for i in range(4):
            cards_frame.grid_columnconfigure(i, weight=1, uniform="col")
            
        self.total_hours_card = StatCard(cards_frame, title="Total Focus Time", value="0.0h", icon="🕐", accent_color=ACCENT_STATS)
        self.total_hours_card.grid(row=0, column=0, padx=5, sticky="ew")
        
        self.sessions_card = StatCard(cards_frame, title="Sessions Today", value="0", icon="📅", accent_color=ACCENT_FOCUS)
        self.sessions_card.grid(row=0, column=1, padx=5, sticky="ew")
        
        self.streak_card = StatCard(cards_frame, title="Day Streak", value="0", icon="🔥", accent_color=ACCENT_FOCUS)
        self.streak_card.grid(row=0, column=2, padx=5, sticky="ew")
        
        self.avg_hours_card = StatCard(cards_frame, title="Daily Average", value="0.0h", icon="📈", accent_color=ACCENT_BREAK)
        self.avg_hours_card.grid(row=0, column=3, padx=5, sticky="ew")
        
        # Chart
        self.chart_frame = MaterialFrame(self, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=SEPARATOR_COLOR)
        self.chart_frame.grid(row=2, column=0, sticky="nsew", padx=28, pady=15)
        
        # Bottom controls
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 20))
        
        refresh_btn = MaterialButton(bottom_frame, text="🔄 Refresh", command=self.refresh_stats, fg_color=BG_CARD, text_color=TEXT_PRIMARY, height=CONTROL_HEIGHT, font=("Inter", CONTROL_FONT_SIZE))
        refresh_btn.pack(side="right")
        
        self._chart_canvas = None
        self._stat_cards = (self.total_hours_card, self.sessions_card, self.streak_card, self.avg_hours_card)
        self._cards_frame = cards_frame
        self._stat_columns = None
        cards_frame.bind("<Configure>", self._layout_cards)

    def _layout_cards(self, event):
        columns = 4 if self._reverse_widget_scaling(event.width) >= 960 else 2
        if self._stat_columns == columns:
            return
        self._stat_columns = columns
        for i in range(4):
            self._cards_frame.grid_columnconfigure(i, weight=1 if i < columns else 0, uniform="col" if i < columns else "")
        for i, card in enumerate(self._stat_cards):
            card.grid_configure(row=i // columns, column=i % columns, padx=6, pady=6, sticky="ew")

    def refresh_stats(self):
        total_hours = self.db.get_total_focus_hours()
        today = self.db.get_today_stats()
        streak = self.db.get_streak()
        weekly = self.db.get_weekly_stats()
        
        self.total_hours_card.update_value(f"{total_hours * 60:.1f} min" if 0 < total_hours < 0.1 else f"{total_hours:.1f}h")
        self.sessions_card.update_value(str(today.completed_sessions))
        self.streak_card.update_value(str(streak))
        
        # Calculate average hours per day from weekly data
        total_weekly_hours = sum(s.focus_hours for s in weekly)
        days_with_data = sum(1 for s in weekly if s.total_focus_minutes > 0)
        avg = total_weekly_hours / max(days_with_data, 1)
        self.avg_hours_card.update_value(f"{avg * 60:.1f} min" if 0 < avg < 0.1 else f"{avg:.1f}h")
        
        self._draw_weekly_chart(weekly)

    def _draw_weekly_chart(self, stats=None):
        import tkinter as tk
        self._chart_stats = stats if stats is not None else self.db.get_weekly_stats()
        if self._chart_canvas is None:
            self._chart_canvas = tk.Canvas(self.chart_frame, highlightthickness=0,
                                     bg=resolve_color(BG_CARD), height=280)
            self._chart_canvas.pack(expand=True, fill="both", padx=28, pady=20)
            self._chart_canvas.bind("<Configure>", self._paint_chart)
        self._paint_chart()

    def _paint_chart(self, event=None):
        canvas = self._chart_canvas
        w, h = max(canvas.winfo_width(), 200), max(canvas.winfo_height(), 160)
        key=(w,h,ctk.get_appearance_mode(),self._chart_stats)
        if getattr(self,'_chart_paint_key',None)==key: return
        self._chart_paint_key=key
        canvas.delete("all")
        canvas.configure(bg=resolve_color(BG_CARD))
        left, top, bottom = 45, 40, h - 35
        right = w - 20
        stats = self._chart_stats
        peak_hours = max((s.focus_hours for s in stats), default=0)
        minutes = 0 < peak_hours < 1
        values = [day.total_focus_minutes if minutes else day.focus_hours for day in stats]
        import math
        maximum = max(5, math.ceil(max(values, default=0) / 5) * 5) if minutes else max(1, peak_hours)
        chart_title = 'Focus minutes' if minutes else 'Focus hours' 
        canvas.create_text(left, 12, anchor="w", text=chart_title + " · Last 7 days",
                           fill=resolve_color(TEXT_PRIMARY), font=("Inter", 12, "bold"))
        for i in range(5):
            value = maximum * i / 4
            y = bottom - (bottom - top) * i / 4
            canvas.create_line(left, y, right, y, fill=resolve_color(SEPARATOR_COLOR))
            canvas.create_text(left - 10, y, anchor="e", text=f"{value:.1f}",
                               fill=resolve_color(TEXT_SECONDARY), font=("Inter", 10))
        slot = (right - left) / max(1, len(stats))
        for i, day in enumerate(stats):
            x = left + slot * (i + 0.5)
            y = bottom - (bottom - top) * values[i] / maximum
            half = min(22, slot * 0.27)
            canvas.create_rectangle(x-half, y, x+half, bottom,
                                    fill=resolve_color(ACCENT_FOCUS), outline="")
            canvas.create_text(x, bottom + 18, text=day.date[-5:],
                               fill=resolve_color(TEXT_SECONDARY), font=("Inter", 10))
        if not any(day.total_focus_minutes for day in stats):
            canvas.create_text((left+right)/2, (top+bottom)/2, text="Your next focus session starts the story.",
                               fill=resolve_color(TEXT_SECONDARY), font=("Inter", 12))
