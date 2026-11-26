import pytest

from solaar.ui import config_panel


@pytest.mark.parametrize(
    "name, group",
    [
        ("dpi", config_panel.GROUP_POINTER),
        ("dpi_extended", config_panel.GROUP_POINTER),
        ("hires-smooth-invert", config_panel.GROUP_POINTER),
        ("report_rate", config_panel.GROUP_POINTER),
        ("onboard-buttons", config_panel.GROUP_BUTTONS),
        ("divert-keys", config_panel.GROUP_BUTTONS),
        ("fn-swap", config_panel.GROUP_BUTTONS),
        ("per-key-lighting", config_panel.GROUP_LIGHTING),
        ("rgb_zone_1", config_panel.GROUP_LIGHTING),
        ("rgb_idle_effect", config_panel.GROUP_LIGHTING),
        ("led_zone_2", config_panel.GROUP_LIGHTING),
        ("brightness_control", config_panel.GROUP_LIGHTING),
        ("headset-signature-startup", config_panel.GROUP_LIGHTING),
        ("headset-mic-gain", config_panel.GROUP_AUDIO),
        ("headset-auto-sleep", config_panel.GROUP_DEVICE),
        ("onboard_profiles", config_panel.GROUP_DEVICE),
        ("change-host", config_panel.GROUP_DEVICE),
        ("something-new", config_panel.GROUP_OTHER),
    ],
)
def test_setting_group(name, group):
    assert config_panel.setting_group(name) == group
