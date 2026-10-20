"""Detect recurring layout/redraw storms with a real idle event loop and isolated data."""
import os
import sys
import tempfile
import time
import faulthandler
import threading
from pathlib import Path
from unittest.mock import patch, Mock
os.environ['DEEPFOCUS_TESTING']='1'
faulthandler.dump_traceback_later(30,repeat=True)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import utils.constants as constants
from ui.timer_view import TimerView
from ui.widgets import CircularProgressBar

counts={'layout':0,'clock':0}
original_layout=TimerView._layout_hero
original_draw=CircularProgressBar._draw
def layout(self,*args,**kwargs):
    counts['layout']+=1
    return original_layout(self,*args,**kwargs)
def draw(self,*args,**kwargs):
    counts['clock']+=1
    return original_draw(self,*args,**kwargs)

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
    constants.DB_DIR=folder
    constants.DB_PATH=str(Path(folder)/'workspace.db')
    constants.CONFIG_PATH=str(Path(folder)/'config.json')
    from ui.app import DeepFocusApp
    with patch.object(TimerView,'_layout_hero',layout),patch.object(CircularProgressBar,'_draw',draw):
        app=DeepFocusApp()
        print('IDLE APP CREATED',flush=True)
        app.site_blocker.block=Mock()
        app.site_blocker.unblock=Mock()
        app.site_blocker.cleanup=Mock()
        app.app_blocker.start_monitoring=Mock()
        app.app_blocker.stop_monitoring=Mock()
        failures=[]
        app.report_callback_exception=lambda *error:failures.append(error)
        samples=[]
        def timed_out():
            print('IDLE WATCHDOG',counts,'SAMPLES',samples,flush=True)
            faulthandler.dump_traceback()
            os._exit(2)
        watchdog=threading.Timer(40,timed_out)
        watchdog.daemon=True
        watchdog.start()
        def sample():
            samples.append((time.perf_counter(),time.process_time(),dict(counts)))
            print('IDLE TICK',dict(counts),flush=True)
        app.after(3000,sample)
        app.after(5000,sample)
        app.after(5500,app._on_close)
        app.mainloop()
        watchdog.cancel()
        assert len(samples)==2 and not failures,(samples,failures)
        first,last=samples
        delta={key:last[2][key]-first[2][key] for key in counts}
        print('IDLE SAMPLE:',delta,'CPU seconds:',round(last[1]-first[1],3),flush=True)
        assert delta['layout']<12 and delta['clock']<8,('Idle redraw storm',delta)
        print('IDLE SMOKE PASSED: settled window has no continuous layout/redraw loop')
faulthandler.cancel_dump_traceback_later()
