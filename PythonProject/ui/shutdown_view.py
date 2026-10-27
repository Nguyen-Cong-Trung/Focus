from ui.metrics import (
    CONTROL_FONT_SIZE, LARGE_CONTROL_HEIGHT, PRIMARY_CONTROL_HEIGHT
)
from ui.design import MaterialFrame
from ui.design import MaterialButton
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from utils.constants import (BG_PRIMARY, BG_CARD, ACCENT_COLOR, ACCENT_HOVER,
                             TEXT_PRIMARY, TEXT_SECONDARY, INPUT_BG, HOVER_BG, SEPARATOR_COLOR, ICE)


class ShutdownView(ctk.CTkScrollableFrame):
    def __init__(self, parent, scheduler):
        super().__init__(parent, fg_color=BG_PRIMARY)
        self.scheduler = scheduler
        self._busy = False
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text='Shutdown Timer', font=('Inter', 30, 'bold'),
                     text_color=TEXT_PRIMARY).grid(row=0, column=0, sticky='w', padx=28, pady=(24, 6))
        ctk.CTkLabel(self, text='Wrap up your workday on your schedule.',
                     text_color=TEXT_SECONDARY, font=('Inter', 15)).grid(row=1, column=0, sticky='w', padx=28)
        card = MaterialFrame(self, fg_color=BG_CARD, corner_radius=16, border_width=1, border_color=SEPARATOR_COLOR)
        card.grid(row=2, column=0, sticky='ew', padx=28, pady=24)
        ctk.CTkLabel(card, text='END YOUR DAY, ON YOUR TERMS', text_color=ICE,
                     font=('Inter', 13, 'bold')).pack(pady=(25, 8))
        self.countdown = ctk.CTkLabel(card, text='01:00:00', font=('Inter', 60, 'bold'), text_color=TEXT_PRIMARY)
        self.countdown.pack(pady=8)
        self.status = ctk.CTkLabel(card, text='No shutdown scheduled in this app session', text_color=TEXT_SECONDARY)
        self.status.pack(pady=(0, 22))
        presets = ctk.CTkFrame(self, fg_color='transparent')
        presets.grid(row=3, column=0, padx=28, sticky='ew')
        presets.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.preset_buttons = {}
        for i, minutes in enumerate((30, 60, 90, 120)):
            button = MaterialButton(presets, text=f'{minutes} min', fg_color=BG_CARD, hover_color=HOVER_BG,
                          text_color=TEXT_PRIMARY, height=LARGE_CONTROL_HEIGHT, width=90,
                          command=lambda m=minutes: self._preset(m), border_width=1, border_color=SEPARATOR_COLOR, font=("Inter", CONTROL_FONT_SIZE))
            button.grid(row=0, column=i, padx=5, sticky='ew')
            self.preset_buttons[minutes] = button
        entry_row = ctk.CTkFrame(self, fg_color='transparent')
        entry_row.grid(row=4, column=0, padx=28, pady=20)
        self.hours, self.minutes = ctk.StringVar(value='1'), ctk.StringVar(value='0')
        self.entries = []
        entry_row.grid_columnconfigure((0, 1), weight=1, uniform='duration')
        for column, (variable, label) in enumerate(((self.hours, 'Hours'), (self.minutes, 'Minutes'))):
            field = ctk.CTkFrame(entry_row, fg_color='transparent')
            field.grid(row=0, column=column, sticky='ew', padx=8)
            ctk.CTkLabel(field, text=label, text_color=TEXT_SECONDARY, font=('Inter', 12)).pack(anchor='w', pady=(0, 6))
            entry = ctk.CTkEntry(field, textvariable=variable, width=144, height=46,
                                 justify='center', fg_color=INPUT_BG, font=('Inter', 20))
            entry.pack(fill='x')
            self.entries.append(entry)
        actions = ctk.CTkFrame(self, fg_color='transparent')
        actions.grid(row=5, column=0, padx=28, pady=(0, 18))
        self.schedule_button = MaterialButton(actions, text='Schedule shutdown', width=180, height=PRIMARY_CONTROL_HEIGHT, corner_radius=12,
                                            fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, command=self._schedule, font=("Inter", CONTROL_FONT_SIZE))
        self.schedule_button.pack(side='left', padx=6)
        MaterialButton(actions, text='Cancel shutdown', width=180, height=PRIMARY_CONTROL_HEIGHT, corner_radius=12,
                      fg_color=BG_CARD, hover_color=HOVER_BG, text_color=TEXT_PRIMARY,
                      command=self._cancel, font=("Inter", CONTROL_FONT_SIZE)).pack(side='left', padx=6)
        ctk.CTkLabel(self, text='Save your work first. Windows may force apps to close when the countdown ends.\n'
                     'The schedule stays active after Focus closes. Cancel also clears schedules set outside this app.',
                     text_color=TEXT_SECONDARY, wraplength=560, justify='center').grid(row=6, column=0, padx=28, pady=12)
        self._preview()
        self.hours.trace_add("write", self._preview)
        self.minutes.trace_add("write", self._preview)
        self._render()
        self._job = self.after(500, self._refresh)

    def _preview(self, *_):
        if self.scheduler.deadline:
            return
        try:
            hours, minutes = int(self.hours.get()), int(self.minutes.get())
            valid = 0 <= hours <= 87600 and 0 <= minutes <= 59
            self.countdown.configure(text=f'{hours:02d}:{minutes:02d}:00' if valid else '--:--:--')
            for duration, button in self.preset_buttons.items():
                selected = valid and hours * 60 + minutes == duration
                button.configure(fg_color=ACCENT_COLOR if selected else BG_CARD,
                                 text_color='#FFFFFF' if selected else TEXT_PRIMARY)
        except ValueError:
            self.countdown.configure(text='--:--:--')

    def _preset(self, minutes):
        if self.scheduler.deadline:
            return
        self.hours.set(str(minutes // 60))
        self.minutes.set(str(minutes % 60))
        self.countdown.configure(text=f'{minutes // 60:02d}:{minutes % 60:02d}:00')

    def _schedule(self):
        try:
            hours, minutes = int(self.hours.get()), int(self.minutes.get())
            if not 0 <= hours <= 87600 or not 0 <= minutes <= 59:
                raise ValueError('Enter hours from 0 to 87600 and minutes from 0 to 59.')
            seconds = hours * 3600 + minutes * 60
            if not 1 <= seconds <= self.scheduler.MAX_SECONDS:
                raise ValueError('Choose a delay greater than zero and no longer than 10 years.')
            answer = CTkMessagebox(title='Confirm shutdown', icon='warning',
                message=f'Your PC will shut down in {hours} hours and {minutes} minutes.\nSave your work before continuing.',
                option_1='Go back', option_2='Schedule shutdown')
            if answer.get() == 'Schedule shutdown':
                self._execute(lambda: self.scheduler.schedule(seconds))
        except Exception as exc:
            CTkMessagebox(title='Could not schedule shutdown', message=str(exc), icon='cancel')

    def _execute(self, function):
        if self._busy: return
        app = self.winfo_toplevel()
        if app._restoring or app._closing: return
        self._busy = True
        self._render()
        def done(error=None):
            self._busy = False
            self._preview()
            self._render()
            if error:
                CTkMessagebox(title='Shutdown schedule',message=str(error),icon='cancel')
        try:
            future = app.run_background(function,lambda _:done(),lambda exc:done(exc))
            if future is None:
                done(RuntimeError('Focus could not start the operation. Quit Focus and reopen it, then try again.'))
        except Exception as exc:
            done(exc)

    def _cancel(self):
        self._execute(self.scheduler.cancel)

    def _render(self):
        if not self._busy and self.scheduler.refresh():
            self._preview()
        active = self.scheduler.deadline is not None
        snapshot=(self.scheduler.deadline,self.scheduler.remaining_seconds if active else None,
            self.scheduler.restored,self._busy)
        if getattr(self,'_render_snapshot',None)==snapshot: return
        self._render_snapshot=snapshot
        self.schedule_button.configure(state='disabled' if active or self._busy else 'normal')
        for entry in self.entries:
            entry.configure(state='disabled' if active or self._busy else 'normal')
        if active:
            hours, rest = divmod(self.scheduler.remaining_seconds, 3600)
            minutes, seconds = divmod(rest, 60)
            self.countdown.configure(text=f'{hours:02d}:{minutes:02d}:{seconds:02d}')
            recorded = self.scheduler.deadline.strftime('%H:%M • %d/%m/%Y')
            if self.scheduler.restored:
                self.status.configure(text='Last recorded shutdown: '+recorded+'\nWindows state is unverified. Cancel to clear any pending schedule.')
            else:
                self.status.configure(text='Shutting down at '+recorded)
        else:
            self.status.configure(text='No shutdown recorded by Focus. External schedules may still exist.')
        if self._busy:
            self.status.configure(text='Updating the Windows shutdown schedule…')

    def _refresh(self):
        self._render()
        self._job = self.after(500, self._refresh)

    def destroy(self):
        self.after_cancel(self._job)
        super().destroy()
