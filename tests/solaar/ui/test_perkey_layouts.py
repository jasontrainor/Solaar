from solaar.ui.perkey.binding import bind
from solaar.ui.perkey.layouts import layout_for

# PRO X RAPID hardware-probed media zones (board-specific, not canonical 153-158).
_RAPID_MEDIA = {150, 152, 153, 154, 155}
# Phantom zones this board shares with the G515 (not physical keys).
_SHARED_PHANTOMS = {47, 97}


def _rapid_hint(name="PRO X RAPID", country=1):
    return {
        "kind": "keyboard",
        "wpid": "C35B",
        "codename": name,
        "name": name,
        "keyboard_layout": country,  # 1 = ANSI
        "zones": [38, 55, 66, *sorted(_RAPID_MEDIA), *sorted(_SHARED_PHANTOMS)],
        "zone_count": 9,
    }


def test_pro_x_rapid_gets_media_top_row():
    layout = layout_for(0x8081, _rapid_hint())

    assert layout.description == "PRO X RAPID"
    media = {c.zone_id: (c.row, c.col, c.label) for c in layout.cells if c.group == "media"}
    assert media == {
        150: (0, 5, "Bright"),
        155: (0, 10, "Prev"),
        152: (0, 11, "Play"),
        154: (0, 12, "Next"),
        153: (0, 13, "Mute"),
    }
    # The generated base is pushed down one row to make room for the media row.
    esc = next(c for c in layout.cells if c.zone_id == 38)
    assert esc.row == 1


def test_pro_x_rapid_media_keys_are_paintable_and_phantoms_dropped():
    layout = layout_for(0x8081, _rapid_hint())
    bound = bind(layout, _rapid_hint()["zones"], lambda z: f"KEY {z}")

    media_bound = {bc.cell.zone_id: bc.bound for bc in bound.matrix if bc.cell.group == "media"}
    assert media_bound == {z: True for z in _RAPID_MEDIA}
    # Shared phantoms must not surface as paintable strip swatches.
    strip_zones = {bc.cell.zone_id for bc in bound.strip}
    assert _SHARED_PHANTOMS.isdisjoint(strip_zones)


def test_pro_x_rapid_still_regional():
    # ISO country code still routes to the ISO main block, with the media row on top.
    iso = layout_for(0x8081, _rapid_hint(country=2))  # 2 = ISO QWERTY
    assert iso.description == "PRO X RAPID"
    assert any(c.group == "media" for c in iso.cells)


def test_non_rapid_tkl_unaffected():
    # A G515 TKL keeps the generic layout: no media top row.
    layout = layout_for(0x8081, _rapid_hint(name="G515 LS TKL"))

    assert layout.description != "PRO X RAPID"
    assert not any(c.group == "media" for c in layout.cells)


def _full_zone_hint(name):
    # G915 X LS TKL reports every zone 1-111 (numpad included) plus media keys.
    return {
        "kind": "keyboard",
        "wpid": "40B6",
        "codename": name,
        "name": name,
        "keyboard_layout": 1,
        "zones": [*range(1, 112), 153, 155, 156, 157, 158, 210],
        "zone_count": 117,
    }


def test_tkl_name_overrides_reported_numpad_zones():
    layout = layout_for(0x8081, _full_zone_hint("G815 LS TKL"))

    assert layout.description == "ANSI QWERTY tenkeyless"


def test_full_size_board_with_numpad_zones_stays_full():
    layout = layout_for(0x8081, _full_zone_hint("G915 X LS"))

    assert layout.description == "ANSI QWERTY 104-key full-size"


def test_g915x_tkl_gets_top_bar():
    layout = layout_for(0x8081, _full_zone_hint("G915 X LS TKL"))

    assert layout.description == "G915 X TKL"
    top = {c.zone_id: (c.row, c.col, c.label) for c in layout.cells if c.group == "media"}
    assert top == {
        210: (0, 0, "Logo"),
        153: (0, 5, "Bright"),
        158: (0, 10, "Prev"),
        155: (0, 11, "Play"),
        157: (0, 12, "Next"),
        156: (0, 13, "Mute"),
    }
    esc = next(c for c in layout.cells if c.zone_id == 38)
    assert esc.row == 1


def test_g915x_tkl_top_bar_paints_in_place_and_numpad_stays_hidden():
    hint = _full_zone_hint("G915 X LS TKL")
    bound = bind(layout_for(0x8081, hint), hint["zones"], lambda z: f"KEY {z}")

    top = {bc.cell.zone_id for bc in bound.matrix if bc.cell.group == "media" and bc.bound}
    assert top == {210, 153, 155, 156, 157, 158}
    assert not bound.strip  # nothing left over for the bottom strip
    drawn = {bc.cell.zone_id for bc in bound.matrix}
    assert 80 not in drawn and 95 not in drawn  # phantom numpad zones


def test_g915x_tkl_still_regional():
    hint = _full_zone_hint("G915 X LS TKL")
    hint["keyboard_layout"] = 2  # ISO QWERTY

    layout = layout_for(0x8081, hint)
    assert layout.description == "G915 X TKL"
    assert any(c.zone_id == 97 for c in layout.cells)  # ISO extra key
