from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

from solaar import perkey_themes
from solaar.cli import theme as cli_theme


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # Never talk to a real running GUI from tests.
    monkeypatch.setattr(cli_theme, "_gui_application", lambda: None)


def _args(command, *rest):
    return SimpleNamespace(command=command, args=list(rest))


def _device(colors):
    dev = MagicMock()
    dev.name = "G915 X LS TKL"
    dev.serial = "SERIAL"
    dev.ping.return_value = True
    dev.persister = {}
    setting = MagicMock()
    setting.name = "per-key-lighting"
    setting.persist = True
    setting.choices = {z: None for z in colors}
    setting.read.return_value = dict(colors)

    def write(value, save=True):
        setting._value = value
        return value

    setting.write.side_effect = write
    return dev, setting


def _run(monkeypatch, args, dev=None, setting=None):
    if setting is not None:
        monkeypatch.setattr(cli_theme.settings_templates, "check_feature_setting", lambda d, n: setting)
    cli_theme.run(["receiver"], args, None, lambda receivers, name: iter([dev] if dev else []))


def test_save_then_list(monkeypatch, capsys):
    dev, setting = _device({1: 0xFF0000, 2: -1})

    _run(monkeypatch, _args("save", "g915", "Mine"), dev, setting)
    _run(monkeypatch, _args("list"))

    assert perkey_themes.load("Mine").colors == {1: 0xFF0000}
    assert "Mine: 1 keys  (saved from G915 X LS TKL)" in capsys.readouterr().out


def test_apply_without_gui_writes_full_map_and_saves(monkeypatch):
    perkey_themes.save(perkey_themes.Theme(name="T", colors={2: 0x00FF00}))
    dev, setting = _device({1: 0xFF0000, 2: -1})

    _run(monkeypatch, _args("apply", "g915", "T"), dev, setting)

    setting.write.assert_called_once_with({1: -1, 2: 0x00FF00}, save=False)
    assert dev.persister["per-key-lighting"] == {1: -1, 2: 0x00FF00}


def test_apply_with_gui_forwards_whole_map(monkeypatch):
    perkey_themes.save(perkey_themes.Theme(name="T", colors={1: 0x0000FF}))
    dev, setting = _device({1: -1, 2: -1})
    app = MagicMock()
    monkeypatch.setattr(cli_theme, "_gui_application", lambda: app)

    _run(monkeypatch, _args("apply", "g915", "T"), dev, setting)

    setting.write.assert_not_called()
    (argv,), _ = app.run.call_args
    assert yaml.safe_load("".join(argv)) == ["config", "SERIAL", "per-key-lighting", {1: 0x0000FF, 2: -1}]


def test_export_import_delete(monkeypatch, tmp_path):
    perkey_themes.save(perkey_themes.Theme(name="T", colors={1: 1}))
    out = tmp_path / "t.json"

    _run(monkeypatch, _args("export", "T", str(out)))
    _run(monkeypatch, _args("delete", "T"))
    assert not perkey_themes.exists("T")
    _run(monkeypatch, _args("import", str(out)))
    assert perkey_themes.load("T").colors == {1: 1}


def test_wrong_argument_count_shows_usage(monkeypatch):
    with pytest.raises(Exception, match="usage: solaar theme apply <device> <name>"):
        _run(monkeypatch, _args("apply", "g915"))


def test_apply_needs_online_device(monkeypatch):
    perkey_themes.save(perkey_themes.Theme(name="T", colors={1: 1}))

    with pytest.raises(Exception, match="no online device"):
        _run(monkeypatch, _args("apply", "nothing", "T"))
