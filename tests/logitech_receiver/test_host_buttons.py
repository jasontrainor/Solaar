from types import SimpleNamespace

from logitech_receiver import settings_templates as T
from logitech_receiver.hidpp20_constants import SupportedFeature as F

SPY_INDEX = 12


class _Dpi:
    name = "dpi"

    def __init__(self, value):
        self._value = value
        self.choices = [400, 800, 1200, 1600, 3200]
        self.writes = []

    def read(self, cached=True):
        return self._value

    def write(self, value, save=True):
        self._value = value
        self.writes.append((value, save))
        return value


class _Features:
    def __contains__(self, feature):
        return feature == F.MOUSE_BUTTON_SPY

    def get_feature(self, index):
        return F.MOUSE_BUTTON_SPY if index == SPY_INDEX else F.ROOT


class _Device:
    def __init__(self, dpi=1600):
        self.online = True
        self.persister = {}
        self.features = _Features()
        self.requests = []
        self.handlers = {}
        self.dpi = _Dpi(dpi)
        self.settings = [self.dpi]
        self.callbacks = []
        self.setting_callback = lambda dev, cls, values: self.callbacks.append(values)
        self.profiles = None

    def feature_request(self, feature, function, *params):
        self.requests.append((function, params))
        if function == 0x00:
            return bytes([11])
        if function == 0x30:
            return bytes(range(1, 12)) + bytes(5)
        return b""

    def add_notification_handler(self, name, fn):
        self.handlers[name] = fn

    def remove_notification_handler(self, name):
        self.handlers.pop(name, None)


def _setting(device):
    rw = T.HostButtons.rw_class(T.HostButtons.feature)
    validator = T.HostButtons.validator_class.build(T.HostButtons, device)
    return T.HostButtons(device, rw, validator)


def _spy(held):
    return SimpleNamespace(sub_id=SPY_INDEX, address=0x00, data=held.to_bytes(2, "big") + bytes(14))


def _table_writes(device):
    return [params[0] for function, params in device.requests if function == 0x40]


def test_build_names_eleven_buttons():
    setting = _setting(_Device())
    assert [int(k) for k in setting._validator.choices] == list(range(1, 12))


def test_native_remap_writes_table_without_spying():
    device = _Device()
    setting = _setting(device)
    setting.write({4: 5, 6: 4})  # swap back and forward
    table = _table_writes(device)[-1]
    assert table[:11] == bytes([1, 2, 3, 5, 5, 4, 7, 8, 9, 10, 11])
    assert device.requests[-1][0] == 0x20  # spy stopped
    assert not device.handlers
    # the stock table is kept, so later writes start from it, not from Solaar's
    assert device.persister[T._HOST_STOCK_KEY][:11] == list(range(1, 12))


def test_dpi_buttons_are_silenced_and_spied():
    device = _Device()
    setting = _setting(device)
    setting.write({5: T.HOST_BUTTON_DPI_SHIFT, 9: T.HOST_BUTTON_DPI_UP, 10: T.HOST_BUTTON_DISABLED})
    table = _table_writes(device)[-1]
    assert table[4] == 0 and table[8] == 0 and table[9] == 0
    assert device.requests[-1][0] == 0x10  # spy started
    assert "host-buttons" in device.handlers


def test_dpi_up_down_steps_through_levels_and_saves():
    device = _Device(dpi=800)
    setting = _setting(device)
    setting.write({9: T.HOST_BUTTON_DPI_UP, 10: T.HOST_BUTTON_DPI_DOWN})
    handler = device.handlers["host-buttons"]
    assert handler(device, _spy(1 << 8)) is True  # button 9 down
    handler(device, _spy(0))
    assert device.dpi.writes[-1] == (1600, True)
    handler(device, _spy(1 << 9))  # button 10 down
    assert device.dpi.writes[-1] == (800, True)
    assert device.callbacks[-1] == [800]


def test_dpi_shift_is_temporary():
    device = _Device(dpi=1600)
    setting = _setting(device)
    setting.write({5: T.HOST_BUTTON_DPI_SHIFT})
    handler = device.handlers["host-buttons"]
    handler(device, _spy(1 << 4))
    assert device.dpi.writes[-1] == (400, False)
    handler(device, _spy(0))
    assert device.dpi.writes[-1] == (1600, False)


def test_other_notifications_are_left_alone():
    device = _Device()
    setting = _setting(device)
    setting.write({9: T.HOST_BUTTON_DPI_UP})
    other = SimpleNamespace(sub_id=3, address=0x00, data=bytes(16))
    assert device.handlers["host-buttons"](device, other) is None


def _with_factory(setting):
    # the G502 X PLUS ROM profile: buttons 5 and 7-11 have functions
    setting._validator.factory = {
        0: T._send_button(0x01),
        3: T._send_button(0x08),
        4: T._function(T.hidpp20.ButtonFunctions.SHIFT_DPI),
        6: T._function(T.hidpp20.ButtonFunctions.TILT_LEFT),
        7: T._function(T.hidpp20.ButtonFunctions.TILT_RIGHT),
        8: T._function(T.hidpp20.ButtonFunctions.CYCLE_PROFILE),
        9: T._function(T.hidpp20.ButtonFunctions.NEXT_DPI),
        10: T._function(T.hidpp20.ButtonFunctions.PREVIOUS_DPI),
    }
    return setting


def test_default_does_the_factory_action():
    device = _Device()
    setting = _with_factory(_setting(device))
    assert setting.effective_action(1) == T.HOST_BUTTON_DEFAULT
    assert setting.effective_action(5) == T.HOST_BUTTON_DPI_SHIFT
    assert setting.effective_action(7) == T.HOST_BUTTON_SCROLL_LEFT
    assert setting.effective_action(9) == T.HOST_BUTTON_DISABLED  # profile cycle means nothing in host mode
    assert setting.effective_action(10) == T.HOST_BUTTON_DPI_UP
    setting.write({10: 4})  # an explicit choice wins
    assert setting.effective_action(10) == 4
    table = _table_writes(device)[-1]
    assert table[:11] == bytes([1, 2, 3, 4, 0, 6, 0, 0, 0, 4, 0])
    assert device.requests[-1][0] == 0x10


def test_onboard_mode_gets_the_stock_table_and_no_spy():
    device = _Device()
    device.features = type("F", (), {"__contains__": lambda s, f: True, "get_feature": _Features.get_feature})()
    base = device.feature_request

    def request(feature, function, *params):
        if feature == F.ONBOARD_PROFILES and function == 0x20:
            return b"\x01"
        return base(feature, function, *params)

    device.feature_request = request
    setting = _setting(device)
    setting.write({9: T.HOST_BUTTON_DPI_UP})
    assert _table_writes(device)[-1][:11] == bytes(range(1, 12))
    assert device.requests[-1][0] == 0x20
    assert not device.handlers


def test_wheel_tilt_scrolls_sideways(monkeypatch):
    scrolls = []
    monkeypatch.setattr(T.diversion, "simulate_scroll", lambda dx, dy: scrolls.append((dx, dy)))
    device = _Device()
    setting = _with_factory(_setting(device))
    setting.write({})
    handler = device.handlers["host-buttons"]
    handler(device, _spy(1 << 6))  # tilt left
    handler(device, _spy(0))
    handler(device, _spy(1 << 7))  # tilt right
    handler(device, _spy(0))
    assert scrolls == [(-1, 0), (1, 0)]
    assert not setting._scroll_timers
