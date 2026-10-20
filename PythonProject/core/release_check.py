"""Isolated smoke check used to verify the packaged executable before release."""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
import faulthandler


def run_release_check(destination):
    os.environ['DEEPFOCUS_TESTING'] = '1'
    output = Path(destination).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fault_log = output.with_suffix('.fault.log').open('w', encoding='utf-8')
    faulthandler.enable(file=fault_log)
    report = {'ok': False, 'frozen': bool(getattr(sys, 'frozen', False)), 'checks': []}
    def checkpoint(message):
        fault_log.write(message + '\n')
        fault_log.flush()
    checkpoint('Starting isolated release check')
    app = None
    try:
        import numpy as np
        import sounddevice as sd
        from utils import constants
        from core.sound_engine import SoundEngine
        from core.instance import SingleInstance

        class Stream:
            def __init__(self, **kwargs): self.active = False
            def start(self): self.active = True
            def stop(self): self.active = False
            def abort(self): self.active = False
            def close(self): self.active = False

        sd.OutputStream = Stream
        with tempfile.TemporaryDirectory(prefix='focus-release-', dir=output.parent) as folder:
            constants.DB_DIR = folder
            constants.DB_PATH = str(Path(folder) / 'workspace.db')
            constants.CONFIG_PATH = str(Path(folder) / 'settings.json')
            constants.update_config({'theme': 'light', 'global_hotkeys': False})
            # DatabaseManager captures DB_PATH on import; load it only after
            # switching constants to the disposable diagnostic workspace.
            from core.backup import BackupManager
            engine = SoundEngine()
            for sound in constants.SOUND_TYPES:
                audio = engine._get_or_create_buffer(sound)
                assert len(audio) > 0 and np.isfinite(audio).all(), sound
            engine.play('rain')
            assert engine.is_playing('rain')
            engine.close()
            assert not engine.get_playing_sounds()
            report['checks'].append('all seven offline sounds, bundled PortAudio, playback/close')
            checkpoint('Audio check passed')
            first = SingleInstance(folder)
            second = SingleInstance(folder)
            try:
                assert first.is_primary and not second.is_primary
                second.activate()
                assert first.consume_activation()
            finally:
                second.close()
                first.close()
            report['checks'].append('Windows single-instance activation')
            checkpoint('Instance check passed; importing UI')

            from ui.app import DeepFocusApp
            checkpoint('UI imported; constructing app')
            app = DeepFocusApp()
            assert Path(app.db.db_path).resolve().parent == Path(folder).resolve()
            checkpoint('App constructed with isolated workspace')
            app.site_blocker.block = app.site_blocker.unblock = lambda *args: True
            app.site_blocker.cleanup = lambda: None
            app.app_blocker.start_monitoring = lambda *args, **kwargs: None
            app.app_blocker.stop_monitoring = lambda: None
            app._show_notification = lambda *args: None
            errors = []
            app.report_callback_exception = lambda *args: errors.append(str(args))
            import customtkinter as ctk
            visits = iter((theme, view) for theme in ('light', 'dark') for view in app.views)

            def step():
                try:
                    case = next(visits, None)
                    if case:
                        theme, view = case
                        ctk.set_appearance_mode(theme)
                        app.show_view(view)
                        app.after(80, step)
                        return
                    about = app.views['settings']._open_about()
                    assert about.profile['name'] == 'Nguyễn Công Trung'
                    about.destroy()
                    report['checks'].append('nine views, both themes, logo/fonts and About metadata')
                    manager = BackupManager(app.db, folder)
                    archive = str(Path(folder) / 'workspace.zip')
                    manager.export_workspace(archive)
                    manager.restore_workspace(archive)
                    report['checks'].append('SQLite workspace backup and restore')
                except BaseException:
                    errors.append(traceback.format_exc())
                finally:
                    if case is None:
                        app._quit()

            # Make sure any failure also terminates the diagnostic process.
            def begin():
                app.after(45000, lambda: (errors.append('release check timed out'), app._quit()))
                step()
            app.after(600, begin)
            app.mainloop()
            checkpoint('Mainloop exited')
            assert not errors, errors
            assert app._destroyed and not app.sound_engine.get_playing_sounds()
            report['checks'].append('clean final shutdown')
            report.update(ok=True, name=constants.APP_NAME, version=constants.APP_VERSION)
    except BaseException:
        report['error'] = traceback.format_exc()
        if app is not None:
            app.shutdown_resources()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    faulthandler.disable()
    fault_log.close()
    return 0 if report['ok'] else 1
