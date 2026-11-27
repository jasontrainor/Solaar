from types import SimpleNamespace

import pytest

from logitech_receiver import dpi_osd
from logitech_receiver.dpi_osd import DpiEvent
from solaar.ui import dpi_osd as ui

AREA = SimpleNamespace(x=0, y=0, width=1920, height=1080)


@pytest.mark.parametrize(
    "position, expected",
    [
        (dpi_osd.TOP_LEFT, (40, 40)),
        (dpi_osd.TOP, (910, 40)),
        (dpi_osd.CENTER, (910, 515)),
        (dpi_osd.RIGHT, (1780, 515)),
        (dpi_osd.BOTTOM, (910, 990)),
        (dpi_osd.BOTTOM_RIGHT, (1780, 990)),
    ],
)
def test_overlay_positions(position, expected):
    assert ui.overlay_origin(AREA, 100, 50, position, 40) == expected


def test_overlay_position_on_a_second_monitor():
    area = SimpleNamespace(x=1920, y=0, width=2560, height=1440)
    assert ui.overlay_origin(area, 100, 50, dpi_osd.TOP_LEFT, 40) == (1960, 40)


def test_describe():
    assert ui.describe(DpiEvent(1600, (800, 1600, 3200))) == "1600 DPI (level 2 of 3)"
    assert ui.describe(DpiEvent(1700, (800, 1600))) == "1700 DPI"
    assert ui.describe(DpiEvent(400, (800,), shift=True)) == "DPI Shift: 400 DPI"


class _Recorder:
    def __init__(self, monkeypatch, overlay_works=True, desktop_works=True):
        self.calls = []
        overlay = SimpleNamespace(show=lambda event, **kw: self.calls.append(("overlay", event.dpi, kw)) or overlay_works)
        monkeypatch.setattr(ui, "_get_overlay", lambda: overlay)
        monkeypatch.setattr(ui, "_desktop_osd", lambda text: self.calls.append(("desktop", text)) or desktop_works)
        monkeypatch.setattr(ui.desktop_notifications, "show", lambda dev, text: self.calls.append(("notification", text)))


def _device(**saved):
    return SimpleNamespace(name="Mouse", persister=dict(saved))


def test_overlay_gets_the_saved_position_time_and_size(monkeypatch):
    rec = _Recorder(monkeypatch)
    device = _device(**{"dpi-osd-position": dpi_osd.TOP, "dpi-osd-duration": 3000, "dpi-osd-size": dpi_osd.SIZE_LARGE})
    ui.show(device, DpiEvent(1600))
    assert rec.calls == [("overlay", 1600, {"position": dpi_osd.TOP, "duration": 3000, "scale": 1.5})]


def test_overlay_falls_back_to_the_desktop_osd_then_a_notification(monkeypatch):
    rec = _Recorder(monkeypatch, overlay_works=False, desktop_works=False)
    ui.show(_device(), DpiEvent(1600))
    assert [c[0] for c in rec.calls] == ["overlay", "desktop", "notification"]


def test_desktop_style_skips_the_shift_release(monkeypatch):
    rec = _Recorder(monkeypatch)
    device = _device(**{"dpi-osd-style": dpi_osd.STYLE_DESKTOP})
    ui.show(device, DpiEvent(800, shift=True))
    ui.show(device, DpiEvent(1600, shift_released=True))
    assert rec.calls == [("desktop", "DPI Shift: 800 DPI")]


def test_notification_style(monkeypatch):
    rec = _Recorder(monkeypatch)
    ui.show(_device(**{"dpi-osd-style": dpi_osd.STYLE_NOTIFICATION}), DpiEvent(2400))
    assert rec.calls == [("notification", "2400 DPI")]


@pytest.mark.parametrize(
    "saved, greyed",
    [
        ({}, set()),
        ({"dpi-osd": dpi_osd.OFF}, {"dpi-osd-style", "dpi-osd-position", "dpi-osd-duration", "dpi-osd-size"}),
        ({"dpi-osd-style": dpi_osd.STYLE_DESKTOP}, {"dpi-osd-position", "dpi-osd-duration", "dpi-osd-size"}),
    ],
)
def test_rows_grey_out_when_they_do_nothing(saved, greyed):
    from solaar.ui import config_panel

    device = _device(**saved)
    names = ("dpi-osd", "dpi-osd-style", "dpi-osd-position", "dpi-osd-duration", "dpi-osd-size")
    assert {n for n in names if config_panel._gate_blocks(device, n)} == greyed
