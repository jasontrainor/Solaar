import pytest

from solaar.ui.perkey.history import UNSET
from solaar.ui.perkey.history import PaintHistory


def test_undo_restores_previous_colors_including_unset():
    h = PaintHistory()
    current = {1: 0xFF0000, 2: UNSET, 3: UNSET}

    assert h.record(current, {1: 0x0000FF, 2: 0x0000FF})

    assert h.undo() == {1: 0xFF0000, 2: UNSET}
    assert not h.can_undo
    assert h.can_redo


def test_redo_reapplies_stroke():
    h = PaintHistory()
    h.record({1: UNSET}, {1: 0x00FF00})
    h.undo()

    assert h.redo() == {1: 0x00FF00}
    assert h.can_undo
    assert not h.can_redo


def test_unchanged_zones_and_noop_strokes_are_not_recorded():
    h = PaintHistory()

    assert not h.record({1: 0x112233}, {1: 0x112233})
    assert not h.can_undo
    assert h.record({1: 0x112233, 2: UNSET}, {1: 0x112233, 2: 0x445566})
    assert h.undo() == {2: UNSET}


def test_new_stroke_clears_redo():
    h = PaintHistory()
    h.record({1: UNSET}, {1: 0x010101})
    h.undo()
    h.record({1: UNSET}, {1: 0x020202})

    assert not h.can_redo


def test_strokes_undo_in_reverse_order():
    h = PaintHistory()
    h.record({1: UNSET}, {1: 0x0000AA})
    h.record({1: 0x0000AA}, {1: 0x0000BB})

    assert h.undo() == {1: 0x0000AA}
    assert h.undo() == {1: UNSET}
    assert h.undo() is None


def test_history_limit_drops_oldest():
    h = PaintHistory(limit=2)
    for i in range(3):
        h.record({1: i}, {1: i + 1})

    assert h.undo() == {1: 2}
    assert h.undo() == {1: 1}
    assert h.undo() is None


class _FakeSink:
    title = "Fake"
    zones = [1, 2, 3]

    def __init__(self):
        self.colors = {1: UNSET, 2: UNSET, 3: UNSET}
        self.writes = []

    @property
    def current(self):
        return dict(self.colors)

    def label(self, zone):
        return f"K{zone}"

    def write_one(self, zone, color):
        self.colors[zone] = color
        self.writes.append({zone: color})

    def write_bulk(self, deltas):
        self.colors.update(deltas)
        self.writes.append(dict(deltas))

    def subscribe(self, listener):
        return lambda: None

    def palette_state(self):
        return None

    def set_palette_state(self, active, previous):
        pass

    def zone_base_color(self):
        return None


def test_editor_undo_redo_writes_through_sink():
    Gtk = pytest.importorskip("gi.repository.Gtk")
    if not Gtk.init_check()[0]:
        pytest.skip("no display for GTK")
    from solaar.ui.perkey.editor import PerKeyEditor

    sink = _FakeSink()
    sink.colors[3] = 0xFF0000
    editor = PerKeyEditor(sink)
    assert not editor._undo_btn.get_sensitive()

    editor._canvas.emit("paint", {1: 0x613583, 2: 0x613583, 3: 0x613583})
    assert sink.colors == {1: 0x613583, 2: 0x613583, 3: 0x613583}
    assert editor._undo_btn.get_sensitive()

    editor.undo()
    assert sink.colors == {1: UNSET, 2: UNSET, 3: 0xFF0000}
    assert not editor._undo_btn.get_sensitive()
    assert editor._redo_btn.get_sensitive()

    editor.redo()
    assert sink.colors == {1: 0x613583, 2: 0x613583, 3: 0x613583}
    editor.shutdown()


def _editor_or_skip():
    Gtk = pytest.importorskip("gi.repository.Gtk")
    if not Gtk.init_check()[0]:
        pytest.skip("no display for GTK")
    from solaar.ui.perkey.editor import PerKeyEditor

    return Gtk, PerKeyEditor(_FakeSink())


def _button_text(Gtk, button):
    child = button.get_child()
    if isinstance(child, Gtk.Label):
        return child.get_text()
    return " ".join(w.get_text() for w in child.get_children() if isinstance(w, Gtk.Label))


def test_tool_buttons_show_their_names():
    Gtk, editor = _editor_or_skip()

    assert _button_text(Gtk, editor._tool_buttons["single"]) == "Brush"
    assert _button_text(Gtk, editor._tool_buttons["bucket"]) == "Fill"
    editor.shutdown()


def test_tool_hint_follows_active_tool():
    _Gtk, editor = _editor_or_skip()

    assert editor._tool_hint.get_text().startswith("Brush:")
    editor._tool_buttons["bucket"].set_active(True)
    assert editor._tool_hint.get_text().startswith("Fill:")
    assert "unpainted" in editor._tool_hint.get_text()
    editor.shutdown()


def test_apply_theme_replaces_map_and_is_one_undo_step(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from solaar import perkey_themes

    _Gtk, editor = _editor_or_skip()
    sink = editor._sink
    sink.colors.update({1: 0xFF0000, 3: 0x00FF00})

    editor.apply_theme(perkey_themes.Theme(name="t", colors={2: 0x0000FF, 999: 0x123456}))
    assert sink.colors == {1: UNSET, 2: 0x0000FF, 3: UNSET}

    editor.undo()
    assert sink.colors == {1: 0xFF0000, 2: UNSET, 3: 0x00FF00}
    editor.shutdown()


def test_save_export_import_from_editor(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    from solaar import perkey_themes

    _Gtk, editor = _editor_or_skip()
    editor._sink.colors.update({1: 0xABCDEF})

    editor.save_current_as("Mine")
    assert perkey_themes.load("Mine").colors == {1: 0xABCDEF}

    exported = tmp_path / "Shared.json"
    editor.export_current(exported)
    perkey_themes.delete("Mine")
    theme = editor.import_theme(exported)
    assert theme.name == "Shared"
    assert [t.name for t in perkey_themes.list_themes()] == ["Shared"]

    editor.delete_theme("Shared")
    assert perkey_themes.list_themes() == []
    editor.shutdown()
