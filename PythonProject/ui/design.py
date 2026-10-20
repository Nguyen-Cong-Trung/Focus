"""Local fonts and small vector icons shared by the desktop interface."""
from pathlib import Path
import math
import os
import sys
from functools import lru_cache
import customtkinter as ctk
from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
BRANDING = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])) / 'branding'


@lru_cache(maxsize=8)
def brand_image(size=44):
    with Image.open(BRANDING / 'focus-logo.png') as source:
        logo = source.convert('RGBA')
    return ctk.CTkImage(light_image=logo, dark_image=logo, size=(size, size))


def set_window_brand(window):
    """Set the real Windows icon, independently of the in-app image."""
    window.iconbitmap(str(BRANDING / 'focus.ico'))


def _mix_color(widget, color, amount):
    resolved = widget._apply_appearance_mode(color)
    if resolved.startswith('#') and len(resolved)==7:
        return _mix_hex(resolved,amount)
    channels = tuple(channel // 256 for channel in widget.winfo_rgb(resolved))
    return _shade(channels,amount)


@lru_cache(maxsize=512)
def _mix_hex(color,amount):
    return _shade(tuple(int(color[i:i+2],16) for i in (1,3,5)),amount)


def _shade(channels,amount):
    target = 255 if amount >= 0 else 0
    return '#' + ''.join(f'{round(c + (target-c)*abs(amount)):02x}' for c in channels)


def _draw_depth(widget, color, button=False):
    """A shallow top bevel, shaded lower lip and an inset rim; all native pixels."""
    canvas = widget._canvas
    if color == 'transparent':
        canvas.delete('material-depth')
        widget._depth_key=None
        return
    width = widget._apply_widget_scaling(widget._current_width)
    height = widget._apply_widget_scaling(widget._current_height)
    if width < 35 or height < 20:
        canvas.delete('material-depth')
        widget._depth_key=None
        return
    radius = min(widget._apply_widget_scaling(widget._corner_radius), height / 2)
    dark = widget._get_appearance_mode() == 'dark'
    key=(width,height,radius,widget._apply_appearance_mode(color),dark,button)
    if getattr(widget,'_depth_key',None)==key and canvas.find_withtag('material-depth'):
        canvas.tag_raise('material-depth')
        return
    widget._depth_key=key
    canvas.delete('material-depth')
    inset = max(8, radius)
    # The bevel occupies the empty padding; text stays on a uniform opaque face.
    for i in range(1, 7 if button else 12):
        amount = (0.16 if button else 0.09) * (1 - i / (7 if button else 12))
        canvas.create_line(inset, i+1, width-inset, i+1,
                           fill=_mix_color(widget, color, amount if dark else amount * 0.5),
                           tags='material-depth')
    canvas.create_line(inset, 1, width-inset, 1,
                       fill=_mix_color(widget, color, 0.25 if dark else 0.65), tags='material-depth')
    for i in range(1, 5):
        canvas.create_line(inset, height-i-1, width-inset, height-i-1,
                           fill=_mix_color(widget, color, -0.10 * (1-i/5)), tags='material-depth')
    canvas.create_line(1, radius, 1, height-radius,
                       fill=_mix_color(widget, color, 0.035), tags='material-depth')
    canvas.create_line(width-2, radius, width-2, height-radius,
                       fill=_mix_color(widget, color, -0.12), tags='material-depth')


class MaterialFrame(ctk.CTkFrame):
    """Raised graphite surface that retains normal Tk geometry and accessibility."""
    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)
        _draw_depth(self, self._fg_color)


class MaterialButton(ctk.CTkButton):
    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)
        _draw_depth(self, self._fg_color, button=True)

    def _on_enter(self, event=None):
        super()._on_enter(event)
        if self._state != 'disabled':
            _draw_depth(self, self._hover_color, button=True)

    def _on_leave(self, event=None):
        super()._on_leave(event)
        _draw_depth(self, self._fg_color, button=True)


def load_design():
    _stabilize_rendering()
    # Native canvas polygons do not depend on rotated font glyphs for rounded
    # corners. This avoids transient glyph blocks during Windows resize/repaint.
    ctk.DrawEngine.preferred_drawing_method = 'polygon_shapes'
    if os.name == 'nt':
        import ctypes
        for font in (ASSETS / 'fonts').glob('*.ttf'):
            ctypes.windll.gdi32.AddFontResourceExW(str(font), 0x10, 0)
    ctk.set_default_color_theme(str(ASSETS / 'paddock-theme.json'))


def _stabilize_rendering():
    """Keep CTk drawing on the main event loop instead of recursively draining it.

    CTk 6 calls Canvas.update_idletasks inside widget _draw methods. Scrollbar
    geometry callbacks can re-enter _draw before startup or a layout pass ends.
    Tk already schedules canvas painting; only skip this internal canvas flush.
    Explicit updates on the app, dialogs and frames retain their normal behavior.
    """
    if ctk.__version__ == '6.0.0':
        ctk.CTkCanvas.update_idletasks = lambda canvas: None
        # The stock Windows titlebar routine withdraws and calls update() while
        # constructing dialogs. Apply the same native color without event-loop
        # re-entry or hiding/showing windows (which can also crash Tk).
        if os.name == 'nt':
            ctk.CTk._windows_set_titlebar_color = _paint_titlebar
            ctk.CTkToplevel._windows_set_titlebar_color = _paint_titlebar
    current = ctk.CTkScrollbar.set
    if getattr(current, '_deepfocus_stable', False):
        return

    def set_if_changed(scrollbar, start_value, end_value):
        start, end = float(start_value), float(end_value)
        if (start, end) == (scrollbar._start_value, scrollbar._end_value):
            return
        return current(scrollbar, start, end)

    set_if_changed._deepfocus_stable = True
    ctk.CTkScrollbar.set = set_if_changed


def _paint_titlebar(window, color_mode):
    import ctypes
    from ctypes import wintypes
    try:
        get_parent=ctypes.windll.user32.GetParent
        get_parent.argtypes=[wintypes.HWND]
        get_parent.restype=wintypes.HWND
        hwnd=get_parent(window.winfo_id())
        set_attribute=ctypes.windll.dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
        set_attribute.restype=ctypes.c_long
        dark=ctypes.c_int(color_mode.lower()=='dark')
        if set_attribute(hwnd,20,ctypes.byref(dark),ctypes.sizeof(dark)):
            set_attribute(hwnd,19,ctypes.byref(dark),ctypes.sizeof(dark))
    except (AttributeError,OSError):
        pass  # Native titlebar decoration must never stop the interface.


@lru_cache(maxsize=32)
def nav_icon(name, active=False):
    def draw(color):
        image = Image.new('RGBA', (72, 72))
        d = ImageDraw.Draw(image)
        line = lambda points: d.line(points, fill=color, width=5, joint='curve')
        if name == 'timer':
            d.ellipse((12, 14, 60, 62), outline=color, width=5)
            line([(36, 24), (36, 39), (46, 45)])
            line([(28, 5), (44, 5)])
        elif name == 'planner':
            d.rounded_rectangle((10, 14, 62, 62), radius=7, outline=color, width=4)
            line([(10, 29), (62, 29)])
            line([(24, 7), (24, 21)])
            line([(48, 7), (48, 21)])
            line([(23, 43), (32, 51), (49, 36)])
        elif name == 'blocker':
            line([(36, 7), (59, 16), (57, 41), (49, 54), (36, 64), (23, 54), (15, 41), (13, 16), (36, 7)])
            line([(24, 35), (32, 43), (48, 27)])
        elif name == 'sound':
            for x, top, bottom in [(13, 27, 45), (25, 15, 57), (37, 7, 65), (49, 21, 51), (61, 29, 43)]:
                line([(x, top), (x, bottom)])
        elif name == 'customizer':
            for y, x in [(17, 27), (36, 47), (55, 23)]:
                line([(10, y), (62, y)])
                d.ellipse((x-7, y-7, x+7, y+7), fill=color)
        elif name == 'shutdown':
            d.arc((12, 12, 60, 62), 305, 235, fill=color, width=5)
            line([(36, 5), (36, 34)])
        elif name == 'history':
            d.rounded_rectangle((12, 9, 60, 63), radius=5, outline=color, width=4)
            for y in (24, 36, 48):
                line([(23, y), (49, y)])
        elif name == 'stats':
            for x, y in [(13, 42), (31, 26), (49, 10)]:
                d.rounded_rectangle((x, y, x+10, 61), radius=2, fill=color)
        else:
            d.ellipse((19, 19, 53, 53), outline=color, width=5)
            d.ellipse((29, 29, 43, 43), outline=color, width=4)
            for angle in range(0, 360, 45):
                a = math.radians(angle)
                line([(36+18*math.cos(a), 36+18*math.sin(a)),
                      (36+28*math.cos(a), 36+28*math.sin(a))])
        return image
    return ctk.CTkImage(light_image=draw('#1E252F' if active else '#586373'),
                        dark_image=draw('#EFF2F7' if active else '#A6B0BF'), size=(20, 20))
