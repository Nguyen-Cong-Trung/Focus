"""Exercise real Tk widgets using isolated data and mocked OS side effects."""
import sys
import os
os.environ["DEEPFOCUS_TESTING"] = "1"
import tempfile
import time
import wave
import faulthandler
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as constants
if '--preview' not in sys.argv:
    faulthandler.dump_traceback_later(300,exit=True)

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as temporary:
    constants.DB_DIR = temporary
    constants.DB_PATH = str(Path(temporary) / 'test.db')
    constants.CONFIG_PATH = str(Path(temporary) / 'config.json')
    from data.database import DatabaseManager
    from data.models import BlockedItem, FocusMode, CustomSound
    fixture_db = DatabaseManager()
    fixture_db.add_blocked_item(BlockedItem(name='smoke.example', value='smoke.example', item_type='website'))
    fixture_db.save_mode(FocusMode(name='Deep Work', focus_minutes=50, short_break_minutes=10,
                                   long_break_minutes=20, sessions_before_long_break=3,
                                   auto_flow=True, target_goal=6))
    for filename, name in (('rain.wav','Rain Room'),('library.wav','Library Ambience')):
        path = Path(temporary)/filename
        with wave.open(str(path),'wb') as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(44100)
            recording.writeframes(b'\0\0'*100)
        fixture_db.save_custom_sound(CustomSound(name=name,file_path=str(path)))
    from ui.app import DeepFocusApp
    import customtkinter as ctk
    from utils.constants import TimerState
    app = DeepFocusApp()
    assert 'smoke.example' in [item.value for item in app.db.get_blocked_items('website')]
    failures = []
    app.report_callback_exception = lambda *error: failures.append(error)
    app._show_notification = Mock()
    app.site_blocker.block = Mock()
    app.site_blocker.unblock = Mock()
    app.site_blocker.cleanup = Mock()
    app.app_blocker.start_monitoring = Mock()
    app.app_blocker.stop_monitoring = Mock()
    app.shutdown_scheduler._run = Mock()

    def check():
        try:
            def wait_until(condition):
                deadline=time.monotonic()+10
                while not condition() and time.monotonic()<deadline:
                    app.update()
                    time.sleep(.01)
                assert condition(), 'UI/background action did not settle within 10 seconds'
            for theme in ('light', 'dark'):
                app.views["settings"].set_theme(theme)
                assert app.config["theme"] == theme
                for view in app.views:
                    app.show_view(view)
                    app.update_idletasks()
            app.deiconify()
            if not app.winfo_viewable(): app.wait_visibility()
            app.update()
            settings = app.views['settings']
            settings.about_button.invoke()
            about = settings._about_dialog
            wait_until(about.winfo_viewable)
            assert about.profile['name'] == 'Nguyễn Công Trung'
            assert about.profile['github_url'] == 'https://github.com/Nguyen-Cong-Trung'
            assert about.profile['email'] == 'trungcong0106a7@gmail.com'
            assert about.profile['linkedin'] == 'https://www.linkedin.com/in/nguyencongtrung'
            assert settings._open_about() is about, 'About must reuse its open window'
            with patch('ui.about_dialog.webbrowser.open', return_value=True) as browser:
                about.github_button.invoke()
                browser.assert_called_once_with(about.profile['github_url'], new=2)
            with patch('ui.about_dialog.webbrowser.open', return_value=True) as browser:
                about.contact_buttons['linkedin'].invoke()
                browser.assert_called_once_with(about.profile['linkedin'], new=2)
            with patch.object(about, 'clipboard_clear'), patch.object(about, 'clipboard_append') as copy:
                about.contact_buttons['email'].invoke()
                copy.assert_called_once_with(about.profile['email'])
            about.destroy()
            reopened = settings._open_about()
            assert reopened is not about and reopened.winfo_exists()
            reopened.destroy()
            from utils.constants import SOUND_TYPES, SOUND_DESCRIPTIONS
            sound_view = app.views['sound']
            for theme in ('light', 'dark'):
                app.views['settings'].set_theme(theme)
                for size in ('900x600', '1240x800'):
                    app.geometry(size)
                    app.show_view('sound')
                    wait_until(lambda: all(card.description_label._label.winfo_ismapped()
                        and card.description_label._label.winfo_width() >= card.description_label._label.winfo_reqwidth()
                        and card.description_label._label.winfo_height() >= card.description_label._label.winfo_reqheight()
                        for card in sound_view.cards))
                    for card in sound_view.cards:
                        if card.sound_type in SOUND_TYPES:
                            assert card.description_label.cget('text') == SOUND_DESCRIPTIONS[card.sound_type]
            from datetime import date
            from core.planner import PlanTask, PlannerStore
            from ui.planner_view import TaskDialog
            planner=app.views['planner']
            planner.select_day(date(2099,10,19))
            app.show_view('planner')
            planner.quick_entry.insert(0,'Quick task')
            planner.quick_add()
            assert len(planner.store.list('2099-10-19'))==1
            draft=TaskDialog(planner,app.db,PlanTask(day='2099-10-19'),planner.refresh)
            app.update()
            draft.save()
            assert draft.winfo_exists() and draft.error.cget('text'), 'Empty task should stay open with validation'
            draft.title_entry.insert(0,'Write a clear proposal with a long title that wraps cleanly within the agenda card')
            draft.time_entry.insert(0,'09:30')
            draft.minutes_entry.delete(0,'end')
            draft.minutes_entry.insert(0,'60')
            draft.mode.set('Mode · Deep Work')
            draft.add_step('Outline',True)
            draft.add_step('Draft')
            draft.save()
            app.update()
            tasks=planner.store.list('2099-10-19')
            planned=next(task for task in tasks if task.start_time)
            assert planned.minutes==60 and planned.checklist[0]['done']
            planner.expand(planned.id)
            planner.toggle_step(planned.id,1,True)
            assert all(step['done'] for step in planner.store.get(planned.id).checklist)
            from datetime import datetime
            with patch('ui.planner_view.datetime',wraps=datetime) as frozen_clock:
                frozen_clock.now.return_value=datetime(2099,10,19,8,0)
                planner.refresh()
                existing_rows=tuple(planner.rows.winfo_children())
                planner.refresh()
                assert existing_rows==tuple(planner.rows.winfo_children()), 'Unchanged planner refresh should preserve rows and scroll state'
                planner.store.step(planned.id,1,False)
                planner.refresh()
                assert existing_rows!=tuple(planner.rows.winfo_children()), 'Changed checklist must invalidate planner rows'
                planner.store.step(planned.id,1,True)
            for theme in ('light','dark'):
                app.views['settings'].set_theme(theme)
                for geometry in ('900x600','1240x800'):
                    app.geometry(geometry)
                    app.update()
                    assert planner.quick_entry.winfo_width()>120
                    assert all(day.winfo_width()>30 for day in planner.day_buttons)
                    assert planner.rows.winfo_height()>75, 'Agenda should remain usable at minimum window size'
                    assert planner.day_buttons[-1].winfo_rootx()+planner.day_buttons[-1].winfo_width() <= app.winfo_rootx()+app.winfo_width()
            planner.start_focus(planned.id)
            assert app.timer_engine.state==TimerState.FOCUSING
            assert app.timer_engine.focus_duration==50, 'Focus uses the linked mode, not the planning estimate'
            assert app.views['timer']._planned_task==planned.title
            app.stop_focus()
            assert not app.views['timer']._planned_task
            planner.toggle(planned.id,True)
            planner.set_filter('Done')
            assert planner.store.get(planned.id).completed
            planner.set_filter('All')
            reminder=planner.store.save(PlanTask(title='Reminder smoke',start_time='00:00'))
            app._show_notification.reset_mock()
            app._check_planner_reminders()
            assert 'Reminder smoke' in app.planner_message.cget('text')
            app._check_planner_reminders()
            assert app._show_notification.call_count==1, 'Reminder must not repeat'
            planner.store.delete(reminder)
            app.planner_banner.pack_forget()
            app._on_mode_selected('Default')
            stats_view = app.views['stats']
            assert stats_view._canvas.winfo_exists(), 'Statistics background canvas was destroyed'
            assert stats_view._canvas is not stats_view._chart_canvas, 'Chart must not replace the frame canvas'
            customizer = app.views['customizer']
            customizer.refresh_modes()
            mode_cards=tuple(customizer._mode_cards)
            customizer.refresh_modes()
            assert mode_cards==tuple(customizer._mode_cards), 'Unchanged modes should preserve existing cards'
            from ui.customizer_view import ModeDialog
            editor = ModeDialog(app, app.db, mode=app.db.get_mode_by_name('Deep Work'))
            if not editor.actions.winfo_viewable(): editor.actions.wait_visibility()
            app.update()
            assert abs(editor.focus_entry.winfo_width() - editor.sessions_entry.winfo_width()) <= 1, 'Timing fields must have equal widths'
            assert editor.focus_entry.winfo_rootx() == editor.short_break_entry.winfo_rootx(), 'Timing columns must align'
            picker = editor.sound_dropdown
            picker._open_dropdown_menu()
            app.update()
            assert picker._picker.winfo_exists()
            picker._move(1)
            picker._choose(1)
            assert editor.sound_var.get() == picker.cget('values')[1]
            assert picker._picker is None
            assert app.grab_current() == editor, 'Closing a dropdown must restore its modal dialog grab'
            picker.configure(values=[f'Sound {i}' for i in range(20)])
            picker._open_dropdown_menu()
            app.update()
            picker._move(19)
            assert picker._picker_index == 19
            picker._picker.focus_force()
            app.update()
            picker._picker.event_generate('<Escape>')
            app.update()
            assert picker._picker is None
            editor.destroy()
            import json
            whitelist_config = constants.load_config()
            whitelist_config['hardcore_sites'] = ['whitelist.example', 'second.example']
            whitelist_config['hardcore_apps'] = ['Distracting.exe']
            constants.save_config(whitelist_config)
            editor = ModeDialog(app, app.db)
            if not editor.actions.winfo_viewable(): editor.actions.wait_visibility()
            editor.name_entry.insert(0, 'Whitelist fixture')
            editor.whitelist_switch.toggle()
            assert editor.sites_box.get('1.0', 'end-1c') == 'whitelist.example\nsecond.example'
            assert editor.apps_box.get('1.0', 'end-1c') == 'Distracting.exe'
            editor._save()
            saved_mode = app.db.get_mode_by_name('Whitelist fixture')
            assert saved_mode.whitelist_mode
            assert json.loads(saved_mode.blocked_sites) == whitelist_config['hardcore_sites']
            assert json.loads(saved_mode.blocked_apps) == whitelist_config['hardcore_apps']
            for geometry, columns in (('900x600', 1), ('1240x800', 2)):
                app.geometry(geometry)
                app.show_view('customizer')
                app.update()
                try:
                    wait_until(lambda:customizer._mode_columns==columns and app.version_label.winfo_ismapped())
                except AssertionError:
                    print('REFLOW DIAGNOSTIC',geometry,app.geometry(),app.state(),
                        customizer.list_frame.winfo_width(),customizer._mode_columns,columns,
                        customizer.winfo_viewable(),flush=True)
                    raise
                assert customizer._mode_columns == columns, 'Mode cards must reflow at narrow widths'
                settings_nav=app.nav_buttons['settings']
                assert settings_nav.winfo_rooty()+settings_nav.winfo_height() <= app.sidebar_frame.winfo_rooty()+app.sidebar_frame.winfo_height(), 'Settings navigation is clipped on a small window'
                assert app.version_label.winfo_ismapped(), 'Sidebar footer is hidden'
                for card in customizer._mode_cards:
                    assert card.winfo_x() + card.winfo_width() <= customizer.list_frame.winfo_width(), 'Mode card extends beyond the page'
                app.show_view('blocker')
                app.update()
                blocker = app.views['blocker']
                assert blocker.web_entry.winfo_rootx() + blocker.web_entry.winfo_width() < app.winfo_rootx() + app.winfo_width(), 'Blocker input is clipped'
                blocker._switch_tab('app')
                app.update_idletasks()
                assert blocker.tab_app.winfo_ismapped()
                blocker._switch_tab('web')
            assert not hasattr(customizer, 'sound_list_frame'), 'Sound library belongs in Sound Studio'
            rows = [w for w in app.views["sound"].sound_list_frame.winfo_children() if int(w.grid_info().get('row', -1)) in (0, 2)]
            assert len(rows) == 2, 'Imported sound rows must occupy distinct rows'
            from ui.design import MaterialButton, MaterialFrame, BRANDING
            assert app._iconbitmap_method_called
            from PIL import Image
            with Image.open(BRANDING / 'focus.ico') as icon:
                assert {(16, 16), (32, 32), (256, 256)} <= icon.ico.sizes()
            assert (BRANDING / 'focus-logo.png').exists()
            assert isinstance(app.views['timer'].center_frame, MaterialFrame)
            assert isinstance(app.views['timer'].start_btn, MaterialButton)
            surface=app.views['timer'].center_frame
            surface._draw()
            depth_ids=surface._canvas.find_withtag('material-depth')
            surface._draw()
            assert depth_ids==surface._canvas.find_withtag('material-depth'), 'Unchanged material surface should reuse its bevel'
            app.views['timer'].start_btn._on_enter()
            app.views['timer'].start_btn._on_leave()
            assert app.views['timer'].center_frame._canvas.find_withtag('material-depth')
            app.show_view('timer')
            timer = app.views['timer']
            for geometry in ('900x600', '1240x800'):
                app.geometry(geometry)
                app.update_idletasks()
                timer._layout_hero()
                app.update_idletasks()
                assert timer.hero_copy.winfo_x() + timer.hero_copy.winfo_width() < timer.progress_circle.winfo_x(), f'Focus copy overlaps the clock at {geometry}: copy={timer.hero_copy.winfo_x(), timer.hero_copy.winfo_width()}, clock={timer.progress_circle.winfo_x(), timer.progress_circle.winfo_width()}, card={timer.center_frame.winfo_width()}'
                assert timer.start_btn.winfo_rooty() + timer.start_btn.winfo_height() <= app.winfo_rooty() + app.winfo_height(), 'Primary action is clipped'
            app.views['timer']._start_focus()
            app.views['timer']._pause_resume()
            remaining = app.timer_engine.remaining_seconds
            original_window = app.winfo_id()
            for theme in ('light', 'dark'):
                app.views['settings'].set_theme(theme)
                app.update_idletasks()
                assert app.timer_engine.state == TimerState.PAUSED
                assert app.timer_engine.remaining_seconds == remaining
                assert app.winfo_id() == original_window
            assert timer.hero_title.winfo_reqwidth() <= timer.hero_copy.winfo_width(), 'Paused heading is clipped'
            app.views['timer']._pause_resume()
            app.views['timer']._skip()
            assert app.timer_engine.state == TimerState.SHORT_BREAK
            app.update_idletasks()
            assert timer.tip_label.winfo_y() + timer.tip_label.winfo_reqheight() <= timer.hero_copy.winfo_height(), 'Break tip is clipped'
            app.blocking.pool.submit(lambda: None).result(timeout=5)
            app.site_blocker.unblock.assert_called()
            app.views['timer']._stop()
            app.toggle_mini_player()
            app.update_idletasks()
            assert not app.topbar.winfo_ismapped()
            assert not app.views['timer'].hero_copy.winfo_ismapped()
            app.toggle_mini_player()
            app.update_idletasks()
            assert app.topbar.winfo_ismapped()
            app.show_view('shutdown')
            app.views['shutdown']._preset(90)
            assert app.views['shutdown'].countdown.cget('text') == '01:30:00'
            app.shutdown_scheduler.schedule(3600)
            app.views['shutdown']._render()
            assert app.views['shutdown'].schedule_button.cget('state') == 'disabled'
            app.shutdown_scheduler.cancel()
            app.views['shutdown']._render()
            assert app.views['shutdown'].schedule_button.cget('state') == 'normal'
            import numpy as np
            sound_card=app.views['sound'].cards[0]
            app.views['sound'].refresh_playback()
            with patch.object(sound_card.toggle_btn,'configure',wraps=sound_card.toggle_btn.configure) as paint_button:
                app.views['sound'].refresh_playback()
                app.views['sound'].refresh_playback()
                assert not paint_button.called, 'Idle audio polling should not repaint buttons'
            with patch.object(app.sound_engine,'_get_or_create_buffer',return_value=np.zeros((32,2),dtype=np.float32)), patch('core.sound_engine.sd.OutputStream'):
                sound_card._toggle_play()
                wait_until(lambda:not sound_card._pending)
                assert sound_card._is_playing
                assert sound_card.vol_slider.cget('state') == 'normal'
                sound_card._toggle_play()
                wait_until(lambda:not sound_card._pending)
                assert not sound_card._is_playing
            with patch.object(app.hotkeys,'enable',return_value=True) as enable, patch.object(app.hotkeys,'disable') as disable:
                settings=app.views['settings']
                settings.hotkeys_switch.toggle()
                assert app.config['global_hotkeys']
                enable.assert_called_once()
                settings.hotkeys_switch.toggle()
                assert not app.config['global_hotkeys']
                disable.assert_called_once()
            locked_id = app.db.save_mode(FocusMode(name='Locked fixture',dead_lock=True,focus_minutes=1))
            app._on_modes_changed()
            app._on_mode_selected('Locked fixture')
            timer._start_focus()
            timer._stop()
            assert app.timer_engine.state == TimerState.FOCUSING
            timer._skip()
            assert app.timer_engine.state == TimerState.FOCUSING
            with patch('ui.app.CTkMessagebox') as confirm:
                confirm.return_value.get.return_value = 'End and unblock'
                app.emergency_unblock()
            assert app.timer_engine.state == TimerState.IDLE
            app._on_mode_selected('Default')
            with patch.object(app.tray,'available',True), patch.object(app.tray,'update'):
                app.testing = False
                app._on_close()
                assert app.state() == 'withdrawn'
                app.testing = True
                app._tray_action('open')
                wait_until(lambda: app.state() == 'normal')
            archive = str(Path(temporary)/'workspace.zip')
            def wait_for_data():
                deadline = time.monotonic()+30
                while app._data_busy and time.monotonic()<deadline:
                    app.update()
                    time.sleep(.01)
                assert not app._data_busy, 'Workspace operation did not finish'
            with patch('tkinter.filedialog.asksaveasfilename',return_value=archive):
                app.workspace_action('backup')
                wait_for_data()
            assert Path(archive).is_file()
            app.db.save_mode(FocusMode(name='After backup'))
            with patch('tkinter.filedialog.askopenfilename',return_value=archive), patch('ui.app.CTkMessagebox') as confirm:
                confirm.return_value.get.return_value = 'Restore workspace'
                app.workspace_action('restore')
                wait_for_data()
            assert app.db.get_mode_by_name('After backup') is None
            assert len(app.db.get_all_custom_sounds()) == 2
            assert len(app.views['planner'].store.list('2099-10-19'))==2, 'Planner tasks must survive workspace restore'
            app.show_view('history')
            app.update()
            wait_until(lambda:app.views['history'].rows.winfo_ismapped())
            assert app.views['history'].rows.winfo_ismapped(), ('History not mapped',app.state(),app.geometry(),
                app.views['history'].winfo_manager(),app.views['history'].winfo_height(),app.main_frame.winfo_height())
            history_rows=tuple(app.views['history'].rows.winfo_children())
            app.views['history'].refresh()
            assert history_rows==tuple(app.views['history'].rows.winfo_children()), 'Unchanged history should preserve rows'
            assert not failures, failures
            print('UI SMOKE PASSED: 9 views, both themes, planner CRUD/checklists/reminders/linked focus, timer controls, break cleanup, logo/icon, materials, aligned rows, responsive layout, mini player, mocked shutdown/cancel, locks, tray lifecycle, workspace backup/restore, history')
        except BaseException:
            import traceback
            traceback.print_exc()
            failures.append(sys.exc_info())
        finally:
            app.timer_engine.stop()
            app._on_close()
            assert 'smoke.example' in fixture_db.get_mode_by_name('Default').blocked_sites

    if "--shutdown" in sys.argv:
        app.show_view("shutdown")
    app.update()
    app.after(180000 if "--preview" in sys.argv else 1500, check)
    app.mainloop()
    if failures:
        raise SystemExit(1)
faulthandler.cancel_dump_traceback_later()
