# Community Panel upstream

Community Panel is the bundled Layout Switcher fork of Dash to Panel 73.

- Upstream: https://github.com/home-sweet-gnome/dash-to-panel
- Baseline: Arch/Manjaro package `gnome-shell-extension-dash-to-panel` 73-1
- Upstream UUID: `dash-to-panel@jderose9.github.com`
- Fork UUID: `community-panel@communitybig.org`
- License: GPL-2.0-or-later
- Original authors: Jason DeRose and Charles Gagnon

The fork initially preserves upstream runtime files and the inherited
`org.gnome.shell.extensions.dash-to-panel` settings schema. This keeps the
Classic, Hybrid, and Desk UX profiles byte-for-byte compatible at the settings
level while the external extension remains available as migration rollback.

Local runtime changes:

- Desk UX indicators use the same fixed geometry as Community Dock: 8 x 3 px
  when unfocused and 18 x 3 px when focused.
- `PanelManager` delegates physical panel creation and release to the unified
  runtime host.
- The primary `Panel` delegates native status-area adoption and restoration to
  the unified runtime host. Native Shell actors and its menu manager remain
  authoritative.
- `PanelManager` delegates monitor selection, topology signals, and serialized
  panel resets to the unified runtime monitor host.
- Shell prototype/global hook installation and exact restoration belong to the
  unified runtime hook host. Inherited behavior callbacks remain unchanged.
- Overview, notification-monitor, desktop usable-area, manager-signal, and
  intellihide-keybinding lifecycle belongs to the unified runtime service host.
- Build 71 ports the official DING usable-area protocol into the unified
  runtime and removes the two dormant inherited implementations. The original
  1-clause BSD attribution is preserved in the owned source.
- Build 72 ports notification aggregation, focus clearing, launcher signals,
  and Unity D-Bus ownership into the unified runtime. The dormant inherited
  notification monitor is removed after GNOME 50/51 acceptance.
- Build 73 ports Overview allocation, dash visibility, workspace isolation,
  hotkeys/previews, and click-to-exit behavior into the unified runtime. The
  inherited Overview module is removed after GNOME 50/51 acceptance.
- Build 74 ports native status styling, Overview/fullscreen visibility,
  tracked-chrome mutations, and guarded Wayland fullscreen surface repair into
  the unified runtime. The inherited Panel style module is removed after
  GNOME 50/51 acceptance.

GNOME 50 and GNOME 51 are live acceptance targets.
