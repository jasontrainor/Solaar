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

from solaar import perkey_themes  # NOQA: E402
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
    "bucket": (
        _("Fill"),
        _(
            "Click a key to recolor it and every connected key of the same color "
            "(clicking an unpainted key fills all connected unpainted keys)"
        ),
    ),
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
                if icon_name and attach_themed_icon(btn, icon_name, label) is not None:
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

        toolbar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
        self._themes_btn = Gtk.Button.new_with_label(_("Themes") + " \u25be")
        self._themes_btn.set_tooltip_text(_("Apply, save, import or export per-key color themes"))
        self._themes_btn.connect(GtkSignal.CLICKED.value, self._on_themes_clicked)
        toolbar.pack_start(self._themes_btn, False, False, 0)

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

        # Always-visible description of the active tool, so it's clear what a
        # click or drag will do before it happens.
        self._tool_hint = Gtk.Label(xalign=0)
        self._tool_hint.set_line_wrap(True)
        self._tool_hint.set_max_width_chars(60)  # wrap within the canvas width, don't widen the window
        self._tool_hint.get_style_context().add_class("dim-label")
        self.pack_start(self._tool_hint, False, False, 0)
        if supported:
            self._show_tool_hint(supported[0])

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
            self._show_tool_hint(name)

    def _show_tool_hint(self, name: str) -> None:
        if name == "gradient":
            label, tip = _("Gradient"), _TOOL_TOOLTIPS["gradient"]
        else:
            label, tip = _TOOL_LABELS.get(name, (name, ""))
        self._tool_hint.set_text(f"{label}: {tip}" if tip else label)

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
        self._paint(delta)

    def _paint(self, delta: dict) -> None:
        """Apply a user change as one undoable step."""
        if not delta:
            return
        self._history.record(dict(self._sink.current), {int(z): int(c) for z, c in delta.items()})
        self._update_history_buttons()
        self._apply(delta)

    # ---- themes ----

    def apply_theme(self, theme: perkey_themes.Theme) -> None:
        """Replace the whole per-key map with `theme` (undoable). Keys the
        theme doesn't color become unset."""
        full = theme.full_map(self._sink.zones)
        current = self._sink.current
        self._paint({z: c for z, c in full.items() if current.get(z, perkey_themes.UNSET) != c})

    def save_current_as(self, name: str):
        theme = perkey_themes.Theme.from_colors(name, self._sink.current, self._sink.title)
        return perkey_themes.save(theme)

    def export_current(self, path) -> None:
        from pathlib import Path

        name = Path(path).stem or self._sink.title
        perkey_themes.write_file(perkey_themes.Theme.from_colors(name, self._sink.current, self._sink.title), path)

    def import_theme(self, path) -> perkey_themes.Theme:
        return perkey_themes.import_file(path)

    def delete_theme(self, name: str) -> None:
        perkey_themes.delete(name)

    def _on_themes_clicked(self, button: Gtk.Button) -> None:
        menu = Gtk.Menu()
        themes = perkey_themes.list_themes()
        if themes:
            for theme in themes:
                item = Gtk.MenuItem(label=theme.name)
                item.set_tooltip_text(_("Apply this theme (Ctrl+Z to undo)"))
                item.connect("activate", lambda _i, t=theme: self.apply_theme(t))
                menu.append(item)
        else:
            empty = Gtk.MenuItem(label=_("No saved themes"))
            empty.set_sensitive(False)
            menu.append(empty)
        menu.append(Gtk.SeparatorMenuItem())
        for label, handler in (
            (_("Save current as\u2026"), self._save_dialog),
            (_("Import\u2026"), self._import_dialog),
            (_("Export current\u2026"), self._export_dialog),
        ):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _i, h=handler: h())
            menu.append(item)
        delete = Gtk.MenuItem(label=_("Delete"))
        if themes:
            submenu = Gtk.Menu()
            for theme in themes:
                item = Gtk.MenuItem(label=theme.name)
                item.connect("activate", lambda _i, t=theme: self._delete_dialog(t.name))
                submenu.append(item)
            delete.set_submenu(submenu)
        else:
            delete.set_sensitive(False)
        menu.append(delete)
        menu.show_all()
        menu.attach_to_widget(button, None)
        menu.popup_at_widget(button, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, None)

    def _parent_window(self):
        top = self.get_toplevel()
        return top if isinstance(top, Gtk.Window) else None

    def _message(self, kind: Gtk.MessageType, text: str, secondary: str = "") -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self._parent_window(), modal=True, message_type=kind, buttons=Gtk.ButtonsType.OK, text=text
        )
        if secondary:
            dialog.format_secondary_text(secondary)
        dialog.run()
        dialog.destroy()

    def _confirm(self, text: str, secondary: str = "") -> bool:
        dialog = Gtk.MessageDialog(
            transient_for=self._parent_window(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=text,
        )
        if secondary:
            dialog.format_secondary_text(secondary)
        ok = dialog.run() == Gtk.ResponseType.YES
        dialog.destroy()
        return ok

    def _save_dialog(self) -> None:
        dialog = Gtk.Dialog(title=_("Save theme"), transient_for=self._parent_window(), modal=True)
        dialog.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL, _("Save"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        entry = Gtk.Entry()
        entry.set_placeholder_text(_("Theme name"))
        entry.set_activates_default(True)
        box = dialog.get_content_area()
        box.set_border_width(8)
        box.set_spacing(6)
        box.pack_start(Gtk.Label(label=_("Save the current colors as a theme named:"), xalign=0), False, False, 0)
        box.pack_start(entry, False, False, 0)
        dialog.show_all()
        try:
            while dialog.run() == Gtk.ResponseType.OK:
                name = entry.get_text().strip()
                if not name:
                    continue
                try:
                    if perkey_themes.exists(name) and not self._confirm(_("Replace the theme '%s'?") % name):
                        continue
                    self.save_current_as(name)
                except (perkey_themes.ThemeError, OSError) as e:
                    self._message(Gtk.MessageType.ERROR, _("Could not save the theme"), str(e))
                    continue
                break
        finally:
            dialog.destroy()

    def _json_filter(self) -> Gtk.FileFilter:
        f = Gtk.FileFilter()
        f.set_name(_("Solaar themes (*.json)"))
        f.add_pattern("*.json")
        return f

    def _import_dialog(self) -> None:
        dialog = Gtk.FileChooserDialog(
            title=_("Import theme"), transient_for=self._parent_window(), action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL, _("Import"), Gtk.ResponseType.OK)
        dialog.add_filter(self._json_filter())
        path = dialog.get_filename() if dialog.run() == Gtk.ResponseType.OK else None
        dialog.destroy()
        if not path:
            return
        try:
            theme = perkey_themes.read_file(path)
            if perkey_themes.exists(theme.name) and not self._confirm(_("Replace the theme '%s'?") % theme.name):
                return
            self.import_theme(path)
        except (perkey_themes.ThemeError, OSError) as e:
            self._message(Gtk.MessageType.ERROR, _("Could not import the theme"), str(e))
            return
        self._message(Gtk.MessageType.INFO, _("Imported theme '%s'") % theme.name, _("Apply it from the Themes menu."))

    def _export_dialog(self) -> None:
        dialog = Gtk.FileChooserDialog(
            title=_("Export current colors"), transient_for=self._parent_window(), action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL, _("Export"), Gtk.ResponseType.OK)
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_name(f"{self._sink.title}.json")
        dialog.add_filter(self._json_filter())
        path = dialog.get_filename() if dialog.run() == Gtk.ResponseType.OK else None
        dialog.destroy()
        if not path:
            return
        if not path.endswith(".json"):
            path += ".json"
        try:
            self.export_current(path)
        except (perkey_themes.ThemeError, OSError) as e:
            self._message(Gtk.MessageType.ERROR, _("Could not export the theme"), str(e))

    def _delete_dialog(self, name: str) -> None:
        if not self._confirm(_("Delete the theme '%s'?") % name, _("This cannot be undone.")):
            return
        try:
            self.delete_theme(name)
        except (perkey_themes.ThemeError, OSError) as e:
            self._message(Gtk.MessageType.ERROR, _("Could not delete the theme"), str(e))

    def _apply(self, delta: dict) -> None:
        self._canvas.update_colors(delta)
        if len(delta) == 1:
            zone, color = next(iter(delta.items()))
            self._sink.write_one(int(zone), int(color))
        else:
            self._sink.write_bulk({int(z): int(c) for z, c in delta.items()})
