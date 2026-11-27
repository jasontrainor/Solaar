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

### Button mapping for gaming mice (G502 X PLUS and others)
- **Button Mapping without onboard profiles** (`host-buttons`). Set Onboard Profiles to Disabled
  and Solaar runs the mouse itself: DPI, report rate, lighting and the buttons all come from
  Solaar's settings, so nothing in a profile can override them.
  - Uses the mouse's MOUSE BUTTON SPY feature (0x8110). Remapping to another mouse button is done
    by the mouse itself. DPI Up/Down/Cycle/Default, **DPI Shift** (held), and Scroll Left/Right
    (wheel tilt) are done by Solaar, so they need Solaar running.
  - **Default** does what the button does in an onboard profile: on the G502 X PLUS the DPI buttons
    step through the profile's DPI levels, the sniper button holds its shift DPI, and the wheel
    tilt scrolls sideways. The DPI levels are taken from the onboard profile Solaar last used.
  - A DPI set with the DPI buttons is saved, like one set in Solaar, so it comes back when the mouse
    reconnects. DPI Shift is temporary.
  - The mouse forgets the mapping when it loses power. Solaar re-applies it whenever the mouse
    connects.

      solaar config "G502 X PLUS" onboard_profiles Disabled
      solaar config "G502 X PLUS" host-buttons 4 Forward

- **Onboard Button Mapping** (`onboard-buttons`) changes the buttons stored in the active onboard
  profile instead, so they work at power-on without Solaar: mouse buttons, DPI Up/Down/Cycle/Default,
  DPI Shift, scroll, profile switching, G-Shift, modifier keys, or disabled. Buttons are named after
  their factory action, and mappings set elsewhere (e.g. key combinations from G HUB) are kept.

      solaar config "G502 X PLUS" onboard-buttons 4 Back

  Only one of the two is active at a time. The other is greyed out, depending on Onboard Profiles.

### On-screen DPI
When the DPI buttons change the DPI, the new DPI pops up on screen as a small card, with a dot for
each DPI level. Holding DPI Shift (the sniper button) shows **DPI SHIFT** and its DPI for as long as
the button is held, then the DPI it goes back to. It works in host mode and with an onboard profile
(with an onboard profile the mouse may not report DPI Shift). Solaar needs to be running.

The settings are on each mouse's page, under Pointer and Scrolling. Changing any of them shows a preview.

| Setting | Choices |
|---|---|
| On-screen DPI (`dpi-osd`) | Off, DPI changes, DPI changes and DPI Shift (default) |
| On-screen style (`dpi-osd-style`) | **Solaar overlay** (default), **Desktop OSD** (KDE Plasma's own popup, like the volume one), **Notification** |
| On-screen position (`dpi-osd-position`) | Top Left, Top, Top Right, Left, Center, Right, Bottom Left, Bottom (default), Bottom Right |
| On-screen time (`dpi-osd-duration`) | 0.5 to 5 seconds (default 1.5) |
| On-screen size (`dpi-osd-size`) | Small, Medium (default), Large |

Position, time and size are for the Solaar overlay, and are greyed out for the other styles.
The overlay appears on the primary screen, stays above other windows and lets clicks through.
Under Wayland it is drawn through XWayland, because a Wayland window can't choose where it goes.

    solaar config "G502 X PLUS" dpi-osd-position "Top Right"
    solaar config "G502 X PLUS" dpi-osd-style "Desktop OSD"

### Lighting
- **LED Control keeps the onboard profile on.** Taking over the lighting used to switch the device to
  host mode every time it connected, which turned off the onboard profile and its button mapping.
  When Onboard Profiles is set to a profile, the device now stays in it.
  (While a profile is active, the device may show the profile's lighting rather than Solaar's.)
- **Idle lighting**: a *When not in use* choice (Always on, Dim when idle, Dim then off,
  Off when idle) sets *Idle after*, *When idle* and *Lights off after* together.
  - Lights off now also works with *Idle after* set to Never.
  - The *Disabled* choice of the idle timeouts is now called *Never*. Rules or commands that use
    the old name need updating.

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

- **Apply theme rule action**: rules can switch per-key themes, e.g. on a key press.
  Pick *Apply theme* under Action in the Rule Editor, or in `rules.yaml`:

      - Rule:
        - Key: [Play/Pause, pressed]
        - ApplyTheme: [G915 X LS TKL, Windows]   # or just `ApplyTheme: Windows` for the triggering device

- Undo/redo, readable key labels, and TKL keyboard layout detection.
- A G915 X LIGHTSPEED TKL layout that includes its top bar (logo, brightness and media keys).
- Brush, Rect and Fill tools are labeled, with a hint describing what the active tool will do.

### Main window
- Settings are in collapsible groups: Pointer and Scrolling, Buttons and Keys, Lighting, Audio,
  Device and Other. Folded groups are remembered per device.
- Settings are editable straight away. The old three-state lock icon is now a small menu at the
  end of each row with Editable, Locked and Ignored. Only locked and ignored rows show an icon.
- Rule Editor, About and Quit are in a header bar instead of a row of buttons at the bottom.
- Battery, link and light level sit on one line, and the device list is narrower.
- The scrollbar no longer covers the controls at the right-hand edge.

### Fixes
- A query like `solaar config <device> per-key-lighting <KEY>` no longer wipes every saved key color.
  A config already damaged this way no longer breaks the editor or LED Control at startup.
- Per-key zone 69 is named PAUSE (Pause/Break) and zone 155 PLAY/PAUSE (the media key).
  Previously they were PASTE and PAUSE.

### Development
- `make dev_venv` builds a local `.venv` that reuses the system GTK bindings and has the test and lint tools.
  `make dev_test` and `make dev_lint` run pytest and ruff from it.
- To run an installed Solaar straight from a checkout, install it as editable into its pipx venv
  without rebuilding the GTK bindings, then restart Solaar after changing the code:

      ~/.local/share/pipx/venvs/solaar/bin/python -m pip install --no-deps --editable .


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
