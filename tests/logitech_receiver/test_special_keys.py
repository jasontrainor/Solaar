from logitech_receiver.special_keys import KEYCODES


def test_keycodes_name_pause_and_play_pause_zones():
    assert KEYCODES["PAUSE"] == 69  # Pause/Break key, not Paste
    assert KEYCODES["PLAY/PAUSE"] == 155  # media key
    assert str(KEYCODES[69]) == "PAUSE"
    assert str(KEYCODES[155]) == "PLAY/PAUSE"
