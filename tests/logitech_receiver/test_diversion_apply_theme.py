from types import SimpleNamespace

import pytest

from logitech_receiver import diversion
from solaar import perkey_themes


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


class _PerKey:
    name = "per-key-lighting"

    def __init__(self):
        self.choices = [1, 2, 3]
        self.written = None

    def write(self, value, save=True):
        self.written = value
        return value


def _device(name="Keyboard", with_perkey=True, others=()):
    setting = _PerKey()
    recorded = []
    dev = SimpleNamespace(name=name, settings=[setting] if with_perkey else [])
    dev.setting_callback = lambda d, cls, values: recorded.append((d, cls, values))
    by_name = {d.name: d for d in others}
    dev.find = lambda ident: by_name.get(ident)
    return dev, setting, recorded


def test_parse_name_only():
    action = diversion.ApplyTheme("Windows")
    assert (action.device, action.theme) == (None, "Windows")
    assert action.data() == {"ApplyTheme": "Windows"}


def test_parse_device_and_name():
    action = diversion.ApplyTheme(["G915 X LS TKL", "Windows"])
    assert (action.device, action.theme) == ("G915 X LS TKL", "Windows")
    assert action.data() == {"ApplyTheme": ["G915 X LS TKL", "Windows"]}


def test_parse_bad_args_is_harmless():
    action = diversion.ApplyTheme(42, warn=False)
    dev, setting, _rec = _device()
    assert action.evaluate(None, None, dev, None) is None
    assert setting.written is None


def test_compiles_from_rule_yaml():
    rule = diversion.Rule([{"ApplyTheme": "Windows"}])
    assert isinstance(rule.components[0], diversion.ApplyTheme)


def test_applies_theme_to_originating_device():
    perkey_themes.save(perkey_themes.Theme("Windows", {1: 0xFF0000, 3: 0x00FF00}))
    dev, setting, recorded = _device()
    diversion.ApplyTheme("Windows").evaluate(None, None, dev, None)
    assert setting.written == {1: 0xFF0000, 2: perkey_themes.UNSET, 3: 0x00FF00}
    assert recorded == [(dev, _PerKey, [setting.written])]


def test_applies_theme_to_named_device():
    perkey_themes.save(perkey_themes.Theme("Windows", {2: 0x0000FF}))
    keyboard, kb_setting, _rec = _device("Keyboard")
    mouse, _m_setting, _mrec = _device("Mouse", with_perkey=False, others=[keyboard])
    diversion.ApplyTheme(["Keyboard", "Windows"]).evaluate(None, None, mouse, None)
    assert kb_setting.written == {1: perkey_themes.UNSET, 2: 0x0000FF, 3: perkey_themes.UNSET}


def test_missing_theme_or_per_key_does_nothing():
    dev, setting, recorded = _device()
    diversion.ApplyTheme("Nope").evaluate(None, None, dev, None)
    assert setting.written is None and recorded == []
    perkey_themes.save(perkey_themes.Theme("Windows", {1: 1}))
    mouse, _s, _r = _device("Mouse", with_perkey=False)
    assert diversion.ApplyTheme("Windows").evaluate(None, None, mouse, None) is None
