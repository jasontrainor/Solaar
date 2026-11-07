import json

import pytest

from solaar import perkey_themes as T


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


def test_save_load_round_trip_drops_unset_keys():
    theme = T.Theme.from_colors("Gaming", {38: 0x613583, 55: 0xFF0000, 56: T.UNSET}, device="G915 X LS TKL")
    path = T.save(theme)

    assert path == T.themes_dir() / "Gaming.json"
    loaded = T.load("Gaming")
    assert loaded.colors == {38: 0x613583, 55: 0xFF0000}
    assert loaded.device == "G915 X LS TKL"


def test_file_is_readable_json_with_hex_colors():
    T.save(T.Theme.from_colors("Work", {1: 0x00FF3B}))

    data = json.loads((T.themes_dir() / "Work.json").read_text())
    assert data == {
        "format": "solaar-perkey-theme",
        "version": 1,
        "name": "Work",
        "device": "",
        "colors": {"1": "#00ff3b"},
    }


def test_full_map_unsets_keys_not_in_theme_and_ignores_foreign_zones():
    theme = T.Theme(name="t", colors={1: 0x111111, 999: 0x222222})

    assert theme.full_map([1, 2, 3]) == {1: 0x111111, 2: T.UNSET, 3: T.UNSET}


def test_list_themes_sorted_and_skips_bad_files():
    T.save(T.Theme(name="beta", colors={1: 1}))
    T.save(T.Theme(name="Alpha", colors={1: 2}))
    (T.themes_dir() / "junk.json").write_text("{not json")

    assert [t.name for t in T.list_themes()] == ["Alpha", "beta"]


def test_list_themes_when_no_directory():
    assert T.list_themes() == []


def test_delete():
    T.save(T.Theme(name="gone", colors={1: 1}))
    T.delete("gone")

    assert not T.exists("gone")
    with pytest.raises(T.ThemeError):
        T.delete("gone")


def test_load_missing_raises():
    with pytest.raises(T.ThemeError, match="no theme named"):
        T.load("nope")


def test_names_are_made_safe_for_filenames():
    path = T.save(T.Theme(name="a/b: c", colors={1: 1}))

    assert path.parent == T.themes_dir()
    assert path.name == "a_b_ c.json"
    assert T.load("a/b: c").name == "a/b: c"


@pytest.mark.parametrize("name", ["", "   ", ".."])
def test_unusable_names_rejected(name):
    with pytest.raises(T.ThemeError):
        T.save(T.Theme(name=name, colors={1: 1}))


def test_import_and_export_files(tmp_path):
    exported = tmp_path / "share" / "mine.json"
    T.write_file(T.Theme(name="Shared", colors={5: 0xABCDEF}), exported)

    theme = T.import_file(exported)

    assert theme.name == "Shared"
    assert T.load("Shared").colors == {5: 0xABCDEF}


@pytest.mark.parametrize(
    "text, message",
    [
        ("[]", "not a Solaar"),
        ('{"format": "other"}', "not a Solaar"),
        ('{"format": "solaar-perkey-theme", "version": 99, "name": "x", "colors": {}}', "unsupported"),
        ('{"format": "solaar-perkey-theme", "version": 1, "colors": {}}', "no name"),
        ('{"format": "solaar-perkey-theme", "version": 1, "name": "x"}', "no colors"),
        ('{"format": "solaar-perkey-theme", "version": 1, "name": "x", "colors": {"a": "#000000"}}', "bad entry"),
        ('{"format": "solaar-perkey-theme", "version": 1, "name": "x", "colors": {"1": "red"}}', "bad entry"),
        ("{oops", "not valid JSON"),
    ],
)
def test_invalid_theme_files_rejected(tmp_path, text, message):
    path = tmp_path / "bad.json"
    path.write_text(text)

    with pytest.raises(T.ThemeError, match=message):
        T.import_file(path)
