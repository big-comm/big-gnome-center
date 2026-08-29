# Community Panel Runtime Map

Last update: 2026-08-28
Baseline: `d22f8de`, runtime build 76

## Scope

Map the internalized Community Panel renderer modules loaded by the unified
runtime. The standalone Community Panel `extension.js` and matching source
copies are dormant rollback assets. `TaskbarSurfaceManager` constructs the
runtime-owned `taskbar/panelManager.js` directly.

Per-layout login Overview policy is also runtime-owned. The Taskbar renderer no
longer reads or mutates its inherited startup-Overview key.

## Active import graph

```text
runtimeController.js
  -> startupOverviewIntegration.js
taskbarSurface.js
  -> taskbarPanelHost.js
  -> taskbarStatusAreaHost.js
  -> taskbarMonitorHost.js
  -> taskbarShellHooks.js
  -> taskbarStatusFullscreenIntegration.js
  -> taskbarServiceHost.js
     -> taskbarOverviewIntegration.js
     -> taskbarNotificationMonitor.js
     -> runtime/desktopIconsUsableArea.js
  -> taskbar/panelManager.js
     -> taskbar/panel.js
        -> taskbar/taskbar.js
           -> taskbar/appIcons.js
           -> taskbar/windowPreview.js
        -> taskbar/intellihide.js
           -> taskbar/proximity.js
        -> taskbar/transparency.js
        -> taskbar/panelSettings.js
        -> taskbar/panelPositions.js
     -> taskbar/runtimeContext.js
     -> taskbar/utils.js
```

## Ownership map

| Module | Live responsibility | Current owner | Migration action |
|---|---|---|---|
| `taskbar/panelManager.js` | behavior callbacks and service coordination | runtime | internalized in build 75 |
| `taskbar/panel.js` | allocation and inherited styling | runtime | internalized in build 75 |
| `taskbar/taskbar.js` | application actor layout and adapters | runtime | internalized in build 75 |
| `taskbar/appIcons.js` | application actors and renderer hooks | runtime | internalized in build 75 |
| `taskbar/windowPreview.js` | preview renderer | runtime | internalized in build 75 |
| `taskbar/intellihide.js` | overlap and reveal renderer | runtime | internalized in build 75 |
| `taskbar/transparency.js` | effective Panel alpha | runtime | internalized in build 75 |
| `taskbarStatusFullscreenIntegration.js` | native status styling and fullscreen tracking | runtime | owned implementation accepted in build 74 |
| `taskbarOverviewIntegration.js` | Taskbar/overview integration | runtime | owned implementation accepted in build 73 |
| `taskbar/proximity.js` | window overlap watches | runtime | internalized in build 75 |
| `taskbarNotificationMonitor.js` | application notification counts | runtime | owned implementation accepted in build 72 |
| `startupOverviewIntegration.js` | per-layout login Overview policy | runtime | owned post-migration option |
| `desktopIconsIntegration.js` | removed in build 71 | runtime | shared owned implementation replaces both copies |
| `taskbar/panelSettings.js` | renderer settings and monitor maps | runtime adapter | remove after upgrade matrix |
| `taskbar/panelPositions.js` | renderer position constants | runtime adapter | replace with layout profiles |
| `taskbar/runtimeContext.js` | renderer dependency injection | runtime adapter | remove last |
| `taskbar/utils.js` | shared Shell helpers | runtime | split only with each consumer |
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
4. `PanelManager` retains accepted renderer callbacks while owned hosts control
   Overview, desktop-icon service, manager signals, and keybindings.

Telemetry reports topology generations, monitor coverage, reset failures, the
installed hook set, injection ownership, shutdown connection, pending
restoration, and restoration conflicts.

## Manager-service boundary

Runtime build 70 adds `TaskbarServiceHost` as the lifecycle owner for services
previously constructed directly by `PanelManager`:

1. Overview construction and activation after primary-panel creation;
2. notification monitor, launcher subscription, and Unity D-Bus name;
3. DING usable-area bridge with exact per-monitor margins;
4. six root settings groups and three panel-box signal groups;
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

## Overview boundary

Runtime build 73 ports the Taskbar Overview behavior into
`TaskbarOverviewIntegration`. It owns dash visibility, Overview allocation,
optional workspace isolation, number hotkeys and previews, and empty-space
exit. Signals, timeouts, keybindings, and exact property descriptors are
restored transactionally; an external replacement is reported instead of
overwritten.

Telemetry reports implementation, activation, signals, hooks, suppressed
native bindings, Overview/search/app-grid state, restoration conflicts,
entry/exit/state counters, pending previews/timeouts, and actor residue. The
inherited `overview.js` was removed after GNOME 50.4 and GNOME 51.beta passed
normal/maximized search, app-grid, activation, workspace, empty-space exit,
10 slow and 20 rapid cycles, native restoration, Taskbar re-entry, and strict
audit.

## Status and fullscreen boundary

Runtime build 74 ports native status styling, Overview panel visibility,
fullscreen chrome tracking, and intellihide tracking into
`TaskbarStatusFullscreenIntegration`. Exact inline styles and tracked-chrome
flags are restored transactionally. The guarded Wayland surface repair uses
the same exact-geometry boundary accepted by the owned Dock.

Telemetry reports implementation, connections, panels and styles owned,
restoration conflicts, Overview/fullscreen counters, native visibility,
tracking mutations, pending repair, surface readiness, and repair count.
`panelStyle.js` was removed only after GNOME 50.4 and GNOME 51.beta passed the
status, F11, teardown, Taskbar re-entry, and strict-audit matrices.

Build 75 closes the active executable boundary. All 13 Taskbar renderer modules
are internal to the unified runtime, and strict audit identifies the runtime
implementation and exact module count. The dormant standalone compatibility
host and schema/resource adapters remain until upgrade/rollback coverage passes.

Build 76 accepts stable, testing, intermediate Community UUID,
downgrade/re-upgrade, logout/login, and reboot migration paths on GNOME 50/51.
Helper build 69 protects its live migration call from Shell extension-order
rebase. A clean package install passes on GNOME 50. One testing-repository
cycle still gates compatibility removal.

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
- Overview review: GNOME Shell 50.4 target
  `233322b9b675b0385767147c1a6cfc6ff7325160`, GNOME Shell main
  `6db7eaf5377e24d85eb9251316a8b2b5ca407cc4`, and Dash-to-Panel master
  `1c0c1f1354bfaccbf2539ef516ec527bea498a51`, retrieved 2026-08-28.
  Reviewed Overview SHA-256 values: GNOME 50.4/current `overview.js`
  `1fb938b6899669121d93a5b01d623003db85753551ff3941251d784f0c9394f5`;
  GNOME 50.4 `overviewControls.js`
  `75c152027190ec9b8ff56e55532c04982f6928dfb8c2979b4d384f9344f9affe`;
  current `overviewControls.js`
  `d798a47c66d0f33c04d18b1bdae5ac5a3d7fa7149c5afd9da40799d43f62b0a2`;
  Dash-to-Panel `overview.js`
  `fa388cb1600037fe6347808a087184596e345eb3d382274fbcee71ade2480048`.
  Official GJS Extension/`InjectionManager` and review lifecycle guidance was
  also reviewed. No public API replaces these private Shell contracts.
- Status/fullscreen review: GNOME Shell 50.4 target
  `233322b9b675b0385767147c1a6cfc6ff7325160`, Shell main
  `6db7eaf5377e24d85eb9251316a8b2b5ca407cc4`, and Dash-to-Panel master
  `1c0c1f1354bfaccbf2539ef516ec527bea498a51`, retrieved 2026-08-28.
  GNOME `layout.js` SHA-256 values are
  `79b73a5a1390c9d6871c96ec18115bb1316747c321c2a157bc837f3a04bc6f12`
  and
  `a7dba213a2946830024610ac696996ae5d866deabc64ae590d474713b4d17fb7`.
  Dash-to-Panel `intellihide.js`, `panel.js`, and `panelStyle.js` values are
  `1789c9f93fa76ad8046c42b9a31a556b2f96296a86f87b2807047d1bcfa8ed04`,
  `f1b771a838802bddcd82b2e8e2ce0e3b7af30c40f829c7e68805e49e2fe691a8`,
  and
  `b72f2953f0b973a870bd239b4825ff6e1ccf9bde9bc0e7fbc8569948b3a5c201`.
  No public API replaces `trackFullscreen` or native status inline styles.

GNOME 50.4 and current main retain the same central contracts used here:
`Main.panel.statusArea`, `addToStatusArea()`, `_addToPanelBox()`, the left,
center, and right boxes, and one `PopupMenuManager` owned by `Main.panel`.
