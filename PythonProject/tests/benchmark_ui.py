"""Measure UI work using isolated data; never operate real blocking/audio/shutdown."""
import os
import sys
import json
import time
import tempfile
import faulthandler
from pathlib import Path
from unittest.mock import Mock, patch
os.environ['DEEPFOCUS_TESTING']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import utils.constants as constants
import customtkinter as ctk

faulthandler.dump_traceback_later(180,exit=True)
draws={'buttons':0,'labels':0,'sliders':0}
originals={name:cls._draw for name,cls in [('buttons',ctk.CTkButton),('labels',ctk.CTkLabel),('sliders',ctk.CTkSlider)]}
def counter(name):
    def wrapped(self,*args,**kwargs):
        draws[name]+=1
        return originals[name](self,*args,**kwargs)
    return wrapped

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
    constants.DB_DIR=folder
    constants.DB_PATH=str(Path(folder)/'workspace.db')
    constants.CONFIG_PATH=str(Path(folder)/'config.json')
    from ui.app import DeepFocusApp
    with patch.object(ctk.CTkButton,'_draw',counter('buttons')),patch.object(ctk.CTkLabel,'_draw',counter('labels')),patch.object(ctk.CTkSlider,'_draw',counter('sliders')):
        start=time.perf_counter()
        app=DeepFocusApp()
        results={'startup_seconds':round(time.perf_counter()-start,4)}
        for obj,names in [(app.site_blocker,('block','unblock','cleanup')),(app.app_blocker,('start_monitoring','stop_monitoring'))]:
            for name in names: setattr(obj,name,Mock())
        failures=[]
        app.report_callback_exception=lambda *error:failures.append(str(error))
        def idle_start():
            results['_idle']=(time.perf_counter(),time.process_time(),dict(draws))
        def measure():
            first=results.pop('_idle')
            results['idle_seconds']=round(time.perf_counter()-first[0],4)
            results['idle_cpu_seconds']=round(time.process_time()-first[1],4)
            results['idle_draws']={key:draws[key]-first[2][key] for key in draws}
            start=time.perf_counter()
            ctk.set_appearance_mode('light')
            app.update_idletasks()
            results['theme_seconds']=round(time.perf_counter()-start,4)
            results['navigation_seconds']={}
            for name in app.views:
                start=time.perf_counter()
                app.show_view(name)
                app.update_idletasks()
                results['navigation_seconds'][name]=round(time.perf_counter()-start,4)
            print(json.dumps(results,indent=2),flush=True)
            if len(sys.argv)>1:
                Path(sys.argv[1]).write_text(json.dumps(results,indent=2),encoding='utf-8')
            app._on_close()
        app.after(2500,idle_start)
        app.after(5500,measure)
        app.mainloop()
        assert not failures,failures
faulthandler.cancel_dump_traceback_later()
