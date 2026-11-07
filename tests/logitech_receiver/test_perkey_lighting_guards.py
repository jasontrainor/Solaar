"""PerKeyLighting must never persist or return a non-map value.

Regression: `solaar config <dev> per-key-lighting <KEY>` (a query) was
forwarded to the running GUI, which wrote the bare key name as the whole
setting and saved it, wiping every saved key color.
"""

from unittest.mock import MagicMock

from logitech_receiver import settings_templates
from logitech_receiver import special_keys

NO_CHANGE = special_keys.COLORSPLUS["No change"]


def _setting(value=None, persisted=None):
    s = settings_templates.PerKeyLighting.__new__(settings_templates.PerKeyLighting)
    device = MagicMock()
    device.online = True
    device.persister = {} if persisted is None else {"per-key-lighting": persisted}
    s._device = device
    s._value = value
    s._validator = MagicMock()
    s._validator.choices = {1: None, 2: None}
    s.persist = True
    s.update = MagicMock()
    return s


def test_write_rejects_non_map_without_persisting():
    s = _setting(value={1: 0xFF0000})

    assert s.write("PLAY/PAUSE") is None
    s.update.assert_not_called()
    assert s._value == {1: 0xFF0000}


def test_read_discards_corrupt_saved_value():
    s = _setting(persisted="PLAY/PAUSE")

    assert s.read() == {1: NO_CHANGE, 2: NO_CHANGE}


def test_read_keeps_valid_saved_map():
    s = _setting(persisted={1: 0x123456, 2: NO_CHANGE})

    assert s.read() == {1: 0x123456, 2: NO_CHANGE}
