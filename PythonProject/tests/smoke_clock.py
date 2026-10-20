"""Verify real glyph bounds inside the clock at several sizes and Tk DPI settings."""
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
from ui.widgets import CircularProgressBar
from ui.design import load_design

root=ctk.CTk()
root.withdraw()
load_design()
clock=CircularProgressBar(root,size=292,width=6)
try:
    for dpi in (1.0,1.25,1.5,2.0,2.5):
        root.tk.call('tk','scaling',dpi)
        for theme in ('light','dark'):
            ctk.set_appearance_mode(theme)
            for size in (220,228,236,250,292):
                clock.size=size
                clock.configure(width=size,height=size)
                for value,status in (('25:00','READY'),('99:59','FOCUSING'),('1440:00','LONG BREAK'),('00:00','PAUSED')):
                    previous_static=clock.find_withtag('clock-static')
                    previous_key=getattr(clock,'_static_key',None)
                    clock.set_state(value,status,.5)
                    if previous_key==clock._static_key:
                        assert previous_static==clock.find_withtag('clock-static'), 'Tick marks should be retained between seconds'
                    unchanged=clock.find_all()
                    clock.set_state(value,status,.5)
                    assert unchanged==clock.find_all(), 'Identical timer state should not recreate canvas items'
                    bounds=[]
                    for tag in ('timer-time','timer-state'):
                        box=clock.bbox(tag)
                        bounds.append(box)
                        radius=size/2-17-clock.width/2-12
                        assert all(math.hypot(x-size/2,y-size/2)<=radius for x in (box[0],box[2]) for y in (box[1],box[3])), (dpi,size,value,status,tag,box)
                    assert bounds[0][3]<bounds[1][1], ('Clock labels overlap',dpi,size,value,bounds)
    print('CLOCK SMOKE PASSED: 5 DPI settings, 5 sizes, both themes, normal/long countdowns, circular bounds and label separation')
finally:
    root.destroy()
