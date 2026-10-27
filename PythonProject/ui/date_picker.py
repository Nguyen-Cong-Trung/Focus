"""Month calendar with direct month/year navigation and an exact-date shortcut."""
from ui.metrics import (
    CONTROL_FONT_SIZE, CONTROL_HEIGHT, LARGE_CONTROL_HEIGHT
)
import calendar
from datetime import date
import customtkinter as ctk
from ui.design import MaterialButton, set_window_brand
from ui.dropdown import FocusDropdown
from ui.panels import label, surface
from utils.constants import (BG_PRIMARY, BG_CARD, INPUT_BG, HOVER_BG, TEXT_PRIMARY,
    TEXT_SECONDARY, TEXT_MUTED, SEPARATOR_COLOR, ACCENT_CUSTOM, ICE)

MONTHS=('January','February','March','April','May','June','July','August','September','October','November','December')


def bounded_day(value, delta):
    return date.fromordinal(max(date.min.toordinal(),min(date.max.toordinal(),value.toordinal()+delta)))


def shift_month(year, month, delta):
    index=(year-1)*12+month-1+delta
    if not 0 <= index < 9999*12:
        return None
    year,month=divmod(index,12)
    return year+1,month+1


class DatePicker(ctk.CTkToplevel):
    def __init__(self,parent,selected,on_select,store=None):
        super().__init__(parent)
        self.selected,self.on_select,self.store=selected,on_select,store
        self.year,self.month=selected.year,selected.month
        self._previous_grab=parent.grab_current()
        self._activate_job=None
        self.title('Choose a date')
        set_window_brand(self)
        self.configure(fg_color=BG_PRIMARY)
        height=min(660,max(480,int(self._reverse_window_scaling(self.winfo_screenheight()-120))))
        self.geometry(f'480x{height}')
        self.minsize(440,480)
        self.transient(parent.winfo_toplevel())
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        header=ctk.CTkFrame(self,fg_color='transparent')
        header.grid(row=0,column=0,sticky='ew',padx=24,pady=(24,14))
        label(header,'GO STRAIGHT TO YOUR DAY',10,ICE,True).pack(anchor='w')
        label(header,'Choose a date',25,bold=True).pack(anchor='w',pady=(6,4))
        label(header,'Pick a month and year, or enter an exact date.',12,TEXT_SECONDARY).pack(anchor='w')
        body=ctk.CTkScrollableFrame(self,fg_color='transparent',corner_radius=0)
        body.grid(row=1,column=0,sticky='nsew',padx=18)
        body.grid_columnconfigure(0,weight=1)
        navigation=ctk.CTkFrame(body,fg_color='transparent')
        navigation.grid(row=2,column=0,sticky='ew',padx=4,pady=(8,8))
        navigation.grid_columnconfigure(1,weight=1)
        self.previous=self._button(navigation,'‹',lambda:self.move_month(-1),width=32)
        self.previous.grid(row=0,column=0,padx=(0,8))
        self.month_picker=FocusDropdown(navigation,menu_title='MONTH',values=list(MONTHS),
            width=140,command=lambda value:self.change_month())
        self.month_picker.grid(row=0,column=1,sticky='ew',padx=(0,8))
        self.year_entry=ctk.CTkEntry(navigation,width=72,height=LARGE_CONTROL_HEIGHT,fg_color=INPUT_BG,
            border_color=SEPARATOR_COLOR,font=('Inter',CONTROL_FONT_SIZE),justify='center')
        self.year_entry.grid(row=0,column=2,padx=(0,8))
        self.year_entry.bind('<Return>',lambda event:self.change_month())
        self.year_entry.bind('<FocusOut>',lambda event:self.change_month())
        self.next=self._button(navigation,'›',lambda:self.move_month(1),width=32)
        self.next.grid(row=0,column=3)
        label(body,'Type a year and press Enter to jump there.',10,TEXT_MUTED).grid(row=3,column=0,sticky='w',padx=4,pady=(0,10))
        grid=surface(body)
        grid.grid(row=4,column=0,sticky='ew',padx=4)
        for col,name in enumerate(('MON','TUE','WED','THU','FRI','SAT','SUN')):
            grid.grid_columnconfigure(col,weight=1,uniform='calendar_days')
            heading=label(grid,name,9,TEXT_MUTED,True)
            heading.configure(anchor='center')
            heading.grid(row=0,column=col,sticky='ew',pady=(14,8))
        self.cells=[]
        for index in range(42):
            cell=self._button(grid,'',lambda:None,width=1)
            cell.configure(height=36,corner_radius=9)
            cell.grid(row=1+index//7,column=index%7,sticky='ew',padx=3,pady=2)
            self.cells.append(cell)
        label(body,'• Open tasks    ·    Today has an outline',10,TEXT_SECONDARY).grid(row=5,column=0,sticky='w',padx=4,pady=(10,8))
        label(body,'JUMP TO AN EXACT DATE',10,TEXT_SECONDARY,True).grid(row=0,column=0,sticky='w',padx=4,pady=(0,8))
        direct=ctk.CTkFrame(body,fg_color='transparent')
        direct.grid(row=1,column=0,sticky='ew',padx=4,pady=(0,8))
        direct.grid_columnconfigure(0,weight=1)
        self.date_entry=ctk.CTkEntry(direct,placeholder_text='YYYY-MM-DD',height=LARGE_CONTROL_HEIGHT,fg_color=INPUT_BG,
            border_color=SEPARATOR_COLOR,font=('Inter',CONTROL_FONT_SIZE))
        self.date_entry.grid(row=0,column=0,sticky='ew',padx=(0,10))
        self.date_entry.insert(0,selected.isoformat())
        self.date_entry.bind('<Return>',lambda event:self.go_to_date())
        self._button(direct,'Go to date →',self.go_to_date,width=112,primary=True).grid(row=0,column=1)
        self.error=label(self,'',11,ACCENT_CUSTOM,wraplength=410,justify='left')
        self.error.grid(row=2,column=0,sticky='ew',padx=24,pady=(6,0))
        footer=ctk.CTkFrame(self,fg_color='transparent')
        footer.grid(row=3,column=0,sticky='ew',padx=24,pady=(8,20))
        self._button(footer,'Today',lambda:self.choose(date.today()),width=90).pack(side='left')
        self._button(footer,'Cancel',self.destroy,width=90).pack(side='right')
        self.bind('<Escape>',lambda event:self.destroy())
        self.render()
        self._activate_job=self.after(80,self._activate)

    @staticmethod
    def _button(parent,text,command,width,primary=False):
        return MaterialButton(parent,text=text,command=command,width=width,height=CONTROL_HEIGHT,
            fg_color=ACCENT_CUSTOM if primary else INPUT_BG,hover_color=HOVER_BG,
            text_color='white' if primary else TEXT_PRIMARY,font=('Inter',CONTROL_FONT_SIZE))

    def _activate(self):
        if self._activate_job is not None: self.after_cancel(self._activate_job)
        self._activate_job=None
        self.grab_set()
        self.year_entry.focus_set()
        self.year_entry.select_range(0,'end')

    def _read_navigation(self):
        try:
            year=int(self.year_entry.get().strip())
            if not 1<=year<=9999: raise ValueError
        except ValueError:
            self.error.configure(text='Enter a year from 1 to 9999, then press Enter.')
            return None
        return year,MONTHS.index(self.month_picker.get())+1

    def change_month(self):
        target=self._read_navigation()
        if target:
            self.year,self.month=target
            self.render()

    def move_month(self,delta):
        current=self._read_navigation()
        if not current: return
        target=shift_month(*current,delta)
        if target:
            self.year,self.month=target
            self.render()

    def render(self):
        self.error.configure(text='')
        self.month_picker.set(MONTHS[self.month-1])
        self.year_entry.delete(0,'end')
        self.year_entry.insert(0,str(self.year))
        self.previous.configure(state='normal' if shift_month(self.year,self.month,-1) else 'disabled')
        self.next.configure(state='normal' if shift_month(self.year,self.month,1) else 'disabled')
        open_days=set()
        if self.store:
            last=calendar.monthrange(self.year,self.month)[1]
            open_days={task.day for task in self.store.list(date(self.year,self.month,1).isoformat(),
                date(self.year,self.month,last).isoformat()) if not task.completed}
        weeks=calendar.Calendar(firstweekday=0).monthdayscalendar(self.year,self.month)
        numbers=[day for week in weeks for day in week]
        for index,cell in enumerate(self.cells):
            day=numbers[index] if index<len(numbers) else 0
            if not day:
                cell.configure(text='',state='disabled',fg_color='transparent',border_width=0,command=lambda:None)
                continue
            value=date(self.year,self.month,day)
            selected=value==self.selected
            cell.configure(text=str(day)+(' •' if value.isoformat() in open_days else ''),state='normal',
                fg_color=ACCENT_CUSTOM if selected else INPUT_BG,text_color='white' if selected else TEXT_PRIMARY,
                border_width=1 if value==date.today() else 0,border_color=ICE,
                command=lambda chosen=value:self.choose(chosen))

    def go_to_date(self):
        try:
            value=date.fromisoformat(self.date_entry.get().strip())
        except ValueError:
            self.error.configure(text='Enter a valid date, such as 2027-04-15 (YYYY-MM-DD).')
            return
        self.choose(value)

    def choose(self,value):
        self.destroy()
        self.on_select(value)

    def destroy(self):
        if self._activate_job is not None:
            self.after_cancel(self._activate_job)
            self._activate_job=None
        # Close child pickers first so their grab cannot return to a destroyed dialog.
        if hasattr(self,'month_picker'): self.month_picker._close_picker()
        self.grab_release()
        previous=self._previous_grab
        self._previous_grab=None
        super().destroy()
        if previous is not None and previous.winfo_exists(): previous.grab_set()
