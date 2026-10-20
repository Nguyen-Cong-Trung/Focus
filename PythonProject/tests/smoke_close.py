"""Real Tk lifecycle with isolated workspace and fake audio/OS side effects."""
import faulthandler
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import Mock, patch

import numpy as np

os.environ['DEEPFOCUS_TESTING'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.instance import SingleInstance
import utils.constants as constants

faulthandler.dump_traceback_later(120, exit=True)


class FakeStream:
    all_streams = []

    def __init__(self, **kwargs):
        self.callback = kwargs['callback']
        self.active = self.closed = False
        self.all_streams.append(self)

    def start(self): self.active = True
    def stop(self): self.active = False
    def abort(self): self.active = False
    def close(self): self.closed = True; self.active = False


with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
    constants.DB_DIR = folder
    constants.DB_PATH = str(Path(folder) / 'workspace.db')
    constants.CONFIG_PATH = str(Path(folder) / 'settings.json')
    constants.update_config({'close_to_tray': True, 'theme': 'light'})
    from ui.app import DeepFocusApp
    guard = SingleInstance(folder)
    app = DeepFocusApp(instance_guard=guard)
    for obj, names in [(app.site_blocker, ('block', 'unblock', 'cleanup')),
                       (app.app_blocker, ('start_monitoring', 'stop_monitoring'))]:
        for name in names: setattr(obj, name, Mock(return_value=True))
    app._show_notification = Mock()
    app.tray.update = Mock()
    failures = []
    app.report_callback_exception = lambda *error: failures.append(str(error))

    def play(name='rain'):
        print('CLOSE CHECK: play ' + name, flush=True)
        app.run_background(lambda: app.sound_engine.play(name), lane='audio')
        return lambda: app.sound_engine.is_playing(name)

    def close_to_tray():
        print('CLOSE CHECK: close to tray', flush=True)
        app.tray.available = True
        app.testing = False
        app._on_close()
        app.testing = True
        yield lambda: app.state() == 'withdrawn'
        yield lambda: not app.sound_engine.get_playing_sounds()

    def checks():
        app.timer_engine.start_focus()
        yield play()
        yield play('pink_noise')
        app.views['sound'].stop_all_button.invoke()
        yield lambda: not app.sound_engine.get_playing_sounds()
        assert app.timer_engine.state == constants.TimerState.FOCUSING
        yield play()
        stream = app.sound_engine._streams['rain']
        yield from close_to_tray()
        data = np.ones((1024, 2), dtype=np.float32)
        stream.callback(data, len(data), None, None)
        assert not np.any(data), 'Closed-window audio must remain silent'
        assert app.timer_engine.state == constants.TimerState.FOCUSING
        second = SingleInstance(folder)
        try:
            assert not second.is_primary
            second.activate()
            yield lambda: app.state() == 'normal'
        finally:
            second.close()
        yield play()
        app._tray_action('stop_sounds')
        yield lambda: not app.sound_engine.get_playing_sounds()
        assert app.timer_engine.state == constants.TimerState.FOCUSING
        app.toggle_mini_player()
        yield play()
        yield from close_to_tray()
        app._tray_action('open')
        yield lambda: app.state() == 'normal'
        app.toggle_mini_player()
        yield play()
        app.sound_engine._streams['rain'].active = False
        app.views['sound'].refresh_playback()
        assert not app.sound_engine.is_playing('rain')
        yield from close_to_tray()
        app.tray.available = False
        yield lambda: app.state() == 'normal'
        assert 'tray icon is unavailable' in app.notice.cget('text')
        yield play()

    steps = checks()

    def finish(error=None):
        if error is not None:
            failures.append(repr(error))
        app.testing = True
        with patch('ui.app.CTkMessagebox') as confirm:
            confirm.return_value.get.return_value = 'End and quit'
            app._quit()

    def advance():
        try:
            condition = next(steps)
        except StopIteration:
            finish()
        except BaseException as error:
            finish(error)
        else:
            deadline = time.monotonic() + 12
            def poll():
                try:
                    if condition():
                        app.after(1, advance)
                    elif time.monotonic() < deadline:
                        app.after(20, poll)
                    else:
                        finish(AssertionError('Lifecycle operation did not settle'))
                except BaseException as error:
                    finish(error)
            app.after(20, poll)

    with patch('core.sound_engine.sd.OutputStream', FakeStream), patch.object(
            app.sound_engine, '_get_or_create_buffer', return_value=np.ones(128, dtype=np.float32)):
        app.after(1000, advance)
        app.mainloop()
    guard.close()
    assert not failures, failures
    assert not app.sound_engine._streams
    assert all(stream.closed for stream in FakeStream.all_streams)
    assert app.work.closed and app.blocking.closed
    print('CLOSE PASSED: global stop, X/tray, timer preserved, single instance restore, mini player, device loss, lost tray recovery, quit cleanup')
faulthandler.cancel_dump_traceback_later()
