# Shell Runtime Inventory

Last update: 2026-08-29
Status: Active Dock and Taskbar executable boundaries owned

## Ownership matrix

| Layout | Active runtime | Position | Dormant inherited settings |
|---|---|---|---|
| BigGnome | Unified runtime -> owned Dock | bottom | none |
| G-Unity | Unified runtime -> owned Dock | left | none |
| Hybrid | Unified runtime -> owned Taskbar | bottom | Dash to Dock snapshot, not enabled |
| Desk UX | Unified runtime -> owned Taskbar | bottom | Dash to Dock snapshot, not enabled |
| Classic | Unified runtime -> owned Taskbar | bottom | Dash to Dock snapshot, not enabled |
| Minimal | Unified runtime -> native GNOME panel only | top | Dash to Dock snapshot, not enabled |

The dormant Dash to Dock sections are migration debt. They must not be treated
as runtime requirements when the focused schema is introduced.

## Source baseline

| Component | Installed size | JS/CSS lines | Active layouts |
|---|---:|---:|---|
| Community Dock | 920 KiB | 15,761 | BigGnome, G-Unity |
| Community Panel | 1.6 MiB | 16,955 | Hybrid, Desk UX, Classic |
| Combined | 2,339,654 bytes | 32,716 | five layouts |

Current installed payload:

| Component | Current bytes | Current JS/CSS lines |
|---|---:|---:|
| Unified runtime with Dock and Taskbar | 965,865 | 29,153 |
| Dock resources and schemas | 176,013 | 1,713 CSS |
| Community Panel rollback/resources | 1,145,880 | 11,018 |
| Combined | 2,287,758 | 41,884 |

The runtime reads the owned schema, maps all six layout profiles, and selects
Dock, Taskbar, or native GNOME behavior. Dock and Taskbar actors, lifecycle,
and active executable modules are owned by this runtime. Community Panel is a
dormant rollback and resource host. The old Community Dock path is not an
extension and contains no executable JavaScript.

Build 76 accepts stable, testing, intermediate-UUID, downgrade/re-upgrade,
logout/login, and reboot paths on GNOME 50/51. Helper build 69 owns the
extension-order protection required while replacing a live legacy Panel. A
clean package install and fresh session pass on GNOME 50. One
testing-repository cycle still gates removal of dormant rollback sources and
schema adapters.

Preferences-only payload removed:

- Dock: `prefs.js` (48 KiB) and `Settings.ui` (168 KiB).
- Panel: `prefs.js` (132 KiB) and `ui/` (200 KiB).
- Panel `img/` is mixed: stacked-app assets are runtime; donation and upstream
  branding assets are preferences/update-notification candidates.

## Module inventory

### Unified Dock runtime

Runtime entry and orchestration:

- `dockRuntime.js`, `dockSurface.js`, `dockActorFactory.js`, `dock/dash.js`.
- `startupOverviewIntegration.js` owns per-layout login Overview policy.
- `shellPopoverThemeIntegration.js` owns light Quick Settings, date/calendar,
  and notification policy with exact cleanup; Minimal stays native dark.
- `taskbarOverviewIntegration.js` owns Taskbar Overview behavior.
- `taskbarStatusFullscreenIntegration.js` owns status/fullscreen behavior.

Application behavior:

- `dock/appIcons.js`, `dock/appIconIndicators.js`.
- `dock/windowPreview.js`.

Visibility and appearance:

- `dock/intellihide.js`, `dock/theming.js`.
- Resource-host `stylesheet.css`.

Integration and compatibility:

- `dock/dbusmenuUtils.js`, shared runtime `desktopIconsUsableArea.js`.
- `dock/fileManager1API.js`, `dock/launcherAPI.js`, `dock/locations.js`.
- `dock/locationsWorker.js`, `dock/utils.js`, `dock/dependencies/`.

Removed standalone payload:

- `extension.js`, `metadata.json`, `prefs.js`, and `Settings.ui`.

### Community Panel

The active copies of the modules below are internalized under the unified
runtime's `taskbar/` directory. Community Panel retains identical dormant
copies only for the upgrade/rollback gate.

Runtime entry and orchestration:

- `extension.js`, `panelManager.js`, `panel.js`, `taskbar.js`.
- `panelSettings.js`, `panelPositions.js`.

Application behavior:

- `appIcons.js`, `windowPreview.js`.
- The DING bridge moved to the unified runtime in build 71. Notification
  monitoring moved in build 72. Overview behavior moved in build 73; the
  inherited module was removed after GNOME 50/51 acceptance.

Visibility and appearance:

- `intellihide.js`, `proximity.js`, `transparency.js`.
- `stylesheet.css`. The inherited `panelStyle.js` was removed in build 74.

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
| Applications menu side | right | layout | n/a | n/a | n/a | n/a |
| Open desktop after login | off | off | on | on | on | off |

## First safe removal slice

- [x] Disable the Dock Show Applications preferences menu.
- [x] Remove Dash to Panel settings from the Panel context menu.
- [x] Remove taskbar locking from the Panel context menu.
- [ ] Validate this slice live on GNOME 50.
- [x] Remove preferences files after local package staging validation.
