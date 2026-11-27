from types import SimpleNamespace

import pytest

from logitech_receiver import dpi_osd
from logitech_receiver import settings_templates as T


@pytest.fixture
def shown(monkeypatch):
    events = []
    monkeypatch.setattr(dpi_osd, "handler", lambda dev, event: events.append(event))
    return events


def _device(**saved):
    return SimpleNamespace(persister=dict(saved))


def test_defaults_show_changes_and_shift(shown):
    device = _device()
    dpi_osd.dpi_changed(device, 1600, [800, 1600])
    dpi_osd.dpi_changed(device, 800, shift=True)
    assert shown == [dpi_osd.DpiEvent(1600, (800, 1600)), dpi_osd.DpiEvent(800, shift=True)]


def test_changes_only_leaves_out_dpi_shift(shown):
    device = _device(**{"dpi-osd": dpi_osd.CHANGES})
    dpi_osd.dpi_changed(device, 800, shift=True)
    dpi_osd.dpi_changed(device, 1600, shift_released=True)
    dpi_osd.dpi_changed(device, 2400)
    assert shown == [dpi_osd.DpiEvent(2400)]


def test_off_shows_nothing(shown):
    dpi_osd.dpi_changed(_device(**{"dpi-osd": dpi_osd.OFF}), 2400)
    assert shown == []


def test_no_handler_and_bad_saved_values_are_harmless(monkeypatch):
    monkeypatch.setattr(dpi_osd, "handler", None)
    dpi_osd.dpi_changed(_device(), 1600)
    assert dpi_osd.saved(_device(**{"dpi-osd-size": "big"}), dpi_osd.SIZE) == dpi_osd.SIZE_MEDIUM
    assert dpi_osd.saved(SimpleNamespace(persister=None), dpi_osd.POSITION) == dpi_osd.BOTTOM


def test_a_failing_handler_is_logged_not_raised(monkeypatch):
    def broken(dev, event):
        raise RuntimeError("no display")

    monkeypatch.setattr(dpi_osd, "handler", broken)
    dpi_osd.dpi_changed(_device(), 1600)


@pytest.mark.parametrize(
    "setting_class, saved, expected",
    [
        (T.DpiOsd, {}, dpi_osd.CHANGES_AND_SHIFT),
        (T.DpiOsdStyle, {"dpi-osd-style": dpi_osd.STYLE_DESKTOP}, dpi_osd.STYLE_DESKTOP),
        (T.DpiOsdPosition, {}, dpi_osd.BOTTOM),
        (T.DpiOsdDuration, {"dpi-osd-duration": 3000}, 3000),
        (T.DpiOsdSizeExtended, {}, dpi_osd.SIZE_MEDIUM),
    ],
)
def test_settings_read_the_saved_choice_and_write_nothing(setting_class, saved, expected):
    device = SimpleNamespace(persister=dict(saved), online=True)
    rw = setting_class.rw_class(setting_class.feature)
    validator = setting_class.validator_class(**setting_class.validator_options)
    value = validator.validate_read(rw.read(device))
    assert int(value) == expected
    assert rw.write(device, validator.prepare_write(value)) is True
