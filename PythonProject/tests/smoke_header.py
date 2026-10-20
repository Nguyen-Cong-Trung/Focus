"""Check actual text allocation and ancestor clipping without computer use."""
import faulthandler
import os
from pathlib import Path
import sys
import tempfile
import time

os.environ['DEEPFOCUS_TESTING'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
import utils.constants as constants

faulthandler.dump_traceback_later(120, exit=True)
with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
    constants.DB_DIR = folder
    constants.DB_PATH = str(Path(folder) / 'workspace.db')
    constants.CONFIG_PATH = str(Path(folder) / 'settings.json')
    constants.update_config({'theme': 'light'})
    from ui.app import DeepFocusApp
    app = DeepFocusApp()
    assert app.title() == 'Focus'
    assert app.header_brand_title.cget('text') == 'Focus'
    assert app.header_brand_subtitle.cget('text') == 'SPERTULO UTILITY'
    assert app.version_label.cget('text') == 'Focus  •  v1.0.0'
    assert Path(app.tray.icon_path).name == 'focus.ico'
    assert (Path(__file__).resolve().parents[2] / 'branding/focus-logo.png').read_bytes() == (
        Path(__file__).resolve().parents[2] / 'Logo Focus.png').read_bytes()
    failures = []
    app.report_callback_exception = lambda *error: failures.append(str(error))
    cases = iter((theme, scale, size, view)
        for theme in ('light', 'dark')
        for scale in (0.8, 1.0, 1.25, 1.5)
        for size, view in (('900x600', 'timer'), ('1240x800', 'shutdown')))
    count = [0]

    def verify():
        try:
            labels = []
            def collect(widget):
                if isinstance(widget, ctk.CTkLabel) and widget.cget('text'):
                    labels.append(widget)
                for child in widget.winfo_children():
                    collect(child)
            collect(app.topbar)
            # Windows can defer native mapping during a DPI transition.
            # Wait for allocation before checking for genuine text clipping.
            if not all(widget._label.winfo_ismapped()
                    and widget._label.winfo_width() >= widget._label.winfo_reqwidth()
                    and widget._label.winfo_height() >= widget._label.winfo_reqheight()
                    for widget in labels):
                if time.monotonic() < ready_deadline[0]:
                    app.after(100, verify)
                    return
            for widget in labels:
                native = widget._label
                context = (widget.cget('text'), current[0], 'native', native.winfo_width(), native.winfo_height(), 'requested', native.winfo_reqwidth(), native.winfo_reqheight())
                assert native.winfo_ismapped(), context
                assert native.winfo_width() >= native.winfo_reqwidth(), context
                assert native.winfo_height() >= native.winfo_reqheight(), context
                x, y = native.winfo_rootx(), native.winfo_rooty()
                right, bottom = x + native.winfo_width(), y + native.winfo_height()
                parent = native.master
                while parent is not app:
                    assert x >= parent.winfo_rootx() - 1, context
                    assert y >= parent.winfo_rooty() - 1, context
                    assert right <= parent.winfo_rootx() + parent.winfo_width() + 1, (context, str(parent), "right", right, parent.winfo_rootx() + parent.winfo_width())
                    assert bottom <= parent.winfo_rooty() + parent.winfo_height() + 1, (context, str(parent), "bottom", bottom, parent.winfo_rooty() + parent.winfo_height())
                    parent = parent.master
            count[0] += 1
            advance()
        except BaseException as error:
            if isinstance(error, AssertionError) and time.monotonic() < ready_deadline[0]:
                app.after(100, verify)
                return
            failures.append(repr(error))
            app._on_close()

    current = [None]
    ready_deadline = [0]
    def advance():
        case = next(cases, None)
        if case is None:
            app._on_close()
            return
        current[0] = case
        ready_deadline[0] = time.monotonic() + 15
        theme, scale, size, view = case
        ctk.set_appearance_mode(theme)
        ctk.set_widget_scaling(scale)
        ctk.set_window_scaling(scale)
        app.geometry(size)
        app.show_view(view)
        app.after(1400, verify)

    app.after(1600, advance)
    app.mainloop()
    assert not failures, failures
    print(f'HEADER PASSED: {count[0]} theme/scale/size/route combinations; full text fits every ancestor')
faulthandler.cancel_dump_traceback_later()



