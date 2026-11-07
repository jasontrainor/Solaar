## Copyright (C) 2026  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License along
## with this program; if not, write to the Free Software Foundation, Inc.,
## 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Named per-key lighting themes, stored as JSON files.

A theme maps per-key zone ids to colors. Keys without a color are left out
and come back as unset ("no change") when the theme is applied, so applying
a theme replaces the whole per-key map. Zone ids are shared across Logitech
keyboards, so a theme saved on one board applies to another; zones the
target doesn't have are ignored.

Themes live in $XDG_CONFIG_HOME/solaar/themes/<name>.json. File format:

    {
      "format": "solaar-perkey-theme",
      "version": 1,
      "name": "Gaming",
      "device": "G915 X LS TKL",
      "colors": {"38": "#613583", "55": "#ff0000"}
    }

Used by both the per-key editor and `solaar theme`; no GTK here.
"""

from __future__ import annotations

import json
import os
import re

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

FORMAT = "solaar-perkey-theme"
VERSION = 1
UNSET = -1


class ThemeError(Exception):
    """A theme file is missing, unreadable, or not a valid theme."""


@dataclass
class Theme:
    name: str
    colors: dict[int, int] = field(default_factory=dict)
    device: str = ""

    def full_map(self, zones) -> dict[int, int]:
        """The per-key map that applying this theme to a device with `zones`
        produces: theme colors where set, unset everywhere else."""
        return {int(z): self.colors.get(int(z), UNSET) for z in zones}

    def to_json(self) -> str:
        data = {
            "format": FORMAT,
            "version": VERSION,
            "name": self.name,
            "device": self.device,
            "colors": {str(z): f"#{c:06x}" for z, c in sorted(self.colors.items())},
        }
        return json.dumps(data, indent=2) + "\n"

    @classmethod
    def from_colors(cls, name: str, colors: dict[int, int], device: str = "") -> Theme:
        """Build a theme from a per-key map, dropping unset keys."""
        kept = {int(z): int(c) for z, c in colors.items() if isinstance(c, int) and 0 <= int(c) <= 0xFFFFFF}
        return cls(name=name, colors=kept, device=device)

    @classmethod
    def from_json(cls, text: str) -> Theme:
        try:
            data = json.loads(text)
        except ValueError as e:
            raise ThemeError(f"not valid JSON: {e}") from e
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            raise ThemeError("not a Solaar per-key theme file")
        if not isinstance(data.get("version"), int) or data["version"] > VERSION:
            raise ThemeError(f"unsupported theme version {data.get('version')!r}")
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ThemeError("theme has no name")
        raw = data.get("colors")
        if not isinstance(raw, dict):
            raise ThemeError("theme has no colors")
        colors = {}
        for key, value in raw.items():
            try:
                zone = int(key)
                color = _parse_color(value)
            except (TypeError, ValueError) as e:
                raise ThemeError(f"bad entry {key!r}: {value!r}") from e
            colors[zone] = color
        device = data.get("device") if isinstance(data.get("device"), str) else ""
        return cls(name=name.strip(), colors=colors, device=device)


def _parse_color(value) -> int:
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return int(value[1:], 16)
    raise ValueError("color must be #rrggbb")


def themes_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser(os.path.join("~", ".config"))
    return Path(base) / "solaar" / "themes"


def _file_for(name: str) -> Path:
    stem = re.sub(r"[^A-Za-z0-9 ._-]", "_", name.strip()).strip(" .")
    if not stem:
        raise ThemeError(f"invalid theme name {name!r}")
    return themes_dir() / f"{stem}.json"


def list_themes() -> list[Theme]:
    """All valid saved themes, sorted by name. Unreadable files are skipped."""
    directory = themes_dir()
    if not directory.is_dir():
        return []
    themes = []
    for path in directory.glob("*.json"):
        try:
            themes.append(Theme.from_json(path.read_text(encoding="utf-8")))
        except (OSError, ThemeError):
            continue
    return sorted(themes, key=lambda t: t.name.lower())


def exists(name: str) -> bool:
    return _file_for(name).is_file()


def load(name: str) -> Theme:
    path = _file_for(name)
    if not path.is_file():
        raise ThemeError(f"no theme named {name!r}")
    return read_file(path)


def save(theme: Theme) -> Path:
    path = _file_for(theme.name)
    write_file(theme, path)
    return path


def delete(name: str) -> None:
    path = _file_for(name)
    if not path.is_file():
        raise ThemeError(f"no theme named {name!r}")
    path.unlink()


def read_file(path) -> Theme:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise ThemeError(f"cannot read {path}: {e.strerror or e}") from e
    return Theme.from_json(text)


def write_file(theme: Theme, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(theme.to_json(), encoding="utf-8")
    os.replace(tmp, path)


def import_file(path) -> Theme:
    """Validate a theme file and add it to the saved themes (replacing any
    saved theme with the same name). Returns the imported theme."""
    theme = read_file(path)
    save(theme)
    return theme
