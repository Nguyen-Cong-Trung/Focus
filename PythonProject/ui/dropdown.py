"""A shared rounded picker with keyboard navigation and modal-safe dismissal."""
import sys
import tkinter as tk
import tkinter.font as tkfont
import customtkinter as ctk
from utils.constants import (BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, SEPARATOR_COLOR,
                             HOVER_BG, SELECTED_BG, ACCENT_CUSTOM)


class FocusDropdown(ctk.CTkOptionMenu):
    def __init__(self, master, menu_title="SELECT MODE", **kwargs):
        self._picker = None
        self._picker_root_binding = None
        self._previous_grab = None
        self._picker_focus_job = None
        self.menu_title = menu_title
        kwargs.setdefault("corner_radius", 10)
        kwargs.setdefault("height", 40)
        kwargs.setdefault("font", ("Inter", 13))
        kwargs.setdefault("fg_color", BG_CARD)
        kwargs.setdefault("button_color", kwargs["fg_color"])
        kwargs.setdefault("button_hover_color", HOVER_BG)
        kwargs.setdefault("text_color", TEXT_PRIMARY)
        super().__init__(master, **kwargs)
        self.bind("<Down>", lambda e: self._open_dropdown_menu())
        self.bind("<space>", lambda e: self._open_dropdown_menu())
        self.bind("<Return>", lambda e: self._open_dropdown_menu())
        self._text_label.configure(takefocus=1)

    def _open_dropdown_menu(self):
        if self._state == "disabled" or not self._values:
            return
        if self._picker is not None:
            self._close_picker()
            return
        popup = tk.Toplevel(self)
        self._picker = popup
        popup.withdraw()
        popup.overrideredirect(True)
        popup.transient(self.winfo_toplevel())
        mask = "#010203"
        popup.configure(bg=mask)
        if sys.platform == "win32":
            popup.wm_attributes("-transparentcolor", mask)
        self._previous_grab = self.grab_current()
        panel = ctk.CTkFrame(popup, fg_color=BG_CARD, bg_color=mask,
                             corner_radius=12, border_width=1, border_color=SEPARATOR_COLOR)
        panel.pack(fill="both", expand=True)
        ctk.CTkLabel(panel, text=self.menu_title, height=16, anchor="w",
                     font=("Inter", 9, "bold"), text_color=TEXT_SECONDARY).pack(fill="x", padx=16, pady=(13, 8))
        font = tkfont.Font(family="Inter", size=13)
        scale = self._get_widget_scaling()
        width = max(self.winfo_width(), round(240 * scale), max(font.measure(v) for v in self._values) + round(64 * scale))
        width = min(width, round(420 * scale), self.winfo_screenwidth()-24)
        height = round((48 + min(len(self._values), 7) * 42) * scale)
        if len(self._values) > 7:
            body = ctk.CTkScrollableFrame(panel, fg_color="transparent", corner_radius=0)
        else:
            body = ctk.CTkFrame(panel, fg_color="transparent", corner_radius=0)
        body.pack(fill="both", expand=True, padx=6, pady=(0, 7))
        self._picker_rows = []
        self._picker_index = self._values.index(self.get()) if self.get() in self._values else 0
        for index, value in enumerate(self._values):
            selected = value == self.get()
            display = value
            while display and font.measure(display) > width - round(68 * scale):
                display = display[:-1]
            if display != value:
                display = display.rstrip() + "…"
            row = ctk.CTkButton(body, text=display, height=36, anchor="w", corner_radius=7,
                border_spacing=12, font=("Inter", 13), text_color=TEXT_PRIMARY,
                fg_color=SELECTED_BG if selected else "transparent", hover_color=HOVER_BG,
                command=lambda i=index: self._choose(i))
            row.pack(fill="x", pady=3)
            if selected:
                mark = ctk.CTkLabel(row, text="✓", width=22, height=20,
                                    text_color=ACCENT_CUSTOM, font=("Inter", 13, "bold"))
                mark.place(relx=1, rely=.5, anchor="e", x=-10)
                mark.bind("<Button-1>", lambda e, i=index: self._choose(i))
            self._picker_rows.append(row)
        x = min(self.winfo_rootx(), self.winfo_screenwidth() - width - 12)
        below = self.winfo_rooty() + self.winfo_height() + 6
        y = below if below + height < self.winfo_screenheight() - 12 else max(12, self.winfo_rooty() - height - 6)
        popup.geometry(f"{width}x{height}+{max(12, x)}+{y}")
        popup.bind("<Escape>", lambda e: self._close_picker())
        popup.bind("<Tab>", lambda e: self._close_picker())
        popup.bind("<Up>", lambda e: self._move(-1))
        popup.bind("<Down>", lambda e: self._move(1))
        popup.bind("<Home>", lambda e: self._move(-len(self._values)))
        popup.bind("<End>", lambda e: self._move(len(self._values)))
        popup.bind("<Return>", lambda e: self._choose(self._picker_index))
        popup.bind("<ButtonPress-1>", self._outside_click, add="+")
        popup.bind("<FocusOut>", self._queue_focus_check)
        root = self.winfo_toplevel()
        self._picker_root_binding = root.bind("<Configure>", lambda e: self._close_picker() if e.widget == root else None, add="+")
        popup.deiconify()
        popup.lift()
        popup.grab_set()
        popup.focus_set()

    def _move(self, offset):
        self._picker_index = max(0, min(len(self._values)-1, self._picker_index + offset))
        for index, row in enumerate(self._picker_rows):
            row.configure(fg_color=HOVER_BG if index == self._picker_index else
                          (SELECTED_BG if self._values[index] == self.get() else "transparent"))
        row = self._picker_rows[self._picker_index]
        body = row.master
        if isinstance(body, ctk.CTkScrollableFrame):
            canvas = body._parent_canvas
            top = row.winfo_y()
            if top < canvas.canvasy(0) or top + row.winfo_height() > canvas.canvasy(canvas.winfo_height()):
                canvas.yview_moveto(top / max(1, body.winfo_height()))
        return "break"

    def _outside_click(self, event):
        popup = self._picker
        if popup and not (popup.winfo_rootx() <= event.x_root < popup.winfo_rootx()+popup.winfo_width()
                          and popup.winfo_rooty() <= event.y_root < popup.winfo_rooty()+popup.winfo_height()):
            self._close_picker()

    def _dismiss_unfocused(self):
        self._picker_focus_job = None
        if self._picker and self._picker.focus_displayof() is None:
            self._close_picker()

    def _queue_focus_check(self, event):
        if self._picker and self._picker_focus_job is None:
            self._picker_focus_job = self.after_idle(self._dismiss_unfocused)

    def _choose(self, index):
        value = self._values[index]
        self._close_picker()
        self._dropdown_callback(value)

    def _close_picker(self):
        popup, self._picker = self._picker, None
        if popup is None:
            return
        if self._picker_focus_job is not None:
            self.after_cancel(self._picker_focus_job)
            self._picker_focus_job = None
        if self._picker_root_binding:
            self.winfo_toplevel().unbind("<Configure>", self._picker_root_binding)
            self._picker_root_binding = None
        popup.grab_release()
        popup.destroy()
        if self._previous_grab is not None and self._previous_grab.winfo_exists():
            self._previous_grab.grab_set()
        self._previous_grab = None

    def configure(self, require_redraw=False, **kwargs):
        if "values" in kwargs or kwargs.get("state") == "disabled":
            self._close_picker()
        super().configure(require_redraw=require_redraw, **kwargs)

    def destroy(self):
        self._close_picker()
        super().destroy()
