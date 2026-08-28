# Community Panel Runtime Map

Last update: 2026-08-28
Baseline: `4f636df`, runtime build 72

## Scope

Map the inherited Community Panel modules still loaded by the unified runtime.
The standalone `extension.js` is a rollback adapter and is not the active
lifecycle owner. `TaskbarSurfaceManager` constructs `PanelManager` directly.

## Active import graph

```text
taskbarSurface.js
  -> taskbarPanelHost.js
  -> taskbarStatusAreaHost.js
  -> taskbarMonitorHost.js
  -> taskbarShellHooks.js
  -> taskbarServiceHost.js
     -> overview.js
     -> taskbarNotificationMonitor.js
     -> runtime/desktopIconsUsableArea.js
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
     -> runtimeContext.js
     -> utils.js
```

## Ownership map

| Module | Live responsibility | Current owner | Migration action |
|---|---|---|---|
| `panelManager.js` | behavior callbacks and service coordination | mixed | service lifecycle delegated to owned hosts |
| `panel.js` | allocation and inherited styling | mixed | native status lifecycle delegated to owned host |
| `taskbar.js` | application actor layout and inherited adapters | mixed | retain until host accepted |
| `appIcons.js` | application actors and renderer hooks | mixed | owned policies already injected |
| `windowPreview.js` | preview renderer | inherited | retain behind owned interactions |
| `intellihide.js` | overlap and reveal renderer | mixed | owned mode selection already active |
| `transparency.js` | effective Panel alpha | inherited | owned opacity is the source of truth |
| `panelStyle.js` | native box and status actor styling | inherited | retain until status host accepted |
| `overview.js` | Taskbar/overview integration | inherited | lifecycle owned by service host; replace behavior separately |
| `proximity.js` | window overlap watches | inherited | retain with intellihide |
| `taskbarNotificationMonitor.js` | application notification counts | runtime | owned implementation accepted in build 72 |
| `desktopIconsIntegration.js` | removed in build 71 | runtime | shared owned implementation replaces both copies |
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

## Monitor and Shell-hook boundary

Runtime build 69 adds two more narrow lifecycle owners:

1. `TaskbarMonitorHost` selects primary/secondary monitors, creates the panel
   set through the physical host, owns topology settings and
   `monitors-changed`, and serializes resets with stale-generation rejection;
2. `TaskbarShellHooks` installs the inherited AppDisplay, layout, overview,
   BoxPointer, workspace-indicator, Looking Glass, message-tray, native-panel,
   and shutdown hooks;
3. hook restoration uses exact saved property descriptors and never overwrites
   a property replaced by another extension after activation;
4. `PanelManager` retains the accepted behavior callbacks, desktop-icon
   service, overview integration, signals, and keybindings.

Telemetry reports topology generations, monitor coverage, reset failures, the
installed hook set, injection ownership, shutdown connection, pending
restoration, and restoration conflicts.

## Manager-service boundary

Runtime build 70 adds `TaskbarServiceHost` as the lifecycle owner for services
previously constructed directly by `PanelManager`:

1. inherited Overview construction and activation after primary-panel creation;
2. notification monitor, launcher subscription, and Unity D-Bus name;
3. DING usable-area bridge with exact per-monitor margins;
4. four root settings groups and three panel-box signal groups;
5. the inherited intellihide toggle keybinding;
6. pending DING idle cancellation and transactional partial cleanup.

Compatibility properties remain on `PanelManager` only for inherited behavior
callbacks and are cleared only while still owned. Telemetry reports
service generations, ownership and activation, subscription and bus ownership,
notification application count, exact desktop margins, pending work, signal
groups, keybinding ownership, failures, and last error.

## Desktop usable-area boundary

Runtime build 71 ports the DING protocol into one shared runtime module. Dock
and Taskbar use stable owner UUIDs, preserve the official 100 ms coalescing and
`setMarginsForExtension()` contract, reconnect on DING state changes, and expose
connection, pending-dispatch, recipient, and dispatch-count telemetry. The two
dormant inherited implementations were removed after GNOME 50 and GNOME 51
accepted exact one-monitor margins, 38/56 px updates, and repeated Dock/Taskbar
transitions.

## Notification boundary

Runtime build 72 ports the notification implementation behind the existing
service lifecycle. The owned monitor aggregates every live message-tray source
per desktop application, merges tray and Unity launcher counts, clears urgency
when the application gains focus, and owns both the launcher subscription and
`com.canonical.Unity` bus name. Construction and teardown are transactional.

Telemetry reports connection and D-Bus ownership, tracked source/state counts,
total notifications, urgent desktop IDs, update count, and last updated app.
Strict audit rejects inherited ownership, disconnected signals, invalid totals,
incoherent application counts, or application/runtime layout-state drift. The
inherited monitor was removed only after
GNOME 50 and GNOME 51 accepted real notifications, focus clearing, 10 slow and
20 rapid cycles, exact teardown/re-entry, and zero strict-audit failures.

## Upstream reference

- GNOME Shell 50.4 `js/ui/panel.js`, tag target
  `233322b9b675b0385767147c1a6cfc6ff7325160`.
- GNOME Shell main `js/ui/panel.js`, retrieved 2026-08-27.
- Dash-to-Panel master `src/panel.js` and `src/panelManager.js`, retrieved
  2026-08-27, plus `src/notificationsMonitor.js`, retrieved 2026-08-28. Current
  upstream still owns these integrations through private
  Shell overrides and explicit teardown; it exposes no newer public GNOME API.
  The bundled copy delegates their lifecycle to the runtime hosts while
  retaining the accepted upstream callbacks.

GNOME 50.4 and current main retain the same central contracts used here:
`Main.panel.statusArea`, `addToStatusArea()`, `_addToPanelBox()`, the left,
center, and right boxes, and one `PopupMenuManager` owned by `Main.panel`.
