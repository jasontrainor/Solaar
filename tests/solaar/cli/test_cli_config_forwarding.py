"""`solaar config` must not forward a query to the running GUI.

With a keyed setting and only a key (no value), the CLI just prints the
setting. It used to forward the command to the GUI anyway, which wrote the
key name as the setting's whole value.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from solaar.cli import config


class _FakeRemoteApp:
    """Stands in for Gtk.Application: claims a GUI is running and records
    anything that would have been sent to it."""

    sent = []

    def register(self):
        return True

    def get_is_remote(self):
        return True

    def run(self, argv):
        _FakeRemoteApp.sent.append(argv)


@pytest.fixture
def fake_gui(monkeypatch):
    Gtk = pytest.importorskip("gi.repository.Gtk")
    _FakeRemoteApp.sent = []
    monkeypatch.setattr(Gtk, "init_check", lambda *a: (True, []))
    monkeypatch.setattr(Gtk.Application, "new", staticmethod(lambda *a: _FakeRemoteApp()))
    return _FakeRemoteApp


def _run(monkeypatch, set_result, value_key="PLAY/PAUSE", extra_subkey=None):
    dev = MagicMock()
    dev.ping.return_value = True
    dev.serial = "SERIAL"
    dev.persister = {}
    setting = MagicMock()
    setting.name = "per-key-lighting"
    monkeypatch.setattr(config.settings_templates, "check_feature_setting", lambda d, n: setting)
    monkeypatch.setattr(config, "set", lambda d, s, a, save: set_result)
    args = SimpleNamespace(
        device="g915", setting="per-key-lighting", value_key=value_key, extra_subkey=extra_subkey, extra2=None
    )
    config.run(["receiver"], args, None, lambda receivers, name: iter([dev]))
    return dev


def test_query_is_not_forwarded_or_saved(monkeypatch, fake_gui):
    dev = _run(monkeypatch, (None, None, None))

    assert fake_gui.sent == []
    assert dev.persister == {}


def test_real_change_is_still_forwarded(monkeypatch, fake_gui):
    _run(monkeypatch, (0xFF0000, "Setting per-key-lighting", 0xFF0000), extra_subkey="0xff0000")

    assert len(fake_gui.sent) == 1
