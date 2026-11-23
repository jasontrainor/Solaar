# <img src="https://pwr-solaar.github.io/Solaar/img/solaar.svg" width="60px"/> Solaar

Solaar is a Linux manager for many Logitech keyboards, mice, and other devices
that connect wirelessly to a Unifying, Bolt, Lightspeed or Nano receiver
as well as many Logitech devices that connect via a USB cable or Bluetooth.
Solaar is not a device driver and responds only to special messages from devices
that are otherwise ignored by the Linux input system.

<a href="https://pwr-solaar.github.io/Solaar/index">More Information</a> -
<a href="https://pwr-solaar.github.io/Solaar/usage">Usage</a> -
<a href="https://pwr-solaar.github.io/Solaar/capabilities">Capabilities</a> -
<a href="https://pwr-solaar.github.io/Solaar/rules">Rules</a> -
<a href="https://pwr-solaar.github.io/Solaar/installation">Manual Installation</a> -
<a href="https://pwr-solaar.github.io/Solaar/issues">Known Issues</a>


## About this fork

This is a personal fork of [pwr-Solaar/Solaar](https://github.com/pwr-Solaar/Solaar).
The rest of this README describes upstream Solaar. On top of upstream, this fork adds:

### Onboard profile button mapping (gaming mice)
- **Button Mapping** setting (`onboard-buttons`) for devices with onboard profiles,
  such as the G502 X PLUS. It changes what each button does in the active onboard profile:
  mouse buttons, DPI Up/Down/Cycle/Default, **DPI Shift** (hold for the profile's shift DPI),
  scroll, profile switching, G-Shift, modifier keys, or disabled.
  Buttons are named after their factory action, and mappings set elsewhere (e.g. key combinations from G HUB) are kept.
  The mapping is stored on the device, so it works at power-on without Solaar running.

      solaar config "G502 X PLUS" onboard-buttons 4 Back

- **LED Control keeps the onboard profile on.** Taking over the lighting used to switch the device to
  host mode every time it connected, which turned off the onboard profile and its button mapping.
  When Onboard Profiles is set to a profile, the device now stays in it.
  (While a profile is active, the device may show the profile's lighting rather than Solaar's.)

### Per-key lighting editor
- **Color themes**: save, apply, import, export and delete named per-key themes from the editor's
  Themes menu. Themes are JSON files in `~/.config/solaar/themes/`.
- **`solaar theme` command**:

      solaar theme list
      solaar theme save <device> <name>
      solaar theme apply <device> <name>
      solaar theme delete <name>
      solaar theme import <file>
      solaar theme export <name> <file>

- Undo/redo, readable key labels, and TKL keyboard layout detection.
- A G915 X LIGHTSPEED TKL layout that includes its top bar (logo, brightness and media keys).
- Brush, Rect and Fill tools are labeled, with a hint describing what the active tool will do.

### Fixes
- A query like `solaar config <device> per-key-lighting <KEY>` no longer wipes every saved key color.
  A config already damaged this way no longer breaks the editor or LED Control at startup.
- Per-key zone 69 is named PAUSE (Pause/Break) and zone 155 PLAY/PAUSE (the media key).
  Previously they were PASTE and PAUSE.

### Development
- `make dev_venv` builds a local `.venv` that reuses the system GTK bindings and has the test and lint tools.
  `make dev_test` and `make dev_lint` run pytest and ruff from it.


[![codecov](https://codecov.io/gh/pwr-Solaar/Solaar/graph/badge.svg?token=D7YWFEWID6)](https://codecov.io/gh/pwr-Solaar/Solaar)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2+-blue.svg)](../LICENSE.txt)

<p align="center">
<img src="https://pwr-solaar.github.io/Solaar/screenshots/Solaar-main-window-multiple.png" width="54%"/>
  &#160;
<img src="https://pwr-solaar.github.io/Solaar/screenshots/Solaar-main-window-receiver.png" width="43%"/>
</p>

<p align="center">
<img src="https://pwr-solaar.github.io/Solaar/screenshots/Solaar-main-window-back-divert.png" width="49%"/>
  &#160;
<img src="https://pwr-solaar.github.io/Solaar/screenshots/Solaar-rule-editor.png" width="48%"/>
</p>

Solaar supports:
- pairing/unpairing of devices with receivers
- configuring device settings
- custom button configuration
- running rules in response to special messages from devices

For more information see
    <a href="https://pwr-solaar.github.io/Solaar/index">the main Solaar documentation page.</a> -


## Installation Packages

Up-to-date prebuilt packages are available for some Linux distros
(e.g., Fedora) in their standard repositories.
If a recent version of Solaar is not
available from the standard repositories for your distribution, you can try
one of these packages:

- Arch solaar package in the [extra repository][arch]
- Ubuntu/Kubuntu package in [Solaar stable ppa][ppa stable]
- NixOS Flake package in [Svenum/Solaar-Flake][nix flake]

Solaar is available from some other repositories
but may be several versions behind the current version:

- a [Debian package][debian], courtesy of Stephen Kitt
- a Ubuntu package is available from [universe repository][ubuntu universe repository]
- a [Gentoo package][gentoo], courtesy of Carlos Silva and Tim Harder
- a [Mageia package][mageia], courtesy of David Geiger

[ppa stable]: https://launchpad.net/~solaar-unifying/+archive/ubuntu/stable
[arch]: https://www.archlinux.org/packages/extra/any/solaar/
[gentoo]: https://packages.gentoo.org/packages/app-misc/solaar
[mageia]: http://mageia.madb.org/package/show/release/cauldron/application/0/name/solaar
[ubuntu universe repository]: http://packages.ubuntu.com/search?keywords=solaar&searchon=names&suite=all&section=all
[nix flake]: https://github.com/Svenum/Solaar-Flake
[debian]: https://packages.debian.org/search?keywords=solaar&searchon=names&suite=all&section=all
