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

"""Undo/redo history for the per-key editor.

Each entry is one paint stroke: the colors the touched zones had before the
stroke and the colors the stroke gave them. Undo hands back the "before" map
and redo the "after" map; the editor writes whichever it gets to the sink.
GTK-free so it can be unit tested directly.
"""

from __future__ import annotations

UNSET = -1


class PaintHistory:
    def __init__(self, limit: int = 200) -> None:
        self._limit = limit
        self._undo: list[tuple[dict[int, int], dict[int, int]]] = []
        self._redo: list[tuple[dict[int, int], dict[int, int]]] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def record(self, current: dict[int, int], delta: dict[int, int]) -> bool:
        """Record a stroke about to be applied. `current` is the color map
        before the stroke, `delta` the zones it paints. Zones whose color
        wouldn't change are left out; a stroke that changes nothing isn't
        recorded. Returns True if an entry was added."""
        before: dict[int, int] = {}
        after: dict[int, int] = {}
        for zone, color in delta.items():
            old = int(current.get(int(zone), UNSET))
            if old != int(color):
                before[int(zone)] = old
                after[int(zone)] = int(color)
        if not after:
            return False
        self._undo.append((before, after))
        if len(self._undo) > self._limit:
            del self._undo[0]
        self._redo.clear()
        return True

    def undo(self) -> dict[int, int] | None:
        """Pop the latest stroke; return the colors that restore it."""
        if not self._undo:
            return None
        entry = self._undo.pop()
        self._redo.append(entry)
        return dict(entry[0])

    def redo(self) -> dict[int, int] | None:
        """Re-apply the most recently undone stroke; return its colors."""
        if not self._redo:
            return None
        entry = self._redo.pop()
        self._undo.append(entry)
        return dict(entry[1])
