"""Paged focus history with planned and measured time shown separately."""
from ui.metrics import (
    CONTROL_FONT_SIZE, CONTROL_HEIGHT
)
import customtkinter as ctk
from ui.panels import PageHeader, label, surface, rule
from utils.constants import BG_PRIMARY, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, HOVER_BG, ACCENT_CUSTOM, ICE


class HistoryView(ctk.CTkFrame):
    def __init__(self, parent, db):
        super().__init__(parent, fg_color=BG_PRIMARY)
        self.db, self.page, self.outcome = db, 0, 'all'
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(2,weight=1)
        PageHeader(self,'YOUR WORK, RECORDED','Session History',
            'See completed, stopped and skipped sessions. Focused time excludes pauses.').grid(row=0,column=0,sticky='ew',padx=28,pady=(24,20))
        filters=ctk.CTkFrame(self,fg_color='transparent')
        filters.grid(row=1,column=0,sticky='ew',padx=28,pady=(0,16))
        self.filter=ctk.CTkSegmentedButton(filters,values=['All','Completed','Stopped','Skipped'],
            command=self._filter,selected_color=ACCENT_CUSTOM,unselected_color=BG_CARD,
            text_color=TEXT_PRIMARY,font=('Inter',CONTROL_FONT_SIZE),height=CONTROL_HEIGHT)
        self.filter.set('All')
        self.filter.pack(side='left')
        ctk.CTkButton(filters,text='Refresh',width=82,height=CONTROL_HEIGHT,fg_color=BG_CARD,text_color=TEXT_PRIMARY,
            hover_color=HOVER_BG,command=self.refresh, font=("Inter", CONTROL_FONT_SIZE)).pack(side='right')
        table=surface(self)
        table.grid(row=2,column=0,sticky='nsew',padx=28,pady=(0,16))
        table.grid_columnconfigure(0,weight=1)
        table.grid_rowconfigure(2,weight=1)
        headings=ctk.CTkFrame(table,fg_color='transparent')
        headings.grid(row=0,column=0,sticky='ew',padx=18,pady=(16,12))
        self._columns(headings)
        for col,text in enumerate(('STARTED','MODE','OUTCOME','PLAN','FOCUSED')):
            label(headings,text,9,TEXT_SECONDARY,True).grid(row=0,column=col,sticky='w')
        rule(table).grid(row=1,column=0,sticky='ew',padx=18)
        self.rows=ctk.CTkScrollableFrame(table,fg_color='transparent',corner_radius=0)
        self.rows.grid(row=2,column=0,sticky='nsew',padx=12,pady=6)
        self.rows.grid_columnconfigure(0,weight=1)
        footer=ctk.CTkFrame(self,fg_color='transparent')
        footer.grid(row=3,column=0,sticky='ew',padx=28,pady=(0,20))
        self.summary=label(footer,'',11,TEXT_SECONDARY)
        self.summary.pack(side='left')
        self.next_button=ctk.CTkButton(footer,text='Next',width=72,fg_color=BG_CARD,text_color=TEXT_PRIMARY,
            command=lambda:self._page(1), height=CONTROL_HEIGHT, font=("Inter", CONTROL_FONT_SIZE))
        self.next_button.pack(side='right',padx=(8,0))
        self.previous_button=ctk.CTkButton(footer,text='Previous',width=82,fg_color=BG_CARD,text_color=TEXT_PRIMARY,
            command=lambda:self._page(-1), height=CONTROL_HEIGHT, font=("Inter", CONTROL_FONT_SIZE))
        self.previous_button.pack(side='right')

    @staticmethod
    def _columns(row):
        for col,width in enumerate((124,130,86,62,78)):
            row.grid_columnconfigure(col,minsize=width,weight=1 if col==1 else 0)

    def _filter(self, text):
        self.outcome=text.lower()
        self.page=0
        self.refresh()

    def _page(self, delta):
        self.page=max(0,self.page+delta)
        self.refresh()

    def refresh(self):
        sessions=self.db.get_sessions(limit=51,offset=self.page*50,outcome=self.outcome)
        if not sessions and self.page:
            self.page-=1
            return self.refresh()
        signature=(self.page,self.outcome,sessions)
        if getattr(self,'_render_signature',None)==signature: return
        self._render_signature=signature
        for widget in self.rows.winfo_children(): widget.destroy()
        self.previous_button.configure(state='normal' if self.page else 'disabled')
        self.next_button.configure(state='normal' if len(sessions)>50 else 'disabled')
        self.summary.configure(text=f'Page {self.page+1} · Older sessions without measured time show —')
        if not sessions:
            label(self.rows,'No sessions yet.',18,TEXT_SECONDARY).grid(row=0,column=0,pady=50)
            return
        for index,session in enumerate(sessions[:50]):
            row=ctk.CTkFrame(self.rows,fg_color='transparent')
            row.grid(row=index,column=0,sticky='ew',pady=4)
            self._columns(row)
            measured='—'
            if session.elapsed_seconds is not None:
                mins,seconds=divmod(round(session.elapsed_seconds),60)
                measured=f'{mins}m {seconds:02d}s'
            values=(session.start_time.strftime('%d %b  %H:%M') if session.start_time else '—',
                    session.mode_name or 'Earlier session',session.outcome.title(),f'{session.duration_minutes} min',measured)
            for col,text in enumerate(values):
                label(row,text,11,ICE if col==2 and session.completed else TEXT_PRIMARY,
                    wraplength=125 if col==1 else 120,justify='left').grid(row=0,column=col,sticky='w',pady=12)
            rule(row).grid(row=1,column=0,columnspan=5,sticky='ew')
