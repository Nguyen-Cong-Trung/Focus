"""A weekly date strip and a calm, actionable daily agenda."""
from ui.metrics import (
    COMPACT_CONTROL_HEIGHT, COMPACT_FONT_SIZE, CONTROL_FONT_SIZE, CONTROL_HEIGHT, LARGE_CONTROL_HEIGHT
)
from dataclasses import replace
from datetime import date, datetime, timedelta
import sqlite3
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from core.planner import PlannerStore, PlanTask
from ui.panels import PageHeader, label, surface, fit_wrap
from ui.design import MaterialButton, set_window_brand
from ui.dropdown import FocusDropdown
from ui.date_picker import DatePicker, bounded_day, MONTHS
from utils.constants import (BG_PRIMARY, BG_CARD, INPUT_BG, HOVER_BG, TEXT_PRIMARY,
    TEXT_SECONDARY, TEXT_MUTED, SEPARATOR_COLOR, ACCENT_CUSTOM, ICE, TimerState)


def button(parent, text, command, primary=False, **kwargs):
    return MaterialButton(parent, text=text, command=command, height=CONTROL_HEIGHT,
        fg_color=ACCENT_CUSTOM if primary else INPUT_BG, hover_color=HOVER_BG,
        text_color='white' if primary else TEXT_PRIMARY, font=('Inter',CONTROL_FONT_SIZE), **kwargs)


class PlannerView(ctk.CTkFrame):
    def __init__(self, parent, db):
        super().__init__(parent, fg_color=BG_PRIMARY)
        self.db = db
        self.selected_day = date.today()
        self.filter_value = 'All'
        self.expanded = set()
        self._refreshing = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        PageHeader(self,'MAKE ROOM FOR WHAT MATTERS','Planner',
            'Plan your day. Break work into small steps. Make space to focus.').grid(
                row=0,column=0,sticky='ew',padx=28,pady=(22,16))

        navigation=ctk.CTkFrame(self,fg_color='transparent')
        navigation.grid(row=1,column=0,sticky='ew',padx=28,pady=(0,10))
        navigation.grid_columnconfigure(0,weight=1)
        self.month_label=button(navigation,'',self.open_date_picker,width=224)
        self.month_label.configure(font=('Inter',17,'bold'),anchor='w',fg_color=BG_CARD)
        self.month_label.grid(row=0,column=0,sticky='w')
        button(navigation,'‹',lambda:self.shift_week(-1),width=34).grid(row=0,column=1,padx=(6,0))
        button(navigation,'Today',self.today,width=64).grid(row=0,column=2,padx=6)
        button(navigation,'›',lambda:self.shift_week(1),width=34).grid(row=0,column=3)
        self.week=ctk.CTkFrame(self,fg_color='transparent')
        self.week.grid(row=2,column=0,sticky='ew',padx=28,pady=(0,14))
        self.day_buttons=[]
        for column in range(7):
            self.week.grid_columnconfigure(column,weight=1,uniform='days')
            day_button=button(self.week,'',lambda i=column:self.select_day(self.week_start+timedelta(days=i)),width=1)
            day_button.configure(height=64,corner_radius=12)
            day_button.grid(row=0,column=column,sticky='ew',padx=(0,6) if column<6 else 0)
            self.day_buttons.append(day_button)

        overview=surface(self)
        overview.grid(row=3,column=0,sticky='ew',padx=28,pady=(0,14))
        for i in range(3): overview.grid_columnconfigure(i,weight=1,uniform='metrics')
        self.metrics=[]
        for col,caption in enumerate(('TASKS FINISHED','TIME PLANNED','NEXT ON YOUR PLAN')):
            frame=ctk.CTkFrame(overview,fg_color='transparent')
            frame.grid(row=0,column=col,sticky='nsew',padx=16,pady=(16,10))
            label(frame,caption,9,TEXT_SECONDARY,True).pack(anchor='w')
            value=label(frame,'—',20,bold=True)
            value.pack(anchor='w',pady=(5,0))
            self.metrics.append(value)
        self.progress=ctk.CTkProgressBar(overview,height=4,progress_color=ACCENT_CUSTOM,fg_color=INPUT_BG)
        self.progress.grid(row=1,column=0,columnspan=3,sticky='ew',padx=16,pady=(0,16))

        controls=ctk.CTkFrame(self,fg_color='transparent')
        controls.grid(row=4,column=0,sticky='ew',padx=28,pady=(0,12))
        controls.grid_columnconfigure(0,weight=1)
        self.quick_entry=ctk.CTkEntry(controls,placeholder_text='Add a task for this day…',height=LARGE_CONTROL_HEIGHT,
            fg_color=INPUT_BG,border_width=1,border_color=SEPARATOR_COLOR,font=('Inter',CONTROL_FONT_SIZE))
        self.quick_entry.grid(row=0,column=0,sticky='ew',padx=(0,8))
        self.quick_entry.bind('<Return>',lambda event:self.quick_add())
        button(controls,'+ Add',self.quick_add,True,width=78).grid(row=0,column=1)
        button(controls,'Plan task',self.new_task,width=96).grid(row=0,column=2,padx=(8,0))
        self.day_label=label(controls,'',12,TEXT_SECONDARY)
        self.day_label.grid(row=1,column=0,sticky='w',pady=(14,0))
        self.filter=ctk.CTkSegmentedButton(controls,values=['All','Open','Done'],height=COMPACT_CONTROL_HEIGHT,
            selected_color=ACCENT_CUSTOM,unselected_color=BG_CARD,text_color=TEXT_PRIMARY,
            font=('Inter',COMPACT_FONT_SIZE),command=self.set_filter)
        self.filter.set('All')
        self.filter.grid(row=1,column=1,columnspan=2,sticky='e',pady=(14,0))
        self.rows=ctk.CTkScrollableFrame(self,fg_color='transparent',corner_radius=0)
        self.rows.grid(row=5,column=0,sticky='nsew',padx=(22,20),pady=(0,6))
        self.rows.grid_columnconfigure(0,weight=1)
        label(self,'Reminders work while Focus is open, including in the system tray.',10,TEXT_MUTED).grid(
            row=6,column=0,sticky='w',padx=28,pady=(0,12))
        self.refresh()

    @property
    def store(self):
        return PlannerStore(self.db)

    def _allowed(self):
        app=self.winfo_toplevel()
        return not (app._closing or app._restoring)

    def select_day(self, day):
        self.selected_day=day
        self.expanded.clear()
        self.refresh()
        self.rows._parent_canvas.yview_moveto(0)

    def today(self):
        self.select_day(date.today())

    def open_date_picker(self):
        if self._allowed():
            return DatePicker(self,self.selected_day,self.select_day,self.store)

    def shift_week(self, delta):
        try: self.select_day(self.selected_day+timedelta(days=7*delta))
        except OverflowError: pass

    def set_filter(self, value):
        self.filter_value=value
        self.refresh()

    def quick_add(self):
        if not self._allowed(): return
        title=self.quick_entry.get().strip()
        if not title:
            self.new_task()
            return
        try:
            self.store.save(PlanTask(title=title,day=self.selected_day.isoformat()))
        except (ValueError,sqlite3.Error) as error:
            self._error(error)
            return
        self.quick_entry.delete(0,'end')
        self.refresh()
        self.quick_entry.focus_set()

    def _error(self, error):
        CTkMessagebox(title='Planner',message=str(error),icon='warning')

    def new_task(self):
        if self._allowed(): TaskDialog(self,self.db,PlanTask(day=self.selected_day.isoformat()),self.refresh)

    def edit_task(self, ident):
        if not self._allowed(): return
        task=self.store.get(ident)
        if task: TaskDialog(self,self.db,task,self.refresh)

    def toggle(self, ident, completed):
        if not self._allowed(): return
        self.store.complete(ident,completed)
        self.refresh()

    def toggle_step(self, ident, index, completed):
        if not self._allowed(): return
        self.store.step(ident,index,completed)
        self.refresh()

    def expand(self, ident):
        if ident in self.expanded: self.expanded.remove(ident)
        else: self.expanded.add(ident)
        self.refresh()

    def start_focus(self, ident):
        if not self._allowed(): return
        task=self.store.get(ident)
        if not task or task.completed: return
        app=self.winfo_toplevel()
        if app.timer_engine.state != TimerState.IDLE:
            self._error('Finish or stop the current timer before focusing on another task.')
            return
        mode=self.db.get_mode(task.mode_id) if task.mode_id else app.active_mode()
        if not mode:
            self._error('The linked Focus Mode was removed. Edit this task to choose another mode.')
            return
        app._on_mode_selected(mode.name)
        app.show_view('timer')
        app.views['timer'].set_planned_task(task.title)
        app.timer_engine.start_focus()

    def refresh(self):
        if self._refreshing: return
        self._refreshing=True
        try: self._render()
        finally: self._refreshing=False

    def _render(self):
        self.week_start=self.selected_day-timedelta(days=self.selected_day.weekday())
        week_tasks=self.store.list(self.week_start.isoformat(),bounded_day(self.week_start,6).isoformat())
        now=datetime.now()
        neighbours=self.store.list(bounded_day(self.selected_day,-1).isoformat(),
            bounded_day(self.selected_day,1).isoformat())
        modes=self.db.get_all_modes()
        signature=(self.selected_day,self.filter_value,frozenset(self.expanded),
            now.strftime('%Y-%m-%d %H:%M'),week_tasks,neighbours,modes)
        if getattr(self,'_render_signature',None)==signature: return
        for index,day_button in enumerate(self.day_buttons):
            if self.week_start.toordinal()+index>date.max.toordinal():
                day_button.configure(text='',state='disabled',fg_color=BG_CARD,border_width=0)
                continue
            day=self.week_start+timedelta(days=index)
            count=sum(t.day==day.isoformat() and not t.completed for t in week_tasks)
            selected=day==self.selected_day
            day_button.configure(text=f'{day:%a}   {day.day}\n'+(f'{count} open' if count else 'Clear'),state='normal',
                fg_color=ACCENT_CUSTOM if selected else BG_CARD,text_color='white' if selected else TEXT_SECONDARY,
                border_width=1 if day==date.today() else 0,border_color=ICE)
        self.month_label.configure(text=f'{MONTHS[self.selected_day.month-1]} {self.selected_day.year}  ▾')
        tasks=[t for t in week_tasks if t.day==self.selected_day.isoformat()]
        done=sum(t.completed for t in tasks)
        self.metrics[0].configure(text=f'{done} / {len(tasks)}')
        minutes=sum(t.minutes for t in tasks)
        self.metrics[1].configure(text=f'{minutes//60}h {minutes%60:02d}m' if minutes>=60 else f'{minutes} min')
        next_task=next((t for t in tasks if not t.completed and t.start_time and
            datetime.fromisoformat(f'{t.day}T{t.start_time}')>=now),None)
        overdue=next((t for t in tasks if not t.completed and t.start_time and
            datetime.fromisoformat(f'{t.day}T{t.start_time}')<now),None)
        self.metrics[2].configure(text=next_task.start_time if next_task else
            overdue.start_time+' · overdue' if overdue else 'Anytime' if any(not t.completed for t in tasks) else 'All clear')
        self.progress.set(done/len(tasks) if tasks else 0)
        self.day_label.configure(text=('Today' if self.selected_day==date.today() else self.selected_day.strftime('%A'))+
            self.selected_day.strftime(' · %d %b')+f' · {len(tasks)-done} open')
        # Include neighbouring days so a late block crossing midnight is flagged too.
        overlaps=self.store.conflicts(neighbours)
        self._modes={mode.id:mode for mode in modes}
        self._render_signature=signature
        for widget in self.rows.winfo_children(): widget.destroy()
        visible=[t for t in tasks if self.filter_value=='All' or t.completed==(self.filter_value=='Done')]
        if not visible:
            empty=surface(self.rows)
            empty.grid(row=0,column=0,sticky='ew',pady=4)
            label(empty,'A little space to think.',21,bold=True).pack(pady=(34,8))
            label(empty,'Add your first task above, or plan a focus block with “Plan task”.' if not tasks else
                'Nothing in this filter. Switch to All to see your day.',12,TEXT_SECONDARY,wraplength=410,justify='center').pack(padx=24,pady=(0,32))
            return
        last_group=None
        row_index=0
        for task in visible:
            group='COMPLETED' if task.completed else 'SCHEDULED' if task.start_time else 'ANYTIME · YOUR CHECKLIST'
            if group!=last_group:
                label(self.rows,group,10,TEXT_MUTED,True).grid(row=row_index,column=0,sticky='w',padx=6,pady=(12,6))
                row_index+=1
                last_group=group
            self._card(task,row_index,overlaps,now)
            row_index+=1

    def _card(self, task, index, overlaps, now):
        card=surface(self.rows)
        card.grid(row=index,column=0,sticky='ew',pady=5,padx=4)
        card.grid_columnconfigure(1,weight=1)
        left=ctk.CTkFrame(card,fg_color='transparent',width=70)
        left.grid(row=0,column=0,sticky='ns',padx=(14,12),pady=16)
        label(left,task.start_time or 'Anytime',14,TEXT_SECONDARY,True).pack(anchor='w')
        label(left,f'{task.minutes} min',10,TEXT_MUTED).pack(anchor='w',pady=(5,0))
        body=ctk.CTkFrame(card,fg_color='transparent')
        body.grid(row=0,column=1,sticky='nsew',pady=16)
        body.grid_columnconfigure(0,weight=1)
        title=ctk.CTkCheckBox(body,text=task.title,variable=ctk.BooleanVar(value=task.completed),
            command=lambda:self.toggle(task.id,not task.completed),font=('Inter',14,'bold'),
            text_color=TEXT_MUTED if task.completed else TEXT_PRIMARY,checkbox_width=19,checkbox_height=19,
            width=1,height=26,fg_color=ACCENT_CUSTOM,hover_color=HOVER_BG)
        title.grid(row=0,column=0,sticky='ew')
        title._text_label.configure(justify='left',anchor='w')
        body.bind('<Configure>',lambda event:fit_wrap(title._text_label,max(120,event.width-38)),add='+')
        mode=self._modes.get(task.mode_id)
        details=f'{task.priority} priority'
        if mode: details+=f'  ·  {mode.name}'
        elif task.mode_id: details+='  ·  Mode removed'
        if not task.completed and task.start_time and datetime.fromisoformat(f'{task.day}T{task.start_time}')<now:
            details+='  ·  Overdue'
        if task.id in overlaps: details+='  ·  Time overlap'
        info=label(body,details,10,ICE if task.priority=='High' else TEXT_SECONDARY,wraplength=250,justify='left')
        info.grid(row=1,column=0,sticky='w',padx=(29,0),pady=(5,0))
        if task.checklist:
            finished=sum(step['done'] for step in task.checklist)
            button(body,f'{"▾" if task.id in self.expanded else "▸"}  {finished}/{len(task.checklist)} steps',
                lambda:self.expand(task.id),width=102).grid(row=2,column=0,sticky='w',padx=(29,0),pady=(10,0))
            if task.id in self.expanded:
                for step_index,step in enumerate(task.checklist):
                    check=ctk.CTkCheckBox(body,text=step['text'],width=1,font=('Inter',11),
                        variable=ctk.BooleanVar(value=step['done']),checkbox_width=16,checkbox_height=16,
                        text_color=TEXT_SECONDARY,fg_color=ACCENT_CUSTOM,
                        command=lambda i=step_index,done=step['done']:self.toggle_step(task.id,i,not done))
                    check.grid(row=3+step_index,column=0,sticky='ew',padx=(29,6),pady=(8,0))
                    check._text_label.configure(wraplength=210,justify='left')
        actions=ctk.CTkFrame(card,fg_color='transparent')
        actions.grid(row=0,column=2,sticky='ne',padx=(12,14),pady=16)
        focus=button(actions,'Focus →',lambda:self.start_focus(task.id),True,width=84)
        focus.pack()
        if task.completed: focus.configure(state='disabled')
        button(actions,'Edit',lambda:self.edit_task(task.id),width=84).pack(pady=(7,0))


class TaskDialog(ctk.CTkToplevel):
    def __init__(self,parent,db,task,on_saved):
        super().__init__(parent)
        self.db,self.task,self.on_saved=db,replace(task,checklist=[dict(s) for s in task.checklist]),on_saved
        self.title('Edit task' if task.id else 'Plan a task')
        set_window_brand(self)
        self.configure(fg_color=BG_PRIMARY)
        height=min(740,max(520,int(self._reverse_window_scaling(self.winfo_screenheight()-120))))
        self.geometry(f'620x{height}')
        self.minsize(540,520)
        self.transient(parent.winfo_toplevel())
        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(1,weight=1)
        PageHeader(self,'ONE THING AT A TIME','Edit task' if task.id else 'Plan a task',
            'Set a time, choose a mode and define your next small steps.').grid(row=0,column=0,sticky='ew',padx=26,pady=(24,16))
        self.form=ctk.CTkScrollableFrame(self,fg_color='transparent')
        self.form.grid(row=1,column=0,sticky='nsew',padx=20)
        self.form.grid_columnconfigure((0,1),weight=1,uniform='fields')
        self.title_entry=self._entry('Task name',task.title,0,0,span=2)
        self.day_entry=self._entry('Date · YYYY-MM-DD',task.day,2,0)
        pick=button(self.form,'Pick…',self.pick_date,width=54)
        pick.configure(height=24,font=('Inter',10))
        pick.grid(row=2,column=0,sticky='e',padx=6,pady=(8,2))
        self.time_entry=self._entry('Start time · 24h, optional',task.start_time,2,1,placeholder='09:30')
        self.minutes_entry=self._entry('Estimated time · minutes',str(task.minutes),4,0)
        label(self.form,'Priority',11,TEXT_SECONDARY).grid(row=4,column=1,sticky='w',padx=6,pady=(12,6))
        self.priority=FocusDropdown(self.form,menu_title='PRIORITY',values=['Low','Normal','High'],width=1)
        self.priority.set(task.priority)
        self.priority.grid(row=5,column=1,sticky='ew',padx=6)
        label(self.form,'Focus Mode',11,TEXT_SECONDARY).grid(row=6,column=0,sticky='w',padx=6,pady=(12,6))
        self.modes={'Current mode':None,**{'Mode · '+mode.name:mode.id for mode in db.get_all_modes()}}
        self.mode=FocusDropdown(self.form,values=list(self.modes),width=1)
        self.mode.set(next((name for name,ident in self.modes.items() if ident==task.mode_id),'Current mode'))
        self.mode.grid(row=7,column=0,columnspan=2,sticky='ew',padx=6)
        label(self.form,'Estimate is for planning. Focus uses the selected mode’s session length.',10,TEXT_MUTED,
            wraplength=480,justify='left').grid(row=8,column=0,columnspan=2,sticky='w',padx=6,pady=(7,12))
        self.reminder=ctk.BooleanVar(value=task.reminder)
        ctk.CTkSwitch(self.form,text='Remind me at the start time',variable=self.reminder,
            progress_color=ACCENT_CUSTOM,font=('Inter',12),text_color=TEXT_PRIMARY).grid(row=9,column=0,columnspan=2,sticky='w',padx=6,pady=(0,14))
        label(self.form,'Notes',11,TEXT_SECONDARY).grid(row=10,column=0,sticky='w',padx=6,pady=(0,6))
        self.notes=ctk.CTkTextbox(self.form,height=84,fg_color=INPUT_BG,font=('Inter',12))
        self.notes.grid(row=11,column=0,columnspan=2,sticky='ew',padx=6)
        self.notes.insert('1.0',task.notes)
        label(self.form,'CHECKLIST',10,TEXT_SECONDARY,True).grid(row=12,column=0,sticky='w',padx=6,pady=(18,8))
        button(self.form,'+ Add step',lambda:self.add_step(),width=96).grid(row=12,column=1,sticky='e',padx=6,pady=(14,6))
        self.steps_frame=ctk.CTkFrame(self.form,fg_color='transparent')
        self.steps_frame.grid(row=13,column=0,columnspan=2,sticky='ew',padx=6,pady=(0,12))
        self.steps=[]
        for step in task.checklist: self.add_step(step['text'],step['done'])
        self.error=label(self,'',11,ACCENT_CUSTOM,wraplength=550,justify='left')
        self.error.grid(row=2,column=0,sticky='ew',padx=26,pady=(8,0))
        self.actions=surface(self)
        self.actions.grid(row=3,column=0,sticky='ew',padx=24,pady=(8,20))
        if task.id:
            button(self.actions,'Delete',self.delete,width=70).pack(side='left',padx=12,pady=12)
            button(self.actions,'Tomorrow',self.move_tomorrow,width=88).pack(side='left',pady=12)
        button(self.actions,'Save task',self.save,True,width=104).pack(side='right',padx=12,pady=12)
        button(self.actions,'Cancel',self.destroy,width=74).pack(side='right',pady=12)
        self.bind('<Escape>',lambda event:self.destroy())
        self.after(80,self._activate)

    def _activate(self):
        if self.winfo_exists():
            self.grab_set()
            self.title_entry.focus_set()

    def pick_date(self):
        try: selected=date.fromisoformat(self.day_entry.get().strip())
        except ValueError: selected=date.today()
        def chosen(value):
            self.day_entry.delete(0,'end')
            self.day_entry.insert(0,value.isoformat())
        return DatePicker(self,selected,chosen,PlannerStore(self.db))

    def _entry(self,caption,value,row,col,span=1,placeholder=''):
        label(self.form,caption,11,TEXT_SECONDARY).grid(row=row,column=col,columnspan=span,sticky='w',padx=6,pady=(12 if row else 0,6))
        entry=ctk.CTkEntry(self.form,height=LARGE_CONTROL_HEIGHT,fg_color=INPUT_BG,border_color=SEPARATOR_COLOR,
            border_width=1,font=('Inter',CONTROL_FONT_SIZE),placeholder_text=placeholder)
        entry.grid(row=row+1,column=col,columnspan=span,sticky='ew',padx=6)
        entry.insert(0,value)
        return entry

    def add_step(self,text='',done=False):
        if len(self.steps)>=50:
            self.error.configure(text='A task can contain up to 50 checklist steps.')
            return
        frame=ctk.CTkFrame(self.steps_frame,fg_color='transparent')
        frame.pack(fill='x',pady=4)
        flag=ctk.BooleanVar(value=done)
        ctk.CTkCheckBox(frame,text='',variable=flag,width=22,checkbox_width=18,checkbox_height=18,
            fg_color=ACCENT_CUSTOM).pack(side='left',padx=(0,6))
        entry=ctk.CTkEntry(frame,placeholder_text='A small, concrete step…',height=CONTROL_HEIGHT,fg_color=INPUT_BG,
            border_width=0,font=('Inter',CONTROL_FONT_SIZE))
        entry.pack(side='left',fill='x',expand=True)
        entry.insert(0,text)
        step=(frame,entry,flag)
        self.steps.append(step)
        button(frame,'×',lambda:self.remove_step(step),width=32).pack(side='left',padx=(6,0))

    def remove_step(self,step):
        self.steps.remove(step)
        step[0].destroy()

    def save(self):
        if not self.master._allowed(): return
        try:
            task=replace(self.task,title=self.title_entry.get(),day=self.day_entry.get(),start_time=self.time_entry.get(),
                minutes=int(self.minutes_entry.get()),priority=self.priority.get(),notes=self.notes.get('1.0','end-1c'),
                mode_id=self.modes[self.mode.get()],reminder=self.reminder.get(),
                checklist=[{'text':entry.get(),'done':flag.get()} for _,entry,flag in self.steps if entry.get().strip()])
            PlannerStore(self.db).save(task)
        except (ValueError,sqlite3.Error) as error:
            self.error.configure(text=str(error) if 'invalid literal' not in str(error) else 'Estimated time must be a whole number of minutes.')
            return
        self.on_saved()
        self.destroy()

    def move_tomorrow(self):
        self.day_entry.delete(0,'end')
        self.day_entry.insert(0,(date.today()+timedelta(days=1)).isoformat())
        self.save()

    def delete(self):
        if not self.master._allowed(): return
        if CTkMessagebox(title='Delete task?',message='This task and its checklist will be removed.',
                icon='question',option_1='Keep task',option_2='Delete').get()=='Delete':
            PlannerStore(self.db).delete(self.task.id)
            self.on_saved()
            self.destroy()
