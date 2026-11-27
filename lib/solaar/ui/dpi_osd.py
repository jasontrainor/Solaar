## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License along
## with this program; if not, write to the Free Software Foundation, Inc.,
## 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""Shows DPI changes on screen: Solaar's own overlay, the desktop's OSD, or a notification.

The overlay is an X11 popup window.  Under Wayland it is opened on XWayland, because a Wayland
window cannot choose where it goes or stay above other windows; an X11 popup can do both,
and doesn't take the keyboard focus or the mouse clicks.
"""

import logging
import math
import os

import cairo
import gi

from logitech_receiver import dpi_osd
from logitech_receiver.dpi_osd import DpiEvent

from solaar.i18n import _

from . import desktop_notifications

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk  # NOQA: E402
from gi.repository import Gio  # NOQA: E402
from gi.repository import GLib  # NOQA: E402
from gi.repository import Gtk  # NOQA: E402
from gi.repository import Pango  # NOQA: E402
from gi.repository import PangoCairo  # NOQA: E402

logger = logging.getLogger(__name__)

_SHIFT_SAFETY_MS = 30000  # hide a DPI Shift overlay if its release is never reported
_FADE_STEP_MS = 20
_FADE_STEPS = 8
_SCALES = {dpi_osd.SIZE_SMALL: 0.75, dpi_osd.SIZE_MEDIUM: 1.0, dpi_osd.SIZE_LARGE: 1.5}
_ICON = "input-mouse"


def init():
    dpi_osd.handler = _from_library


def uninit():
    dpi_osd.handler = None
    global _overlay
    if _overlay is not None:
        _overlay.destroy()
        _overlay = None


def _from_library(device, event):
    # Button events arrive on the receiver's listener thread; draw on the GTK one.
    GLib.idle_add(show, device, event)


def describe(event):
    """The change as one line of text, for the desktop OSD and notifications."""
    if event.shift:
        return _("DPI Shift: %d DPI") % event.dpi
    if event.dpi in event.levels:
        return _("%(dpi)d DPI (level %(level)d of %(count)d)") % {
            "dpi": event.dpi,
            "level": event.levels.index(event.dpi) + 1,
            "count": len(event.levels),
        }
    return _("%d DPI") % event.dpi


def show(device, event):
    """Show a DPI change in the style chosen for the device. Returns False (for GLib.idle_add)."""
    style = dpi_osd.saved(device, dpi_osd.STYLE)
    if style == dpi_osd.STYLE_OVERLAY:
        overlay = _get_overlay()
        if overlay is not None and overlay.show(
            event,
            position=dpi_osd.saved(device, dpi_osd.POSITION),
            duration=dpi_osd.saved(device, dpi_osd.DURATION),
            scale=_SCALES.get(dpi_osd.saved(device, dpi_osd.SIZE), 1.0),
        ):
            return False
    if event.shift_released and style != dpi_osd.STYLE_OVERLAY:
        return False  # the desktop OSD and notifications don't need a second popup for the release
    if style != dpi_osd.STYLE_NOTIFICATION and _desktop_osd(describe(event)):
        return False
    desktop_notifications.show(device, describe(event))
    return False


def preview(device):
    """Show the device's current DPI the way it will be shown, e.g. after changing how."""
    if not dpi_osd.wanted(device):
        hide()
        return False
    dpi = next((s for s in getattr(device, "settings", []) if s.name in ("dpi", "dpi_extended")), None)
    value = getattr(dpi, "_value", None) if dpi else None
    if isinstance(value, dict):
        value = next(iter(value.values()), None)
    if value is None:
        return False
    from logitech_receiver import settings_templates

    levels, _default, _shift = settings_templates.host_button_dpi_levels(device)
    show(device, DpiEvent(int(value), tuple(levels)))
    return False


def hide():
    if _overlay is not None:
        _overlay.hide()


def _desktop_osd(text):
    """Show text in KDE Plasma's on-screen display. False if Plasma isn't there."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "NameHasOwner",
            GLib.Variant("(s)", ("org.kde.plasmashell",)),
            GLib.VariantType("(b)"),
            Gio.DBusCallFlags.NONE,
            500,
            None,
        )
        if not reply.unpack()[0]:
            return False
        bus.call(
            "org.kde.plasmashell",
            "/org/kde/osdService",
            "org.kde.osdService",
            "showText",
            GLib.Variant("(ss)", (_ICON, text)),
            None,
            Gio.DBusCallFlags.NONE,
            1000,
            None,
            None,
        )
        return True
    except GLib.Error as e:
        logger.debug("desktop OSD not available: %s", e)
        return False


_overlay = None
_overlay_failed = False


def _get_overlay():
    global _overlay, _overlay_failed
    if _overlay is None and not _overlay_failed:
        display = _overlay_display()
        if display is None:
            logger.warning("no X11 display for the DPI overlay, using the desktop OSD instead")
            _overlay_failed = True
        else:
            _overlay = _Overlay(display)
    return _overlay


def _overlay_display():
    """A display whose windows can place themselves: the X11 one, via XWayland under Wayland."""
    default = Gdk.Display.get_default()
    if default is None:
        return None
    if "Wayland" not in default.__gtype__.name:
        return default
    name = os.environ.get("DISPLAY")
    if not name:
        return None
    try:
        return Gdk.Display.open(name)
    except Exception as e:
        logger.warning("cannot open X11 display %s: %s", name, e)
        return None


def overlay_origin(area, width, height, position, margin):
    """Top-left corner of a width x height overlay at `position` within `area` (a Gdk.Rectangle)."""
    column = (position - 1) % 3
    row = (position - 1) // 3
    x = (area.x + margin, area.x + (area.width - width) // 2, area.x + area.width - width - margin)[column]
    y = (area.y + margin, area.y + (area.height - height) // 2, area.y + area.height - height - margin)[row]
    return int(x), int(y)


class _Overlay:
    """A small rounded card with the DPI, drawn above everything and ignoring the mouse."""

    def __init__(self, display):
        self._display = display
        self._hide_id = None
        self._fade_id = None
        self._event = None
        self._scale = 1.0
        window = Gtk.Window(type=Gtk.WindowType.POPUP)
        screen = display.get_default_screen()
        window.set_screen(screen)
        visual = screen.get_rgba_visual()
        self._alpha = visual is not None and screen.is_composited()
        if self._alpha:
            window.set_visual(visual)
        window.set_app_paintable(True)
        window.set_accept_focus(False)
        window.connect("draw", self._draw)
        window.connect("realize", self._realized)
        self._window = window

    @staticmethod
    def _realized(window):
        window.get_window().input_shape_combine_region(cairo.Region(), 0, 0)  # clicks go through

    def destroy(self):
        self._cancel_timers()
        self._window.destroy()

    def _unit(self):
        resolution = self._window.get_screen().get_resolution()
        return self._scale * (resolution / 96.0 if resolution and resolution > 0 else 1.0)

    def _layout(self, text, points, bold=True):
        layout = self._window.create_pango_layout(text)
        font = Pango.FontDescription.from_string("Sans")
        font.set_weight(Pango.Weight.BOLD if bold else Pango.Weight.NORMAL)
        font.set_size(int(points * self._scale * Pango.SCALE))
        layout.set_font_description(font)
        return layout

    def _parts(self):
        event = self._event
        caption = self._layout(_("DPI SHIFT") if event.shift else _("DPI"), 9)
        number = self._layout(str(event.dpi), 28)
        dots = len(event.levels) if (event.levels and event.dpi in event.levels and not event.shift) else 0
        return caption, number, dots

    def _geometry(self):
        u = self._unit()
        caption, number, dots = self._parts()
        pad, gap, dot, dot_gap = 16 * u, 2 * u, 7 * u, 6 * u
        cw, ch = caption.get_pixel_size()
        nw, nh = number.get_pixel_size()
        dots_w = dots * dot + max(dots - 1, 0) * dot_gap
        width = max(cw, nw, dots_w, 70 * u) + 2 * pad
        height = pad + ch + gap + nh + ((gap * 3 + dot) if dots else 0) + pad
        return int(math.ceil(width)), int(math.ceil(height))

    def show(self, event, position, duration, scale):
        self._event = event
        self._scale = scale
        self._cancel_timers()
        try:
            width, height = self._geometry()
            monitor = self._display.get_primary_monitor() or self._display.get_monitor(0)
            area = monitor.get_workarea() if monitor else None
            self._window.resize(width, height)
            if area is not None:
                self._window.move(*overlay_origin(area, width, height, position, int(40 * self._unit())))
            self._window.set_opacity(1.0)
            self._window.show()
            self._window.queue_draw()
        except Exception:
            logger.exception("showing the DPI overlay")
            return False
        self._hide_id = GLib.timeout_add(_SHIFT_SAFETY_MS if event.shift else duration, self._start_fade)
        return True

    def hide(self):
        self._cancel_timers()
        self._window.hide()

    def _cancel_timers(self):
        for source in (self._hide_id, self._fade_id):
            if source is not None:
                GLib.source_remove(source)
        self._hide_id = self._fade_id = None

    def _start_fade(self):
        self._hide_id = None
        steps = [_FADE_STEPS]

        def step():
            steps[0] -= 1
            if steps[0] <= 0:
                self._fade_id = None
                self._window.hide()
                return False
            self._window.set_opacity(steps[0] / _FADE_STEPS)
            return True

        self._fade_id = GLib.timeout_add(_FADE_STEP_MS, step)
        return False

    def _draw(self, window, cr):
        if self._event is None:
            return False
        u = self._unit()
        width, height = window.get_allocated_width(), window.get_allocated_height()
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        radius = 14 * u if self._alpha else 0
        cr.new_sub_path()
        cr.arc(width - radius, radius, radius, -math.pi / 2, 0)
        cr.arc(width - radius, height - radius, radius, 0, math.pi / 2)
        cr.arc(radius, height - radius, radius, math.pi / 2, math.pi)
        cr.arc(radius, radius, radius, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.set_source_rgba(0.09, 0.09, 0.11, 0.88 if self._alpha else 1.0)
        cr.fill()

        caption, number, dots = self._parts()
        pad, gap, dot, dot_gap = 16 * u, 2 * u, 7 * u, 6 * u
        cw, ch = caption.get_pixel_size()
        nw, nh = number.get_pixel_size()
        y = pad
        if self._event.shift:
            cr.set_source_rgb(1.0, 0.62, 0.2)
        else:
            cr.set_source_rgba(1, 1, 1, 0.6)
        cr.move_to((width - cw) / 2, y)
        PangoCairo.show_layout(cr, caption)
        y += ch + gap
        cr.set_source_rgb(1, 1, 1)
        cr.move_to((width - nw) / 2, y)
        PangoCairo.show_layout(cr, number)
        y += nh + gap * 3
        if dots:
            current = self._event.levels.index(self._event.dpi)
            x = (width - (dots * dot + (dots - 1) * dot_gap)) / 2
            for i in range(dots):
                cr.arc(x + dot / 2, y + dot / 2, dot / 2, 0, 2 * math.pi)
                cr.set_source_rgba(1, 1, 1, 0.95 if i == current else 0.25)
                cr.fill()
                x += dot + dot_gap
        return True
