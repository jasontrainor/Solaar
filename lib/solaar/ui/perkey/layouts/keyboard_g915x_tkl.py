## Copyright (C) 2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
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

"""G915 X LIGHTSPEED TKL per-key layout.

Regional TKL base plus the board's top bar. Positions follow the diagram in
Logitech's G915 X LIGHTSPEED TKL setup guide: G logo above Esc; Lightspeed,
Bluetooth, Game Mode and Brightness buttons above F1-F4; Previous, Play/Pause,
Next and Mute above F9-F12; the volume roller above the nav cluster.

Only the logo, Brightness and the four media keys are addressable — the board
reports their canonical zones (210, 153, 155-158). Lightspeed, Bluetooth,
Game Mode and the roller have no per-key zone and are not drawn.
"""

from __future__ import annotations

from ..layout import Cell
from ..layout import Layout
from ._keyboard_base import with_top_row

# Columns match the F-row in _keyboard_base.FN_ROW (Esc=0, F4=5, F9-F12=10-13).
TOP_BAR: tuple[Cell, ...] = (
    Cell(zone_id=210, row=0, col=0, group="media", label="Logo"),
    Cell(zone_id=153, row=0, col=5, group="media", label="Bright"),
    Cell(zone_id=158, row=0, col=10, group="media", label="Prev"),
    Cell(zone_id=155, row=0, col=11, group="media", label="Play"),
    Cell(zone_id=157, row=0, col=12, group="media", label="Next"),
    Cell(zone_id=156, row=0, col=13, group="media", label="Mute"),
)

DESCRIPTION = "G915 X TKL"


def with_top_bar(base: Layout) -> Layout:
    """Return a regional TKL `base` with the G915 X TKL top bar above it."""
    return with_top_row(base, TOP_BAR, DESCRIPTION)
