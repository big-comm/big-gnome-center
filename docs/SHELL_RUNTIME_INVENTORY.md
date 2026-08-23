# Shell Runtime Inventory

Last update: 2026-08-22
Status: static inventory and passive unified runtime foundation complete

## Ownership matrix

| Layout | Active runtime | Position | Dormant inherited settings |
|---|---|---|---|
| BigGnome | Community Dock + native panel controller | bottom | none |
| G-Unity | Community Dock + native panel controller | left | none |
| Hybrid | Community Panel | bottom | Dash to Dock snapshot, not enabled |
| Desk UX | Community Panel | bottom | Dash to Dock snapshot, not enabled |
| Classic | Community Panel | bottom | Dash to Dock snapshot, not enabled |
| Minimal | native GNOME panel only | top | Dash to Dock snapshot, not enabled |

The dormant Dash to Dock sections are migration debt. They must not be treated
as runtime requirements when the focused schema is introduced.

## Source baseline

| Component | Installed size | JS/CSS lines | Active layouts |
|---|---:|---:|---|
| Community Dock | 920 KiB | 15,761 | BigGnome, G-Unity |
| Community Panel | 1.6 MiB | 16,955 | Hybrid, Desk UX, Classic |
| Combined | 2,339,654 bytes | 32,716 | five layouts |

Phase 1 checkpoint after removing independent preferences:

| Component | Current bytes | Current JS/CSS lines |
|---|---:|---:|
| Community Dock | 628,811 | 14,545 |
| Community Panel | 1,201,954 | 12,857 |
| Combined | 1,830,765 | 27,402 |

This first cleanup removes 508,889 bytes and 5,314 JS/CSS lines without
removing runtime features.

Passive unified runtime checkpoint:

| Component | Current bytes | JavaScript lines | Actor ownership |
|---|---:|---:|---|
| Layout Switcher Shell Runtime | 23,406 | 166 | none (extraction gate) |

The new runtime reads the owned schema and maps all six layout profiles, but
an explicit passive gate prevents it from creating actors. Community Dock and
Community Panel remain authoritative until their individual approval gates.

Preferences-only payload removed:

- Dock: `prefs.js` (48 KiB) and `Settings.ui` (168 KiB).
- Panel: `prefs.js` (132 KiB) and `ui/` (200 KiB).
- Panel `img/` is mixed: stacked-app assets are runtime; donation and upstream
  branding assets are preferences/update-notification candidates.

## Module inventory

### Community Dock

Runtime entry and orchestration:

- `extension.js`, `docking.js`, `dash.js`, `imports.js`.
- `indicatorController.js`, `panelController.js`.

Application behavior:

- `appIcons.js`, `appIconIndicators.js`, `appIconsDecorator.js`.
- `appSpread.js`, `windowPreview.js`, `notificationsMonitor.js`.

Visibility and appearance:

- `intellihide.js`, `theming.js`, `stylesheet.css`.

Integration and compatibility:

- `dbusmenuUtils.js`, `desktopIconsIntegration.js`, `fileManager1API.js`.
- `launcherAPI.js`, `locations.js`, `locationsWorker.js`, `utils.js`.
- `dependencies/gi.js`, `dependencies/shell/extensions/extension.js`.
- `dependencies/shell/misc.js`, `dependencies/shell/ui.js`.

Removed preferences-only payload:

- `prefs.js`, `Settings.ui`.

### Community Panel

Runtime entry and orchestration:

- `extension.js`, `panelManager.js`, `panel.js`, `taskbar.js`.
- `panelSettings.js`, `panelPositions.js`.

Application behavior:

- `appIcons.js`, `windowPreview.js`, `notificationsMonitor.js`.
- `overview.js`, `desktopIconsIntegration.js`.

Visibility and appearance:

- `intellihide.js`, `proximity.js`, `transparency.js`.
- `panelStyle.js`, `stylesheet.css`.

Shared support:

- `utils.js`.

Removed preferences-only payload:

- `prefs.js` and every file under `ui/`.

## Layout setting inventory

The canonical key/value inventory is stored in the named GSettings sections of
the layout snapshots. Counts below make accidental additions or removals
visible during extraction.

| Layout | Active component section | Active keys | Dormant Dock keys |
|---|---|---:|---:|
| BigGnome | `dash-to-dock` | 24 | 0 |
| G-Unity | `dash-to-dock` | 31 | 0 |
| Hybrid | `dash-to-panel` | 99 | 15 |
| Desk UX | `dash-to-panel` | 46 | 30 |
| Classic | `dash-to-panel` | 101 | 15 |
| Minimal | none | 0 | 31 |

Canonical sources:

- `usr/share/layout-switcher/layouts/biggnome.txt`
- `usr/share/layout-switcher/layouts/g-unity.txt`
- `usr/share/layout-switcher/layouts/hybrid.txt`
- `usr/share/layout-switcher/layouts/desk-ux.txt`
- `usr/share/layout-switcher/layouts/classic.txt`
- `usr/share/layout-switcher/layouts/minimal.txt`

The extraction must copy only keys proven to affect an active contract. A key
present in a dormant section is not evidence of use.

## Behavior matrix

| Contract | BigGnome | G-Unity | Hybrid | Desk UX | Classic | Minimal |
|---|---|---|---|---|---|---|
| Launch/focus/minimize | Dock | Dock | Taskbar | Taskbar | Taskbar | GNOME |
| Favorites/running apps | yes | yes | yes | yes | yes | GNOME |
| Multiple-window preview | yes | yes | yes | yes | yes | GNOME |
| Notification badges | yes | yes | yes | yes | yes | GNOME |
| Running indicator | dot | dot | Hybrid | Desk UX | none | none |
| Auto/intelligent hiding | Dock | Dock | Panel | Panel | Panel | none |
| System status/clock | native top | native top | bottom | bottom | bottom | native top |
| App labels | no | no | no | no | yes | no |
| Desktop icons default | off | off | on | off | on | off |

## First safe removal slice

- [x] Disable the Dock Show Applications preferences menu.
- [x] Remove Dash to Panel settings from the Panel context menu.
- [x] Remove taskbar locking from the Panel context menu.
- [ ] Validate this slice live on GNOME 50.
- [x] Remove preferences files after local package staging validation.
