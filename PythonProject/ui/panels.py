"""Quiet, consistent page furniture for the workspace panels."""
import customtkinter as ctk
from ui.design import MaterialFrame
from utils.constants import BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, SEPARATOR_COLOR, ICE


def label(parent, text, size=13, color=TEXT_PRIMARY, bold=False, **kwargs):
    kwargs.setdefault("height", 0)
    return ctk.CTkLabel(parent, text=text, font=("Inter", size, "bold" if bold else "normal"),
                        text_color=color, anchor="w", **kwargs)


def fit_wrap(widget,width):
    """Height-only Configure events must not redraw/reflow unchanged text."""
    width=round(width)
    if float(str(widget.cget('wraplength')))!=width:
        widget.configure(wraplength=width)


class PageHeader(ctk.CTkFrame):
    def __init__(self, parent, category, title, description):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        label(self, category, 10, ICE, True).grid(row=0, column=0, sticky="w", pady=(0, 7))
        label(self, title, 30, bold=True).grid(row=1, column=0, sticky="w")
        self.description = label(self, description, 13, TEXT_SECONDARY, justify="left")
        self.description.grid(row=2, column=0, sticky="w", pady=(5, 0))
        self.bind("<Configure>", lambda e: fit_wrap(self.description,max(220,e.width-10)))


def surface(parent):
    return MaterialFrame(parent, fg_color=BG_CARD, corner_radius=14,
                         border_width=1, border_color=SEPARATOR_COLOR)


def rule(parent):
    return ctk.CTkFrame(parent, fg_color=SEPARATOR_COLOR, height=1, corner_radius=0)
