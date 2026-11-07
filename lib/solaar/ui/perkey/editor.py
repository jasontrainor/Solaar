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

"""Editor widget: combines toolbar + palette + canvas into one VBox.

The editor consumes only the PerKeyColorSink protocol — no device imports,
no Setting imports — preserving the FE/BE seam.
"""

from __future__ import annotations

import logging

from enum import Enum

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk  # NOQA: E402
from gi.repository import Gtk  # NOQA: E402

from solaar.i18n import _  # NOQA: E402

from . import binding  # NOQA: E402
from ._icons import attach_themed_icon  # NOQA: E402
from .canvas import KeyboardCanvas  # NOQA: E402
from .history import PaintHistory  # NOQA: E402
from .layout import Layout  # NOQA: E402
from .palette import GradientSwatch  # NOQA: E402
from .palette import Palette  # NOQA: E402
from .protocol import PerKeyColorSink  # NOQA: E402

logger = logging.getLogger(__name__)


class GtkSignal(Enum):
    CLICKED = "clicked"
    COLOR_CHANGED = "color-changed"
    PAINT = "paint"
    TOGGLED = "toggled"


_TOOL_LABELS = {
    "single": (_("Brush"), _("Click or drag to paint individual keys")),
    "rect": (_("Rect"), _("Drag to select a rectangle of keys, painted on release")),
    "bucket": (_("Fill"), _("Flood-fill connected keys of the same color with the active color")),
}
_TOOL_TOOLTIPS = {
    "gradient": _("Drag to fade from previous color to active color"),
}
_TOOL_ICON_NAMES = {
    "single": "solaar-tool-brush-symbolic",
    "rect": "solaar-tool-rect-symbolic",
    "bucket": "solaar-tool-bucket-symbolic",
}


class PerKeyEditor(Gtk.Box):
    def __init__(self, sink: PerKeyColorSink, layout: Layout | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._sink = sink
        self._layout = layout
        self._unsubscribe = None
        self._history = PaintHistory()

        # toolbar row
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._tool_buttons: dict[str, Gtk.RadioButton] = {}
        self._gradient_swatch: GradientSwatch | None = None
        first: Gtk.RadioButton | None = None
        supported = layout.supported_tools if layout else ("single", "rect", "bucket", "gradient")
        for name in supported:
            if name == "gradient":
                btn = Gtk.RadioButton.new_from_widget(first)
                btn.set_mode(False)
                self._gradient_swatch = GradientSwatch()
                btn.add(self._gradient_swatch)
                btn.set_tooltip_text(_TOOL_TOOLTIPS["gradient"])
            else:
                label, tip = _TOOL_LABELS.get(name, (name, ""))
                icon_name = _TOOL_ICON_NAMES.get(name)
                btn = Gtk.RadioButton.new_from_widget(first)
                btn.set_mode(False)  # render as toggle button rather than radio
                if icon_name and attach_themed_icon(btn, icon_name) is not None:
                    btn.set_tooltip_text(tip or label)
                    btn.get_accessible().set_name(label)
                else:
                    btn.set_label(label)
                    btn.set_tooltip_text(tip)
            btn.connect(GtkSignal.TOGGLED.value, self._on_tool_toggled, name)
            if first is None:
                first = btn
            toolbar.pack_start(btn, False, False, 0)
            self._tool_buttons[name] = btn

        toolbar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
        self._undo_btn = self._history_button("edit-undo-symbolic", _("Undo"), _("Undo the last paint (Ctrl+Z)"), self.undo)
        self._redo_btn = self._history_button(
            "edit-redo-symbolic", _("Redo"), _("Redo the last undone paint (Ctrl+Shift+Z or Ctrl+Y)"), self.redo
        )
        toolbar.pack_start(self._undo_btn, False, False, 0)
        toolbar.pack_start(self._redo_btn, False, False, 0)
        self._update_history_buttons()

        initial_active, initial_previous = 0xFF0000, 0xFF0000
        try:
            persisted = sink.palette_state()
        except Exception as e:
            logger.debug("palette_state read failed: %s", e)
            persisted = None
        if persisted is not None:
            initial_active, initial_previous = persisted
        self._palette = Palette(active=initial_active, previous=initial_previous)
        self._palette.connect(GtkSignal.COLOR_CHANGED.value, self._on_color_changed)
        toolbar.pack_end(self._palette, False, False, 0)
        if self._gradient_swatch is not None:
            self._gradient_swatch.update(self._palette.get_color(), self._palette.get_last_color())

        self.pack_start(toolbar, False, False, 0)

        # canvas inside a scrolled window so wide layouts can scroll if the
        # window is shrunk below content size. propagate_natural_size lets the
        # window auto-fit small layouts (e.g. an 8-LED mouse) without forcing
        # an oversized minimum.
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_width(True)
        scroll.set_propagate_natural_height(True)
        # Inset frame around the keyboard so it reads as a distinct panel
        # rather than floating flat against the dialog background.
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        self._canvas = KeyboardCanvas()
        self._canvas.connect(GtkSignal.PAINT.value, self._on_canvas_paint)
        scroll.add(self._canvas)
        self.pack_start(scroll, True, True, 0)

        self._canvas.set_active_color(self._palette.get_color())
        if self._gradient_swatch is not None:
            self._canvas.set_gradient_colors_source(self._gradient_swatch.get_colors)
        try:
            base = sink.zone_base_color()
        except Exception as e:
            logger.debug("zone_base_color read failed: %s", e)
            base = None
        self._canvas.set_zone_base_color(base)
        self._refresh_layout()
        self._sync_from_sink()
        self._unsubscribe = sink.subscribe(self._on_sink_update)

    def shutdown(self) -> None:
        if self._unsubscribe:
            try:
                self._unsubscribe()
            except Exception as e:
                logger.debug("perkey sink unsubscribe failed: %s", e)
            self._unsubscribe = None
        try:
            self._palette.shutdown()
        except Exception as e:
            logger.debug("palette shutdown failed: %s", e)

    def _refresh_layout(self) -> None:
        if self._layout is None:
            # No registered layout: lay out all reported zones as a flat strip.
            from .layout import Cell

            zones = list(self._sink.zones)
            cells = tuple(Cell(zone_id=z, row=0, col=i, group="strip", label=self._sink.label(z)) for i, z in enumerate(zones))
            self._layout = Layout(cells=cells, rows=1, cols=max(1, len(zones)), description=f"flat strip ({len(zones)} zones)")
        bound = binding.bind(
            self._layout,
            list(self._sink.zones),
            self._sink.label,
        )
        self._canvas.set_layout(bound)

    def _sync_from_sink(self) -> None:
        self._canvas.set_colors(dict(self._sink.current))

    def _on_sink_update(self, current: dict[int, int]) -> None:
        self._canvas.set_colors(dict(current))

    def _on_color_changed(self, _palette, color: int) -> None:
        self._canvas.set_active_color(color)
        # Gradient swatch tracks only real picker colors; toggling unset
        # leaves it alone so the gradient setup isn't disturbed.
        picker = self._palette.get_picker_color()
        if self._gradient_swatch is not None:
            self._gradient_swatch.update(picker, self._palette.get_last_color())
        try:
            self._sink.set_palette_state(picker, self._palette.get_last_color())
        except Exception as e:
            logger.debug("set_palette_state failed: %s", e)

    def _on_tool_toggled(self, btn: Gtk.RadioButton, name: str) -> None:
        if btn.get_active():
            self._canvas.set_tool(name)

    def _history_button(self, icon_name: str, label: str, tip: str, action) -> Gtk.Button:
        btn = Gtk.Button.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
        if not Gtk.IconTheme.get_default().has_icon(icon_name):
            btn = Gtk.Button.new_with_label(label)
        btn.set_tooltip_text(tip)
        btn.get_accessible().set_name(label)
        btn.connect(GtkSignal.CLICKED.value, lambda _b: action())
        return btn

    def _update_history_buttons(self) -> None:
        self._undo_btn.set_sensitive(self._history.can_undo)
        self._redo_btn.set_sensitive(self._history.can_redo)

    def undo(self) -> None:
        changes = self._history.undo()
        if changes:
            self._apply(changes)
        self._update_history_buttons()

    def redo(self) -> None:
        changes = self._history.redo()
        if changes:
            self._apply(changes)
        self._update_history_buttons()

    def handle_key(self, event: Gdk.EventKey) -> bool:
        """Undo/redo shortcuts; the hosting window forwards key presses here."""
        mods = event.state & Gtk.accelerator_get_default_mod_mask()
        key = Gdk.keyval_to_lower(event.keyval)
        ctrl = Gdk.ModifierType.CONTROL_MASK
        shift = Gdk.ModifierType.SHIFT_MASK
        if mods == ctrl and key == Gdk.KEY_z:
            self.undo()
            return True
        if (mods == ctrl | shift and key == Gdk.KEY_z) or (mods == ctrl and key == Gdk.KEY_y):
            self.redo()
            return True
        return False

    def _on_canvas_paint(self, _canvas, delta: dict) -> None:
        if not delta:
            return
        self._history.record(dict(self._sink.current), {int(z): int(c) for z, c in delta.items()})
        self._update_history_buttons()
        self._apply(delta)

    def _apply(self, delta: dict) -> None:
        self._canvas.update_colors(delta)
        if len(delta) == 1:
            zone, color = next(iter(delta.items()))
            self._sink.write_one(int(zone), int(color))
        else:
            self._sink.write_bulk({int(z): int(c) for z, c in delta.items()})
