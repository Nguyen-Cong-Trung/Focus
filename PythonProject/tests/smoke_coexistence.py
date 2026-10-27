"""Real Tk loop alongside disposable GUI/CPU processes; no Computer Use."""
import faulthandler
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import Mock, patch

os.environ['DEEPFOCUS_TESTING'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
faulthandler.dump_traceback_later(90, exit=True)


class Stream:
    def __init__(self, **kwargs): self.active = False
    def start(self): self.active = True
    def stop(self): self.active = False
    def abort(self): self.active = False
    def close(self): self.active = False


def run():
    import sounddevice
    import customtkinter as ctk
    from utils import constants
    checks = []
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
        directory = Path(folder)
        constants.DB_DIR = folder
        constants.DB_PATH = str(directory / 'workspace.db')
        constants.CONFIG_PATH = str(directory / 'config.json')
        constants.update_config({'theme': 'light', 'global_hotkeys': False})
        # Each helper is created by this check and is the only process it stops.
        gui_code = """import pathlib,sys,tkinter as tk,time
p=pathlib.Path(sys.argv[1]);r=tk.Tk();r.withdraw()
def beat():
 p.write_text(str(time.monotonic()));r.after(100,beat)
beat();r.after(60000,r.destroy);r.mainloop()
"""
        cpu_code = """import pathlib,sys,time
p=pathlib.Path(sys.argv[1]);end=time.monotonic()+60
while time.monotonic()<end:
 stop=time.monotonic()+.02
 while time.monotonic()<stop: sum(i*i for i in range(300))
 p.write_text(str(time.monotonic()));time.sleep(.08)
"""
        children = [subprocess.Popen([sys.executable, '-X', 'utf8', '-c', code, str(directory / name)],
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    for code, name in ((gui_code, 'gui.heartbeat'), (cpu_code, 'cpu.heartbeat'))]
        app = None
        errors = []
        try:
            from ui.app import DeepFocusApp
            with patch.object(sounddevice, 'OutputStream', Stream):
                app = DeepFocusApp()
                app.report_callback_exception = lambda *error: errors.append(str(error))
                app.site_blocker.block = app.site_blocker.unblock = Mock(return_value=True)
                app.site_blocker.cleanup = Mock()
                app.app_blocker.start_monitoring = app.app_blocker.stop_monitoring = Mock()
                app._show_notification = Mock()
                visits = iter((theme, view) for theme in ('light', 'dark') for view in app.views)

                def finish():
                    try:
                        assert app._ready_shown and app.winfo_viewable()
                        assert app.timer_engine.remaining_seconds < 25 * 60
                        app.timer_engine.pause()
                        paused = app.timer_engine.remaining_seconds
                        def resumed():
                            try:
                                assert app.timer_engine.remaining_seconds == paused
                                app.timer_engine.resume()
                                app.timer_engine.stop()
                                app.stop_all_sounds()
                                for child in children:
                                    assert child.poll() is None, 'Unrelated helper process stopped'
                                for name in ('gui.heartbeat', 'cpu.heartbeat'):
                                    heartbeat = float((directory / name).read_text())
                                    assert time.monotonic() - heartbeat < 3, name
                                checks.append('independent Tk app and CPU worker remain responsive')
                                checks.append('timer advances under concurrent load; pause/resume stays correct')
                            except BaseException as error:
                                errors.append(repr(error))
                            finally:
                                app.timer_engine.stop()
                                app._quit()
                        app.after(1100, resumed)
                    except BaseException as error:
                        errors.append(repr(error))
                        app.timer_engine.stop()
                        app._quit()

                def step():
                    try:
                        case = next(visits, None)
                        if case is None:
                            checks.append('all nine views, light/dark themes, resize and mini player')
                            finish()
                            return
                        theme, view = case
                        ctk.set_appearance_mode(theme)
                        app.show_view(view)
                        app.geometry('940x660' if theme == 'light' else '1240x800')
                        if view == 'timer':
                            app.toggle_mini_player()
                            app.toggle_mini_player()
                        app.after(160, step)
                    except BaseException as error:
                        errors.append(repr(error))
                        app.timer_engine.stop()
                        app._quit()

                def begin():
                    try:
                        app.timer_engine.start_focus()
                        app.sound_engine.play('rain')
                        app.sound_engine.play('brown_noise')
                        assert len(app.sound_engine.get_playing_sounds()) == 2
                        # Device loss is simulated, without opening actual audio.
                        app.sound_engine.playback_handle('rain').active = False
                        app.views['sound'].refresh_playback()
                        app.sound_engine.play('rain')
                        checks.append('mixed playback, output loss/retry and global stop with fake audio hardware')
                        app._ui_events.put(lambda: (_ for _ in ()).throw(OSError('injected integration failure')))
                        app._ui_events.put(lambda: checks.append('clock continues after a failed Windows callback'))
                        step()
                    except BaseException as error:
                        errors.append(repr(error))
                        app.timer_engine.stop()
                        app._quit()
                app.after(500, begin)
                app.after(25000, lambda: (errors.append('coexistence test timeout'), app.timer_engine.stop(), app._quit()))
                app.mainloop()
                assert not errors, errors
                assert app._destroyed and not app.sound_engine.get_playing_sounds()
                checks.append('clean shutdown, no retained audio streams')
        finally:
            if app is not None:
                app.shutdown_resources()
            for child in children:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)
    output = {'ok': True, 'checks': checks, 'hardware_audio': 'mocked', 'other_processes': 2}
    destination = Path(__file__).resolve().parents[2] / '.release-work/coexistence-check.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps(output, indent=2), flush=True)


if __name__ == '__main__':
    run()
    faulthandler.cancel_dump_traceback_later()
