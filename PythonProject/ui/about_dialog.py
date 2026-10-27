"""Creator information and links, presented in the workspace's visual style."""
from ui.metrics import (
    CONTROL_FONT_SIZE, CONTROL_HEIGHT, PRIMARY_CONTROL_HEIGHT
)
import webbrowser
from urllib.parse import urlsplit

import customtkinter as ctk

from ui.design import MaterialButton, brand_image, set_window_brand
from ui.panels import label, surface, fit_wrap
from utils.constants import (APP_NAME, APP_SUITE, APP_VERSION, BG_PRIMARY,
    INPUT_BG, HOVER_BG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_COLOR, ACCENT_HOVER, ICE)


class AboutDialog(ctk.CTkToplevel):
    def __init__(self, parent, profile):
        super().__init__(parent)
        self.profile = profile
        self.title(f'About {APP_NAME}')
        set_window_brand(self)
        self.configure(fg_color=BG_PRIMARY)
        self.geometry('660x650')
        self.minsize(520, 440)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.bind('<Escape>', lambda event: self.destroy())

        content = ctk.CTkScrollableFrame(self, fg_color=BG_PRIMARY, corner_radius=0)
        content.grid(row=0, column=0, sticky='nsew', padx=8, pady=(8, 0))
        content.grid_columnconfigure(0, weight=1)
        self._wrapped = []

        hero = surface(content)
        hero.grid(row=0, column=0, sticky='ew', padx=18, pady=(18, 16))
        hero.grid_columnconfigure(1, weight=1)
        label(hero, '', image=brand_image(68), corner_radius=0).grid(
            row=0, column=0, rowspan=3, padx=(24, 20), pady=24)
        label(hero, APP_SUITE.upper(), 10, ICE, True, corner_radius=0).grid(
            row=0, column=1, sticky='w', pady=(22, 4))
        label(hero, APP_NAME, 32, bold=True, corner_radius=0).grid(row=1, column=1, sticky='w')
        label(hero, f'Version {APP_VERSION}', 12, TEXT_SECONDARY, corner_radius=0).grid(
            row=2, column=1, sticky='w', pady=(4, 24))

        creator = surface(content)
        creator.grid(row=1, column=0, sticky='ew', padx=18, pady=(0, 16))
        creator.grid_columnconfigure(0, weight=1)
        label(creator, 'CREATED BY', 10, ICE, True, corner_radius=0).grid(
            row=0, column=0, sticky='w', padx=24, pady=(22, 8))
        self.creator_name = self._text(creator, profile['name'], 24, bold=True)
        self.creator_name.grid(row=1, column=0, sticky='ew', padx=24)
        if profile.get('bio'):
            self.bio = self._text(creator, profile['bio'], 13, color=TEXT_SECONDARY)
            self.bio.grid(row=2, column=0, sticky='ew', padx=24, pady=(10, 0))
        contacts = []
        if profile.get('email'):
            contacts.append(('email', 'EMAIL', profile['email'], 'Copy email', self._copy_email))
        if profile.get('linkedin'):
            contacts.append(('linkedin', 'LINKEDIN', profile['linkedin'], 'Open profile  ↗',
                lambda: self._open_link(profile['linkedin'])))
        if profile.get('website'):
            contacts.append(('website', 'WEBSITE', profile['website'], 'Visit website  ↗',
                lambda: self._open_link(profile['website'])))
        contact_frame = ctk.CTkFrame(creator, fg_color='transparent')
        contact_frame.grid(row=3, column=0, sticky='ew', padx=24, pady=(16 if contacts else 0, 20))
        contact_frame.grid_columnconfigure(0, weight=1)
        self.contact_buttons = {}
        for row, (key, title, value, action, command) in enumerate(contacts):
            line = ctk.CTkFrame(contact_frame, fg_color='transparent')
            line.grid(row=row, column=0, sticky='ew', pady=(0 if row == 0 else 16, 0))
            line.grid_columnconfigure(0, weight=1)
            label(line, title, 10, TEXT_MUTED, True, corner_radius=0).grid(row=0, column=0, sticky='w')
            self._text(line, value, 12, color=TEXT_SECONDARY).grid(
                row=1, column=0, sticky='ew', pady=(4, 0))
            button = ctk.CTkButton(line, text=action, width=112, height=CONTROL_HEIGHT,
                fg_color=INPUT_BG, hover_color=HOVER_BG, text_color=TEXT_PRIMARY,
                font=('Inter', CONTROL_FONT_SIZE), command=command)
            button.grid(row=0, column=1, rowspan=2, padx=(16, 0))
            self.contact_buttons[key] = button

        discover = surface(content)
        discover.grid(row=2, column=0, sticky='ew', padx=18, pady=(0, 16))
        discover.grid_columnconfigure(0, weight=1)
        label(discover, 'More from the creator', 17, bold=True, corner_radius=0).grid(
            row=0, column=0, sticky='w', padx=24, pady=(22, 6))
        self._text(discover, 'Discover more tools and get the latest releases on GitHub.',
            12, color=TEXT_SECONDARY).grid(row=1, column=0, sticky='ew', padx=24)
        self.github_label = self._text(discover, profile['github_url'], 12, color=ICE)
        self.github_label.grid(row=2, column=0, sticky='ew', padx=24, pady=(12, 16))
        self.github_button = MaterialButton(discover, text='Explore more tools  ↗',
            height=PRIMARY_CONTROL_HEIGHT, font=('Inter', CONTROL_FONT_SIZE, 'bold'), fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER, text_color='white',
            command=lambda: self._open_link(profile['github_url']))
        self.github_button.grid(row=3, column=0, sticky='ew', padx=24)
        self.copy_button = ctk.CTkButton(discover, text='Copy GitHub link', height=CONTROL_HEIGHT,
            fg_color=INPUT_BG, hover_color=HOVER_BG, text_color=TEXT_PRIMARY,
            font=('Inter', CONTROL_FONT_SIZE), command=self._copy_link)
        self.copy_button.grid(row=4, column=0, sticky='ew', padx=24, pady=(8, 20))

        if profile.get('copyright'):
            self._text(content, profile['copyright'], 11, color=TEXT_MUTED).grid(
                row=3, column=0, sticky='ew', padx=24, pady=(12, 18))

        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.grid(row=1, column=0, sticky='ew', padx=26, pady=(10, 18))
        footer.grid_columnconfigure(0, weight=1)
        self.status = label(footer, '', 11, ICE, corner_radius=0, wraplength=330)
        self.status.grid(row=0, column=0, sticky='w', padx=(0, 12))
        ctk.CTkButton(footer, text='Close', width=88, height=CONTROL_HEIGHT,
            fg_color=INPUT_BG, hover_color=HOVER_BG, text_color=TEXT_PRIMARY,
            command=self.destroy, font=("Inter", CONTROL_FONT_SIZE)).grid(row=0, column=1)
        content.bind('<Configure>', self._fit_text, add='+')
        content._parent_canvas.bind('<Configure>', self._fit_text, add='+')
        self._wrap_job = self.after(100, self._fit_text)

    def destroy(self):
        job = getattr(self, '_wrap_job', None)
        if job is not None:
            self.after_cancel(job)
            self._wrap_job = None
        super().destroy()

    def _text(self, parent, text, size, color=TEXT_PRIMARY, bold=False):
        widget = label(parent, text, size, color, bold, corner_radius=0,
            wraplength=400, justify='left')
        widget.bind('<Configure>', lambda event: fit_wrap(widget,
            max(120, widget._reverse_widget_scaling(event.width) - 2)), add='+')
        self._wrapped.append(widget)
        return widget

    def _fit_text(self, event=None):
        for widget in self._wrapped:
            if widget.winfo_exists():
                width = widget._reverse_widget_scaling(widget.winfo_width()) - 2
                fit_wrap(widget, max(160, width))

    def _open_link(self, url):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname:
            self.status.configure(text='This link is unavailable. Copy the GitHub link instead.')
            return
        try:
            opened = webbrowser.open(url, new=2)
        except (webbrowser.Error, OSError):
            opened = False
        self.status.configure(text='Opened in your browser.' if opened else
            'Could not open the browser. You can copy the link instead.')

    def _copy(self, text, message):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status.configure(text=message)

    def _copy_link(self):
        self._copy(self.profile['github_url'], 'GitHub link copied.')

    def _copy_email(self):
        self._copy(self.profile['email'], 'Contact email copied.')
