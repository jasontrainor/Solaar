"""Button Mapping (onboard-buttons) edits buttons in an onboard profile sector, and
LED Control must not knock the device out of its onboard profile."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from logitech_receiver import common
from logitech_receiver import hidpp20
from logitech_receiver import settings_templates as st
from logitech_receiver.hidpp20_constants import SupportedFeature

SIZE = 255
# Buttons as the G502 X PLUS stores them: left, right, middle, Ctrl, DPI shift, Shift
BUTTONS = ["80010001", "80010002", "80010004", "80020100", "90070000", "80020200"]


def _sector(buttons):
    raw = bytearray(b"\xff" * SIZE)
    raw[0:32] = bytes(32)
    for i, b in enumerate(buttons):
        raw[32 + i * 4 : 36 + i * 4] = bytes.fromhex(b)
    raw[-2:] = common.int2bytes(common.crc16(bytes(raw[:-2])), 2)
    return bytes(raw)


class FakeDevice:
    def __init__(self, mode=0x01, active=2, persisted=None):
        self.mode = mode
        self.active = active
        self.persister = persisted if persisted is not None else {}
        self.sectors = {2: _sector(BUTTONS), 0x0101: _sector(BUTTONS[:3] + ["80010008", "90070000", "80010010"])}
        profile = SimpleNamespace(sector=2, enabled=1, buttons=[hidpp20.Button.from_bytes(bytes.fromhex(b)) for b in BUTTONS])
        self.profiles = SimpleNamespace(size=SIZE, sectors=16, buttons=len(BUTTONS), profiles={2: profile})
        self.features = {SupportedFeature.ONBOARD_PROFILES: 1}
        self.requests = []

    def feature_request(self, feature, fn, *params):
        self.requests.append((feature, fn, params))
        if feature == SupportedFeature.ONBOARD_PROFILES:
            if fn == 0x20:
                return bytes([self.mode]) + bytes(15)
            if fn == 0x40:
                return common.int2bytes(self.active, 2) + bytes(14)
        return bytes(16)


@pytest.fixture
def sectors(mocker):
    written = {}

    def read_sector(device, sector, size):
        return device.sectors[sector]

    def write_sector(device, sector, data):
        written[sector] = data
        device.sectors[sector] = data
        return True

    mocker.patch.object(hidpp20.OnboardProfiles, "read_sector", side_effect=read_sector)
    mocker.patch.object(hidpp20.OnboardProfiles, "write_sector", side_effect=write_sector)
    return written


@pytest.mark.parametrize(
    "raw, name",
    [
        ("80010001", "Left Click"),
        ("80010008", "Back"),
        ("80010040", "Mouse Button 7"),
        ("80020100", "Ctrl"),
        ("80020300", "Ctrl+Shift"),
        ("90070000", "DPI Shift"),
        ("9007FF00", "DPI Shift"),
        ("8000FFFF", "Disabled"),
        ("FFFFFFFF", "Not Mapped"),
        ("00010020", "Macro"),
    ],
)
def test_action_names(raw, name):
    assert st.onboard_button_action_name(st._normalize_button(bytes.fromhex(raw))) == name


def test_function_padding_byte_is_ignored():
    assert st._normalize_button(bytes.fromhex("9007FF00")) == st._normalize_button(bytes.fromhex("90070000"))


def test_build_names_buttons_after_factory_actions(sectors):
    validator = st.OnboardButtons.validator_class.build(st.OnboardButtons, FakeDevice())
    names = [str(k) for k in validator.choices]
    assert names[3] == "Button 4 (Back)"
    assert names[4] == "Button 5 (DPI Shift)"
    # the current custom mapping is offered even though it isn't a stock choice
    assert st._send_key(0x01, 0) in validator.choices[4]


def test_read_returns_active_profile_button(sectors):
    device = FakeDevice()
    rw = st.OnboardButtons.rw_class(SupportedFeature.ONBOARD_PROFILES)
    assert rw.read(device, 5)[1:] == bytes.fromhex("90070000")
    assert rw.read(device, 4)[1:] == bytes.fromhex("80020100")


def test_write_patches_one_button_and_reloads_active_profile(sectors):
    device = FakeDevice()
    rw = st.OnboardButtons.rw_class(SupportedFeature.ONBOARD_PROFILES)
    assert rw.write(device, 4, bytes.fromhex("80010008"))

    new = sectors[2]
    old = _sector(BUTTONS)
    assert new[32 + 12 : 36 + 12] == bytes.fromhex("80010008")
    assert new[: 32 + 12] == old[: 32 + 12] and new[36 + 12 : -2] == old[36 + 12 : -2]
    assert common.crc16(new[:-2]) == common.bytes2int(new[-2:])
    assert (SupportedFeature.ONBOARD_PROFILES, 0x30, (b"\x00\x02",)) in device.requests
    assert device.profiles.profiles[2].buttons[3].value == 8


def test_write_refuses_sector_with_bad_checksum(sectors):
    device = FakeDevice()
    device.sectors[2] = device.sectors[2][:-2] + b"\x00\x00"
    rw = st.OnboardButtons.rw_class(SupportedFeature.ONBOARD_PROFILES)
    assert rw.write(device, 4, bytes.fromhex("80010008")) is None
    assert sectors == {}


def test_host_mode_edits_profile_solaar_will_select(sectors):
    device = FakeDevice(mode=0x02, active=0, persisted={"onboard_profiles": 2})
    assert st._onboard_target_sector(device) == 2


def _claim(device):
    setting = st.RGBControl.__new__(st.RGBControl)
    device.settings = []
    device.cleanups = []
    setting._repaint_after_claim = MagicMock()
    setting._claim_sw_control(device)
    return [r for r in device.requests if r[0] == SupportedFeature.ONBOARD_PROFILES and r[1] == 0x10]


def test_led_control_keeps_selected_onboard_profile(mocker):
    mocker.patch.object(st.rgb_power, "start")
    assert _claim(FakeDevice(persisted={"onboard_profiles": 2})) == []


def test_led_control_takes_host_mode_without_a_profile(mocker):
    mocker.patch.object(st.rgb_power, "start")
    assert _claim(FakeDevice(persisted={"onboard_profiles": 0})) == [(SupportedFeature.ONBOARD_PROFILES, 0x10, (b"\x02",))]
