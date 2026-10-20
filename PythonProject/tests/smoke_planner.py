"""Focused Tk layout check for the planner, without OS side effects."""
import os
import sys
import tempfile
import faulthandler
from pathlib import Path
from datetime import date

os.environ['DEEPFOCUS_TESTING']='1'
faulthandler.enable()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
from data.database import DatabaseManager
from core.planner import PlanTask
from ui.design import load_design
from ui.planner_view import PlannerView, TaskDialog
from ui.date_picker import DatePicker, shift_month

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
    db=DatabaseManager(Path(folder)/'planner.db')
    root=ctk.CTk()
    root._closing=root._restoring=False
    load_design()
    root.geometry('668x524')  # Available content area of the minimum main window.
    planner=PlannerView(root,db)
    planner.pack(fill='both',expand=True)
    planner.select_day(date(2099,10,19))
    for i in range(3):
        planner.store.save(PlanTask(title='An intentionally long task title to verify that wrapping keeps the card inside its column',
            day='2099-10-19',start_time=f'{9+i:02d}:00',checklist=[{'text':'Check the layout of a long checklist step in a narrow window','done':False}]))
    failures=[]
    root.report_callback_exception=lambda *error:failures.append(error)
    try:
        root.deiconify()
        for theme in ('light','dark'):
            ctk.set_appearance_mode(theme)
            planner.refresh()
            root.update()
            assert planner.rows.winfo_height()>75
            cards=[widget for widget in planner.rows.winfo_children() if isinstance(widget,ctk.CTkFrame)]
            for card in cards:
                assert card.winfo_x()+card.winfo_width() <= planner.rows.winfo_width()+2, 'Task card extends beyond its column'
            picker=planner.open_date_picker()
            root.update()
            picker.month_picker.set('February')
            picker.year_entry.delete(0,'end')
            picker.year_entry.insert(0,'2040')
            picker.change_month()
            assert (picker.year,picker.month)==(2040,2)
            assert any(cell.cget('text')=='29' for cell in picker.cells), 'Leap day must be selectable'
            picker.move_month(-1)
            assert (picker.year,picker.month)==(2040,1)
            picker.year_entry.delete(0,'end')
            picker.year_entry.insert(0,'invalid')
            picker.change_month()
            assert picker.error.cget('text')
            picker.date_entry.delete(0,'end')
            picker.date_entry.insert(0,'2040-02-30')
            picker.go_to_date()
            assert picker.winfo_exists() and picker.error.cget('text')
            picker.date_entry.delete(0,'end')
            picker.date_entry.insert(0,'2040-02-29')
            picker.go_to_date()
            root.update()
            assert planner.selected_day==date(2040,2,29), 'Exact date must update the agenda and week'
            picker=planner.open_date_picker()
            root.update()
            picker.cells[next(i for i,cell in enumerate(picker.cells) if cell.cget('text')=='15')].invoke()
            assert planner.selected_day==date(2040,2,15)
            picker=planner.open_date_picker()
            picker.move_month(12)
            picker.destroy()
            assert planner.selected_day==date(2040,2,15), 'Cancel must preserve selection'
            for boundary in (date.min,date.max):
                planner.select_day(boundary)
                picker=planner.open_date_picker()
                picker.destroy()
            assert shift_month(2026,12,1)==(2027,1)
            assert shift_month(1,1,-1) is None
            assert shift_month(9999,12,1) is None
            planner.select_day(date(2099,10,19))
            dialog=TaskDialog(planner,db,PlanTask(day='2099-10-19'),planner.refresh)
            root.update()
            dialog._activate()
            picker=dialog.pick_date()
            root.update()
            picker._activate()
            picker.month_picker._open_dropdown_menu()
            picker.month_picker._choose(1)
            assert picker.grab_current()==picker, 'Month dropdown must restore calendar grab'
            picker.choose(date(2044,2,29))
            assert dialog.day_entry.get()=='2044-02-29'
            assert dialog.grab_current()==dialog, 'Calendar must restore task editor grab'
            assert abs(dialog.day_entry.winfo_width()-dialog.time_entry.winfo_width())<=1
            assert dialog.actions.winfo_y()+dialog.actions.winfo_height() <= dialog.winfo_height(), 'Task actions are clipped'
            for i in range(50): dialog.add_step(f'Step {i+1}')
            dialog.add_step('Over the limit')
            assert len(dialog.steps)==50 and dialog.error.cget('text')
            dialog.destroy()
            root.update()
        assert not failures,failures
        print('PLANNER SMOKE PASSED: month/year/date jumps, leap days, year bounds, cancel, calendar clicks, nested modal/dropdown grabs, narrow content, aligned columns, checklist limit, both themes')
    finally:
        root.destroy()
