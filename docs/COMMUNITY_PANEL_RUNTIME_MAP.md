# Community Panel Runtime Map

Last update: 2026-08-27
Baseline: `6e77d2d`, runtime build 68

## Scope

Map the inherited Community Panel modules still loaded by the unified runtime.
The standalone `extension.js` is a rollback adapter and is not the active
lifecycle owner. `TaskbarSurfaceManager` constructs `PanelManager` directly.

## Active import graph

```text
taskbarSurface.js
  -> panelManager.js
     -> panel.js
        -> taskbar.js
           -> appIcons.js
           -> windowPreview.js
        -> intellihide.js
           -> proximity.js
        -> transparency.js
        -> panelStyle.js
        -> panelSettings.js
        -> panelPositions.js
     -> overview.js
     -> notificationsMonitor.js
     -> desktopIconsIntegration.js
     -> runtimeContext.js
     -> utils.js
```

## Ownership map

| Module | Live responsibility | Current owner | Migration action |
|---|---|---|---|
| `panelManager.js` | Shell injections and monitor lifecycle | mixed | physical lifecycle delegated to owned host |
| `panel.js` | allocation and inherited styling | mixed | native status lifecycle delegated to owned host |
| `taskbar.js` | application actor layout and inherited adapters | mixed | retain until host accepted |
| `appIcons.js` | application actors and renderer hooks | mixed | owned policies already injected |
| `windowPreview.js` | preview renderer | inherited | retain behind owned interactions |
| `intellihide.js` | overlap and reveal renderer | mixed | owned mode selection already active |
| `transparency.js` | effective Panel alpha | inherited | owned opacity is the source of truth |
| `panelStyle.js` | native box and status actor styling | inherited | retain until status host accepted |
| `overview.js` | Taskbar/overview integration | inherited | audit before removal |
| `proximity.js` | window overlap watches | inherited | retain with intellihide |
| `notificationsMonitor.js` | application notification counts | inherited | audit against owned app model |
| `desktopIconsIntegration.js` | desktop usable-area bridge | inherited | remove if inactive for accepted layouts |
| `panelSettings.js` | renderer settings and monitor maps | adapter | remove after upgrade matrix |
| `panelPositions.js` | renderer position constants | adapter | replace with layout profiles |
| `runtimeContext.js` | compatibility dependency injection | adapter | remove last |
| `utils.js` | shared Shell helpers | inherited | split only with each consumer |
| `extension.js` | standalone compatibility entry point | inactive | retain for rollback cycle |

## Native status-area boundary

GNOME Shell owns `Main.panel`, `statusArea`, its three boxes, every native
indicator, and the shared popup-menu manager. The focused runtime may adopt and
position existing containers, but must not recreate or destroy them.

Runtime build 68 delegates the narrow physical and native-status lifecycle
through two reviewed bridges in the inherited renderer:

1. `TaskbarPanelHost` owns the detach, chrome tracking, physical wrapper, and
   restoration of `Main.panel`;
2. `TaskbarStatusAreaHost` owns existing Activities, Date Menu, and Quick
   Settings containers without recreating them;
3. actor restoration state stays in the runtime, never on Shell actors;
4. the native popup-menu manager remains unchanged;
5. creation failure and manager teardown both restore the native host.

Telemetry reports host generation and count, adopted and orphan roles, menu
state, native clock and Quick Settings state, and transformed actor geometry.

## Upstream reference

- GNOME Shell 50.4 `js/ui/panel.js`, tag target
  `233322b9b675b0385767147c1a6cfc6ff7325160`.
- GNOME Shell main `js/ui/panel.js`, retrieved 2026-08-27.
- Dash-to-Panel master `src/panel.js` and `src/panelManager.js`, retrieved
  2026-08-27. The bundled copies differ only by the accepted local runtime
  compatibility patches.

GNOME 50.4 and current main retain the same central contracts used here:
`Main.panel.statusArea`, `addToStatusArea()`, `_addToPanelBox()`, the left,
center, and right boxes, and one `PopupMenuManager` owned by `Main.panel`.
