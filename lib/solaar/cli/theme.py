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

"""`solaar theme` — manage per-key lighting themes from the command line.

    solaar theme list
    solaar theme save <device> <name>
    solaar theme apply <device> <name>
    solaar theme delete <name>
    solaar theme import <file>
    solaar theme export <name> <file>
"""

from __future__ import annotations

import yaml

from logitech_receiver import settings_templates

from solaar import perkey_themes

SETTING_NAME = "per-key-lighting"

# Commands that need an online device; the rest only touch theme files.
DEVICE_COMMANDS = ("save", "apply")

USAGE = {
    "list": "list",
    "save": "save <device> <name>",
    "apply": "apply <device> <name>",
    "delete": "delete <name>",
    "import": "import <file>",
    "export": "export <name> <file>",
}


def _expect(args, count):
    if len(args.args) != count:
        raise Exception(f"usage: solaar theme {USAGE[args.command]}")
    return args.args


def run(receivers, args, _find_receiver, find_device):
    command = args.command
    if command == "list":
        _expect(args, 0)
        themes = perkey_themes.list_themes()
        if not themes:
            print(f"No saved themes in {perkey_themes.themes_dir()}")
        for theme in themes:
            device = f"  (saved from {theme.device})" if theme.device else ""
            print(f"{theme.name}: {len(theme.colors)} keys{device}")
    elif command == "delete":
        (name,) = _expect(args, 1)
        perkey_themes.delete(name)
        print(f"Deleted theme '{name}'")
    elif command == "import":
        (path,) = _expect(args, 1)
        theme = perkey_themes.import_file(path)
        print(f"Imported theme '{theme.name}' ({len(theme.colors)} keys)")
    elif command == "export":
        name, path = _expect(args, 2)
        perkey_themes.write_file(perkey_themes.load(name), path)
        print(f"Exported theme '{name}' to {path}")
    elif command == "save":
        device_name, name = _expect(args, 2)
        dev, setting = _per_key_setting(receivers, find_device, device_name)
        theme = perkey_themes.Theme.from_colors(name, dict(setting.read() or {}), dev.name)
        perkey_themes.save(theme)
        print(f"Saved {len(theme.colors)} key colors from {dev.name} as theme '{name}'")
    elif command == "apply":
        device_name, name = _expect(args, 2)
        theme = perkey_themes.load(name)
        dev, setting = _per_key_setting(receivers, find_device, device_name)
        full = theme.full_map(int(k) for k in setting.choices)
        _apply(dev, setting, full)
        print(f"Applied theme '{name}' to {dev.name}")


def _per_key_setting(receivers, find_device, device_name):
    dev = None
    for dev in find_device(receivers, device_name.lower()):
        if dev.ping():
            break
        dev = None
    if not dev:
        raise Exception(f"no online device found matching '{device_name}'")
    setting = settings_templates.check_feature_setting(dev, SETTING_NAME)
    if setting is None:
        raise Exception(f"{dev.name} has no per-key lighting")
    return dev, setting


def _gui_application():
    """The running Solaar GUI as a remote Gtk.Application, or None."""
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gio
        from gi.repository import Gtk

        from solaar.cli.config import APP_ID

        if not Gtk.init_check()[0]:
            return None
        application = Gtk.Application.new(APP_ID, Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        application.register()
        return application if application.get_is_remote() else None
    except Exception:
        return None


def _apply(dev, setting, full):
    application = _gui_application()
    if application is not None:
        # Let the running GUI write it, so its per-key editor and saved
        # config stay in step. A single value means "write the whole map".
        application.run([yaml.dump(["config", dev.serial or dev.unitId, setting.name, full])])
        return
    setting.write(full, save=False)
    if dev.persister is not None and setting.persist:
        dev.persister[setting.name] = setting._value
