"""Cold-start saved theme must apply before the first native window is built."""
import os
import sys
import tempfile
import faulthandler
from pathlib import Path
from unittest.mock import patch, Mock
os.environ['DEEPFOCUS_TESTING']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
import utils.constants as constants
from utils.constants import BG_PRIMARY, BG_CARD

faulthandler.dump_traceback_later(90,exit=True)
theme=sys.argv[1] if len(sys.argv)>1 else 'light'
ctk.set_appearance_mode('dark' if theme=='light' else 'light')
observed=[]
original_init=ctk.CTk.__init__
def capture_init(self,*args,**kwargs):
    observed.append((ctk.get_appearance_mode().lower(),kwargs.get('fg_color')))
    original_init(self,*args,**kwargs)

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
    constants.DB_DIR=folder
    constants.DB_PATH=str(Path(folder)/'workspace.db')
    constants.CONFIG_PATH=str(Path(folder)/'settings.json')
    constants.update_config({'theme':theme})
    from ui.app import DeepFocusApp
    with patch.object(ctk.CTk,'__init__',capture_init):
        app=DeepFocusApp()
    for obj,names in [(app.site_blocker,('block','unblock','cleanup')),(app.app_blocker,('start_monitoring','stop_monitoring'))]:
        for name in names: setattr(obj,name,Mock())
    failures=[]
    app.report_callback_exception=lambda *error:failures.append(str(error))
    assert observed==[(theme,BG_PRIMARY)],observed
    assert app.state()=='withdrawn', 'Partially constructed UI must remain hidden'
    assert app.cget('bg')==BG_PRIMARY[0 if theme=='light' else 1]
    def verify():
        try:
            assert app.winfo_viewable(), 'Ready app must become visible'
            expected=0 if theme=='light' else 1
            assert app.main_frame._canvas.cget('bg')==BG_PRIMARY[expected], ('main background',app.main_frame._canvas.cget('bg'))
            clock=app.views['timer'].progress_circle
            assert clock.cget('bg')==BG_CARD[expected], ('clock background',clock.cget('bg'))
            card=app.views['timer'].center_frame
            assert card._canvas.cget('bg')==BG_PRIMARY[expected], ('rounded card backing',card._canvas.cget('bg'))
            assert card._canvas.itemcget('inner_parts','fill')==BG_CARD[expected], ('card fill',card._canvas.itemcget('inner_parts','fill'))
            # Restore should keep the palette; no theme reconstruction is needed.
            app.withdraw()
            app._tray_action('open')
            app.update_idletasks()
            assert card._canvas.cget('bg')==BG_PRIMARY[expected]
            assert clock.cget('bg')==BG_CARD[expected]
            assert not failures,failures
            print(f'STARTUP THEME PASSED: saved {theme}, opposite default, correct root/frames/clock, hidden construction, tray restore',flush=True)
        except BaseException as error:
            failures.append(repr(error))
        finally:
            app._on_close()
    app.after(700,verify)
    app.mainloop()
    assert not failures,failures
faulthandler.cancel_dump_traceback_later()
