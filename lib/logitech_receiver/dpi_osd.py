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
"""Reports DPI changes made with a mouse's buttons, so they can be shown on screen.

The library only reports them; the UI sets `handler` to draw them.
The settings that control this are kept by Solaar and stored in the config file.
"""

from __future__ import annotations

import dataclasses
import logging

logger = logging.getLogger(__name__)

# Setting names, and what they default to before the user changes them.
SETTING = "dpi-osd"
STYLE = "dpi-osd-style"
POSITION = "dpi-osd-position"
DURATION = "dpi-osd-duration"
SIZE = "dpi-osd-size"

# What to show (the dpi-osd setting).
OFF = 0
CHANGES = 1
CHANGES_AND_SHIFT = 2

# How to show it (the dpi-osd-style setting).
STYLE_OVERLAY = 0
STYLE_DESKTOP = 1
STYLE_NOTIFICATION = 2

# Where the overlay goes (the dpi-osd-position setting), laid out like a numeric keypad turned upside down:
# 1 2 3 along the top, 4 5 6 across the middle, 7 8 9 along the bottom.
TOP_LEFT, TOP, TOP_RIGHT, LEFT, CENTER, RIGHT, BOTTOM_LEFT, BOTTOM, BOTTOM_RIGHT = range(1, 10)

SIZE_SMALL = 1
SIZE_MEDIUM = 2
SIZE_LARGE = 3

DEFAULTS = {
    SETTING: CHANGES_AND_SHIFT,
    STYLE: STYLE_OVERLAY,
    POSITION: BOTTOM,
    DURATION: 1500,
    SIZE: SIZE_MEDIUM,
}


@dataclasses.dataclass(frozen=True)
class DpiEvent:
    dpi: int
    levels: tuple = ()  # the DPI levels the buttons step through, if known
    shift: bool = False  # DPI Shift is being held; the overlay stays until it is released
    shift_released: bool = False  # DPI Shift was let go and `dpi` is the DPI restored


handler = None  # set by the UI: handler(device, DpiEvent), called from any thread


def saved(device, name):
    """The saved value of one of the on-screen DPI settings, or its default."""
    default = DEFAULTS[name]
    persister = getattr(device, "persister", None)
    value = persister.get(name) if persister else None
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def wanted(device, shift=False):
    """Whether the user wants this kind of change shown for this device."""
    mode = saved(device, SETTING)
    return mode == CHANGES_AND_SHIFT or (mode == CHANGES and not shift)


def dpi_changed(device, dpi, levels=(), shift=False, shift_released=False):
    """Report a DPI change made with the device's buttons."""
    if handler is None or not wanted(device, shift or shift_released):
        return
    try:
        event = DpiEvent(int(dpi), tuple(int(lv) for lv in levels or ()), shift, shift_released)
        handler(device, event)
    except Exception:
        logger.exception("%s: showing DPI %s", device, dpi)
