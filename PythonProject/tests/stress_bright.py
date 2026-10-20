"""Exercise cold-start light mode, every route and live resize without Computer Use."""
import os
import sys
import json
import time
import tempfile
import traceback
import faulthandler
from pathlib import Path
from unittest.mock import Mock
os.environ['DEEPFOCUS_TESTING']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
import utils.constants as constants
from data.models import FocusMode, FocusSession

faulthandler.dump_traceback_later(180,exit=True)
ctk.set_appearance_mode('dark')
result={'visits':0,'resizes':0,'audited_frames':0,'mismatches':[],'callbacks':[],'idle_gaps_ms':[]}
with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
    constants.DB_DIR=folder
    constants.DB_PATH=str(Path(folder)/'workspace.db')
    constants.CONFIG_PATH=str(Path(folder)/'config.json')
    constants.update_config({'theme':'light'})
    from ui.app import DeepFocusApp
    from core.planner import PlannerStore, PlanTask
    app=DeepFocusApp()
    for obj,names in [(app.site_blocker,('block','unblock','cleanup')),(app.app_blocker,('start_monitoring','stop_monitoring'))]:
        for name in names: setattr(obj,name,Mock())
    app.report_callback_exception=lambda *error:result['callbacks'].append(''.join(traceback.format_exception(*error)))
    for index in range(8):
        app.db.save_mode(FocusMode(name=f'Stress mode {index+1}'))
        app.db.save_session(FocusSession(completed=True,elapsed_seconds=60,outcome='completed'))
        PlannerStore(app.db).save(PlanTask(title=f'Prepare task {index+1}',start_time=f'{9+index:02d}:00',
            checklist=[{'text':'First step','done':False}]))
    actions=[]
    routes=list(app.views)
    for cycle in range(2):
        for route in routes:
            actions.append(('route',route))
            for geometry in ('900x600','1060x680','1380x880','980x640'):
                actions.append(('size',geometry))
    actions.extend([('tray',None),('size','1240x800'),('route','timer')])
    last_tick=[None]
    def heartbeat():
        if app._destroyed: return
        now=time.perf_counter()
        if last_tick[0] is not None: result['idle_gaps_ms'].append(round((now-last_tick[0])*1000,2))
        last_tick[0]=now
        app.after(40,heartbeat)
    def audit(widget):
        if not widget.winfo_viewable(): return
        if isinstance(widget,ctk.CTkFrame) and hasattr(widget,'_canvas'):
            result['audited_frames']+=1
            expected=widget._apply_appearance_mode(widget._bg_color)
            actual=widget._canvas.cget('bg')
            if widget.winfo_rgb(expected)!=widget.winfo_rgb(actual):
                result['mismatches'].append(('backing',str(widget),expected,actual))
            inner=widget._canvas.find_withtag('inner_parts')
            if inner:
                expected=widget._apply_appearance_mode(widget._bg_color if widget._fg_color=='transparent' else widget._fg_color)
                actual=widget._canvas.itemcget(inner[0],'fill')
                if actual and widget.winfo_rgb(expected)!=widget.winfo_rgb(actual):
                    result['mismatches'].append(('face',str(widget),expected,actual))
        for child in widget.winfo_children(): audit(child)
    def step():
        try:
            audit(app)
            if not actions:
                gaps=sorted(result['idle_gaps_ms'])
                result['heartbeat_p95_ms']=gaps[int((len(gaps)-1)*.95)]
                result['heartbeat_max_ms']=max(gaps)
                if len(sys.argv)>1:
                    Path(sys.argv[1]).write_text(json.dumps({key:value for key,value in result.items() if key!='idle_gaps_ms'},indent=2),encoding='utf-8')
                print(json.dumps({key:value for key,value in result.items() if key!='idle_gaps_ms'},indent=2),flush=True)
                app._on_close()
                return
            kind,value=actions.pop(0)
            if kind=='route':
                app.show_view(value)
                result['visits']+=1
            elif kind=='size':
                app.geometry(value)
                result['resizes']+=1
            else:
                app.withdraw()
                app._tray_action('open')
            app.after(70,step)
        except BaseException:
            result['callbacks'].append(traceback.format_exc())
            app._on_close()
    app.after(600,heartbeat)
    app.after(900,step)
    app.mainloop()
    assert not result['mismatches'],result['mismatches'][:8]
    assert not result['callbacks'],result['callbacks']
    print('BRIGHT STRESS PASSED',flush=True)
faulthandler.cancel_dump_traceback_later()
