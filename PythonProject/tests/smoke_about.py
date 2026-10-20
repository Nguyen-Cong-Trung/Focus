"""Check About layout and actions with fixture identity and mocked external effects."""
import faulthandler
from pathlib import Path
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
from ui.design import load_design
from ui.about_dialog import AboutDialog

faulthandler.dump_traceback_later(90, exit=True)
load_design()
root = ctk.CTk()
root.geometry('900x650')
root.update()
if not root.winfo_viewable():
    root.wait_visibility()
profile = {'name': 'A creator name long enough to wrap onto another line',
    'github_url': 'https://github.com/example',
    'bio': 'Independent tools for everyday work. ' * 6,
    'website': 'https://example.com', 'email': 'fixture@example.com',
    'linkedin': 'https://www.linkedin.com/in/example',
    'copyright': 'Copyright fixture — layout verification only.'}
dialog = AboutDialog(root, profile)
failures = []
root.report_callback_exception = lambda *error: failures.append(str(error))
cases = iter((theme, size) for theme in ('light', 'dark') for size in ('520x440', '660x650', '850x800'))
count = [0]
deadline = [0]


def verify():
    try:
        for widget in dialog._wrapped:
            native = widget._label
            assert native.winfo_ismapped(), widget.cget('text')
            assert native.winfo_width() >= native.winfo_reqwidth(), (widget.cget('text'), 'width', native.winfo_width(), native.winfo_reqwidth(), widget.winfo_geometry(), widget.cget('wraplength'))
            assert native.winfo_height() >= native.winfo_reqheight(), (widget.cget('text'), 'height', native.winfo_height(), native.winfo_reqheight(), widget.winfo_geometry())
        count[0] += 1
        advance()
    except AssertionError as error:
        if time.monotonic() < deadline[0]:
            root.after(100, verify)
        else:
            failures.append(repr(error))
            root.destroy()


def advance():
    case = next(cases, None)
    if case is None:
        with patch('ui.about_dialog.webbrowser.open', return_value=True) as browser:
            dialog.github_button.invoke()
            browser.assert_called_once_with(profile['github_url'], new=2)
        with patch.object(dialog, 'clipboard_clear'), patch.object(dialog, 'clipboard_append') as copy:
            dialog.copy_button.invoke()
            copy.assert_called_once_with(profile['github_url'])
            assert dialog.status.cget('text') == 'GitHub link copied.'
        with patch('ui.about_dialog.webbrowser.open', return_value=True) as browser:
            dialog.contact_buttons['linkedin'].invoke()
            browser.assert_called_once_with(profile['linkedin'], new=2)
        with patch.object(dialog, 'clipboard_clear'), patch.object(dialog, 'clipboard_append') as copy:
            dialog.contact_buttons['email'].invoke()
            copy.assert_called_once_with(profile['email'])
            assert dialog.status.cget('text') == 'Contact email copied.'
        with patch('ui.about_dialog.webbrowser.open', return_value=False):
            dialog.github_button.invoke()
            assert 'Could not open' in dialog.status.cget('text')
        with patch('ui.about_dialog.webbrowser.open') as browser:
            dialog._open_link('javascript:alert(1)')
            browser.assert_not_called()
        root.destroy()
        return
    theme, size = case
    deadline[0] = time.monotonic() + 10
    ctk.set_appearance_mode(theme)
    dialog.geometry(size)
    root.after(600, verify)


root.after(1000, advance)
root.mainloop()
assert not failures, failures
assert count[0] == 6, count
faulthandler.cancel_dump_traceback_later()
print('ABOUT PASSED: 6 theme/size combinations, long text, GitHub action, copy and browser failure')
