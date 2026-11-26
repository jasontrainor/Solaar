from types import SimpleNamespace

from logitech_receiver import hidpp20
from solaar.ui import config_panel


def _device(idle, effect, sleep):
    values = {"rgb_idle_timeout": idle, "rgb_idle_effect": effect, "rgb_sleep_timeout": sleep}
    settings = [SimpleNamespace(name=n, _value=v) for n, v in values.items()]
    return SimpleNamespace(settings=settings, persister={})


DIM50 = hidpp20.LEDEffectSetting(ID=0x80, intensity=50)
NO_CHANGE = hidpp20.LEDEffectSetting(ID=0x00)


def test_presets_match_current_values():
    assert config_panel._matching_idle_preset(_device(0, NO_CHANGE, 0)) == "on"
    assert config_panel._matching_idle_preset(_device(60, DIM50, 0)) == "dim"
    assert config_panel._matching_idle_preset(_device(60, DIM50, 600)) == "dim-off"
    assert config_panel._matching_idle_preset(_device(0, DIM50, 300)) == "off"


def test_other_values_are_custom():
    assert config_panel._matching_idle_preset(_device(60, NO_CHANGE, 600)) == "custom"
    assert config_panel._matching_idle_preset(_device(60, hidpp20.LEDEffectSetting(ID=0x80, intensity=25), 0)) == "custom"


def test_idle_effect_gated_when_idle_is_never():
    assert config_panel._gate_blocks(_device(0, DIM50, 300), "rgb_idle_effect")
    assert not config_panel._gate_blocks(_device(60, DIM50, 300), "rgb_idle_effect")
