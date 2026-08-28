# Shell Runtime Remaining Work

Last update: 2026-08-27
Safe checkpoint: `70212c9`
Status: Build 71 owns the shared DING usable-area implementation

## Purpose

Track only the work that remains after the accepted GNOME 50 checkpoint. The
goal is a smaller Layout Switcher-owned Shell runtime without changing the six
approved layouts or exposing upstream Dock and Panel complexity to users.

This report is the execution checklist. The longer migration document keeps the
architecture, product rules, and historical decisions.

## What the rollback preserved

The documentation was not reset to an older version. The failed direct Dock
lifecycle extraction was reverted in code and recorded as a rejected approach.
The current source deliberately stops at the last safe boundary:

- `layout-switcher-runtime@communitybig.org` is the only visual runtime UUID
  enabled by layout files;
- the unified controller selects Dock, Taskbar, or native GNOME per layout;
- Community Dock is retired as an extension; Community Panel is disabled as a
  standalone extension;
- the accepted Panel/Taskbar engine remains imported internally as a rollback
  module;
- Dock construction, lifecycle, and executable modules belong to the unified
  runtime;
- independent Dock and Panel preference screens are removed;
- supported controls and per-layout defaults belong to Layout Switcher;
- external Dash to Dock and Dash to Panel packages are not package dependencies
  and are not modified or uninstalled from user systems.

The first direct Dock lifecycle attempt was rejected because teardown callbacks
outlived cleared extension settings. The accepted implementation gives the
unified runtime exact construction and reverse-order teardown ownership.

## Current architecture

```text
Layout Switcher GTK app
  -> owned runtime schema and per-layout overrides
  -> helper extension for safe switch orchestration
  -> unified Shell runtime UUID
       -> owned Dock runtime for BigGnome and G-Unity
       -> owned Taskbar physical/status/topology/hook hosts with inherited
          visual modules for Hybrid, Desk UX, and Classic
       -> native GNOME surface for Minimal
```

Current internal payload:

| Module | Bytes | JS/CSS lines | Public UUID enabled |
|---|---:|---:|---|
| Unified runtime with Dock and Taskbar lifecycle | 581,690 | 16,557 | yes |
| Dock resource host | 176,013 | 1,713 CSS | no entry point |
| Inherited Taskbar visual modules | 1,186,762 | 12,352 | rollback adapter only |
| Total | 1,944,465 | 30,622 | one public runtime |

The size target is not a fixed percentage. Removal is allowed only when a
replacement passes the relevant behavior contract.

## Accepted layout contracts

| Layout | Surface | Position | Indicator default | Special behavior |
|---|---|---|---|---|
| BigGnome | Dock + native top panel | bottom | Desk UX | compact dock |
| G-Unity | Dock + native top panel | left | dot | Unity-style placement |
| Hybrid | Taskbar/panel | bottom | Hybrid | icon lift enabled by default |
| Desk UX | Taskbar/panel | bottom | Desk UX | size changes by focus state |
| Classic | Labeled taskbar/panel | bottom | none | application labels |
| Minimal | Native GNOME panel | top | none | no Dock/Taskbar controls |

Light/dark mode is global user state. Switching layouts must preserve it. Icon
theme, AppIndicator actors, labels, menu styling, and Shell styling must follow
the final effective mode without stale caches.

## Required work

### 0. Freeze the accepted baseline

- [x] Record GNOME 50 screenshots for all six layouts in light and dark mode.
- [x] Record GNOME 51 screenshots for all six layouts in light and dark mode.
- [x] Record dimensions for panel height, dock size, indicator geometry, and
  icon spacing.
- [x] Add transition coverage for every source/target surface pair:
  Dock-to-Dock, Dock-to-Taskbar, Taskbar-to-Dock, Taskbar-to-Taskbar, and
  native-to/from managed surfaces.
- [x] Add a read-only live audit for schemas, enabled UUIDs, extension state,
  Shell D-Bus availability, session type, theme state, and internal payload.
- [x] Extend the live audit with actor-level surface and duplicate-actor checks.
- [x] Store local-to-VM checksum verification with every deployment.

Gate: no extraction begins until the reference matrix is captured and the user
accepts it as the visual source of truth.

Evidence: [`baselines/README.md`](baselines/README.md). Both clean Wayland
sessions passed 12 reference states and all eight surface-transition directions.

### 1. Extract the Dock engine incrementally

- [x] Isolate lifecycle ownership without constructing the inherited
  `DockManager` directly from the controller.
- [x] Port primary launch, focus, minimize, and multiple-window actions.
- [x] Port favorite and running-app data ownership and stable ordering.
- [x] Port notification monitor and badge-count ownership.
- [x] Port core application context-menu action ownership.
- [x] Port notification badge actor and text ownership.
- [x] Remove the replaced inherited notification-monitor and
  indicator-controller branches.
- [x] Port the native top-panel appearance and visibility controller used by
  Dock layouts, then remove its inherited branch.
- [x] Port favorites, running applications, launch, focus, minimize, and
  multiple-window behavior.
- [x] Port remaining application context-menu construction.
- [x] Port the three accepted running indicators.
- [x] Port standard and soft-lift hover behavior without hover rectangles.
- [x] Port always visible, always hidden, and intelligent hiding.
- [x] Port bottom placement for BigGnome.
- [x] Port left placement for G-Unity.
- [x] Validate repeated slow and rapid fullscreen changes on GNOME 50 and 51.
- [x] Validate overview, workspace changes, and the complete monitor matrix.
- [x] Validate teardown/re-enable behavior on GNOME 50 and GNOME 51 after
  removing replaced inherited services.
- [x] Remove dormant App Spread, workspace isolation, and numeric-shortcut
  services; legacy App Spread actions fall back to accepted previews.
- [x] Move executable Dock modules into the unified runtime.
- [x] Remove the standalone Community Dock entry point, metadata, and lifecycle.

Evidence: GNOME 50.4 and GNOME 51.beta passed BigGnome and G-Unity with two
logical monitors, both primary-monitor choices, and primary-monitor removal.
Each layout also passed 10 slow and 25 rapid overview transitions plus 10 slow
and 25 rapid workspace transitions on both Shell versions. Strict audits found
one Dock actor per logical monitor and no stage residue. The complete local
suite passed with `531 passed`.

Fullscreen regression evidence: runtime build 49 passed the first F11 entry
after moving a non-maximized Brave window, then 10 slow and 20 rapid cycles from
both non-maximized and maximized states on GNOME 50.4 and GNOME 51.beta. Every
accepted sample required frame, buffer, `MetaWindowActor`, and
`MetaSurfaceContainerActorWayland` at `0,0 1280x800`, a mapped monitor-sized
child surface, hidden Shell chrome, and no black margins. Every exit restored
the exact original frame and buffer. Strict audits report zero failures and
warnings; current Shell journals are clean.

The root cause was a late Wayland child allocation after Mutter had centered
the surface container over its intentional black fullscreen background. Texture
invalidation did not change container placement. The final compatibility guard
observes container replacement and child allocation, coalesces the real events
through one idle, and moves only the internal container after all native
fullscreen and exact-geometry guards pass. It never changes application window
state or geometry. This matches the ownership boundary used by official Dash to
Dock and Dash to Panel.

Permanent F11 acceptance gate:

1. Move a non-maximized window away from `0,0`; test its first F11 entry.
2. Run 10 slow and 20 rapid cycles from non-maximized and maximized states.
3. Repeat the complete matrix on GNOME 50 and GNOME 51.
4. Require surface-container and mapped-child telemetry, not only window/frame
   geometry.
5. Require screenshots and exact exit restoration; source contracts are not
   visual acceptance evidence.

Gates:

1. BigGnome accepted on GNOME 50, then GNOME 51.
2. G-Unity accepted on GNOME 50, then GNOME 51.
3. Standalone Dock compatibility engine removed only after both gates pass.

### 2. Extract the Taskbar and Panel engine incrementally

- [x] Isolate panel and taskbar lifecycle ownership.
- [x] Preserve the native status area, clock, menus, and panel interaction.
- [x] Port application buttons, launch, focus, minimize, grouping, and
  multiple-window behavior.
- [x] Port Hybrid, Desk UX, and no-indicator renderers with exact geometry.
- [x] Port Classic labels without changing its no-indicator contract.
- [x] Port always visible, always hidden, and intelligent hiding as an overlay;
  maximized windows must use the released work area.
- [x] Preserve open menus while the pointer leaves the panel.
- [x] Own monitor selection, panel creation, topology signals, and reset
  serialization.
- [x] Own installation and exact restoration of Shell prototype/global hooks.
- [x] Own Overview, notification monitor, desktop usable-area, manager-signal,
  and intellihide-keybinding lifecycle.
- [ ] Validate Quick Settings, date menu, AppIndicator, JamesDSP, GSConnect,
  removable drives, notifications, and fullscreen transitions.
- [ ] Remove each inherited Panel branch only after its replacement is accepted.

Gates:

1. Hybrid accepted on GNOME 50, then GNOME 51.
2. Desk UX accepted on GNOME 50, then GNOME 51.
3. Classic accepted on GNOME 50, then GNOME 51.
4. Taskbar compatibility engine removed only after all three gates pass.

Lifecycle evidence: runtime build 50 constructs and destroys the inherited
`PanelManager` from `TaskbarSurfaceManager`; the old extension entry point is a
thin rollback adapter. Inherited visual modules use a separate live context and
no longer import lifecycle globals from the entry point. Runtime diagnostics
and the strict audit require manager ownership, global ownership, settled
activation, exact actor count, and no stage residue.

GNOME 50.4 passed fresh-session Hybrid activation; `Hybrid -> BigGnome ->
Hybrid`, `Classic -> Minimal -> Classic`, and `Desk UX -> G-Unity -> Desk UX`;
and direct runtime disable/enable. Hybrid and Classic produced one `1280x38`
Taskbar; Desk UX produced one `1280x46` Taskbar. Every managed-surface exit
released the manager, `global.dashToPanel`, and all Taskbar stage actors.

GNOME 51.beta passed fresh-session Hybrid activation, `Hybrid -> BigGnome ->
Hybrid`, and direct runtime disable/enable. The corrected transition runner then
passed all eight surface directions on both Shell versions. Every strict audit
had zero failures. Both VMs finished with exactly one `1280x800` monitor.

Theme lifecycle evidence: runtime build 51 stores component stylesheet files,
not the `St.Theme` instance that loaded them. Teardown unloads from the current
Shell theme, matching GNOME Shell's `ExtensionManager`. This fixes Classic light
-> Desk UX -> dark -> G-Unity, where a copied Community Panel stylesheet was
previously left duplicated and then became a null custom stylesheet. Helper
build 68 reports theme diagnostics, and strict audit rejects null or duplicate
custom stylesheets. The exact sequence passed twice on GNOME 50.4 and GNOME
51.beta with readable G-Unity panel icons, successful `loadTheme`, screenshots,
zero strict-audit failures, and one monitor.

Permanent theme-transition gate:

1. Enter a Taskbar layout from a light native layout.
2. Change the application color scheme while the Taskbar is active.
3. Leave for a Dock or native layout and require `loadTheme` without `ERR`.
4. Require no null or duplicate custom stylesheet in helper telemetry.
5. Inspect panel foreground visually and inspect the journal on GNOME 50 and 51.

Build 51 validation: focused `112 passed`; full suite `538 passed` with one
known PyGI deprecation warning. JavaScript syntax and diff checks pass.

Taskbar behavior evidence: builds 52-57 own app action policy, popup lifecycle,
layout-specific indicators, and visibility selection. GNOME 50 and 51 passed
launch/focus/minimize, grouped multi-window preview, context menu, Hybrid,
Desk UX, Classic, always visible, always hidden, intelligent overlay, and menu
hold checks. Exact geometry was `1280x38` for Hybrid/Classic and `1280x46` for
Desk UX. Both final Hybrid audits reported zero failures.

Official Dash-to-Panel master `1c0c1f1` confirms that intellihide changes
tracked chrome struts and queues Shell regions; it does not resize application
windows. A GNOME 50 `1280x838` regression came from runtime Taskbar teardown:
the stock top panel was restored for the 200 ms Ubuntu Dock settle before the
bottom Taskbar returned. Build 57 keeps one `PanelManager` alive across
Hybrid/Desk UX/Classic and only tears it down for Taskbar <-> Dock changes.
No geometry repair shim or blind timer remains. GNOME 50 and 51 passed
intelligent `1280x800` -> visible `1280x762` and two minimize/reactivate cycles;
GNOME 50 preserved the exact normal frame `60,116 1160x530`.

Build 57 validation: focused `88 passed`; layout-applier `102 passed`; full
suite `544 passed`, with one known PyGI deprecation warning. Runtime payload
SHA-256 is
`223230c6be0b8fde7355746923ca1bd2d0a23d23f5111012cd125fb40aead8cb`
locally and on both VMs. Both VMs finish on Hybrid with one monitor. Remaining
Panel gate: user visual acceptance of native status menus and the full manual
button/layout matrix before inherited branches are removed.

Manual follow-up build 59 closes three Taskbar defects found in that matrix.
The vertical line beside a two-window Hybrid icon was Dash-to-Panel's legacy
Metro stacked-window SVG leaking through when the user selected the Desk UX
indicator; the owned renderer suppresses that decoration without changing the
horizontal indicator or grouping behavior. Explicit always-hidden changes no
longer inherit the upstream 2000 ms startup delay. Both runtime activation and
the live settings backend configure intellihide before enabling it. Community
Menu uses native `St.Icon` sizing and follows the live Panel allocation.

Telemetry now derives expected Taskbar actor height from
`panel-height-overrides`, including Desk UX's six external margin pixels.
GNOME 51 passed live 38 -> 56 -> 38 menu scaling and Hybrid + Desk UX indicator
with two Nautilus windows without the vertical edge. GNOME 50 passed the 56 px
menu check. Both versions completed always-visible -> always-hidden within the
350 ms observation window. Final strict audits report zero failures and only
the known SSH `tty` warning; each VM has one `1280x800` monitor. Focused tests:
`111 passed`; full suite: `547 passed` with the known PyGI warning.

The original monolithic transition runner stalled once in `CompleteSwitch`
after redundantly reapplying the already verified Hybrid source. Isolated
reapply passed on builds 49 and 50. The runner now reuses a previous verified
target when it is the next source, avoiding redundant full dconf loads while
preserving all eight surface-direction audits.

Separate external-extension debt: Copyous callbacks at
`lib/ui/components/clipboardItemMenu.js:58` and
`lib/ui/items/statusItem.js:110` access `this.ext.settings` after Copyous is
disabled during `BeginSwitch`. Fix Copyous signal/idle cleanup in its own
repository; do not attribute these stacks to the Taskbar runtime.
The accepted build 51 GNOME 50 run reproduced these same late callbacks at
`clipboardItemMenu.js:58` and `statusItem.js:110`; the owning fix is signal/idle
cancellation during Copyous disable, not a runtime transition delay.

Separate AppIndicator debt on GNOME 50: its asynchronous
`_waitForFullyReady()` can resume after `AppIndicatorsIconActor` is disposed,
then reads a null `_indicator`. The stack reaches Panel teardown because status
items are being restored, but the failing frames are
`appIndicator.js:1049/1058` and `promiseUtils.js`. Fix cancellation in the
AppIndicator extension; do not add a Taskbar teardown delay.

Build 68 owns the primary physical Panel host and native status-area lifecycle.
`TaskbarPanelHost` detaches/restores `Main.panel`, owns chrome tracking, and
rolls back partial construction. `TaskbarStatusAreaHost` stores exact
parent/index state for Activities, Date Menu, and Quick Settings inside the
runtime; it no longer writes `_dtpOriginalParent` fields on Shell actors. The
native `Main.panel.statusArea` actors and popup-menu manager remain
authoritative. Two narrow reviewed bridges remain in inherited `panel.js` and
`panelManager.js`; the active module map is in
`docs/COMMUNITY_PANEL_RUNTIME_MAP.md`.

Telemetry and strict audit now cover physical-host generation/count, adoption
and restoration state, all status roles, orphans, clock, Quick Settings, open
menus, and transformed status geometry. Window telemetry distinguishes normal
applications from the DING desktop window so only real maximized applications
are compared with the work area. The extension-state audit retries only a
transient D-Bus `NoReply`.

GNOME 50.4 (`Classic`) and GNOME 51.beta (`Hybrid`) each passed 10 slow and 20
rapid Taskbar/Dock cycles. Final strict audits had zero failures, one Taskbar
actor, zero stage residue, and one `1280x800` monitor. Maximized Brave matched
the work area at `1280x768` on GNOME 50 and `1280x762` on GNOME 51. Quick
Settings opened through `Super+S` and remained open after the pointer left the
Panel. `Super+V` is Copyous and must not be used as a status-menu test.

Manual status acceptance still required: open Date Menu by click, exercise
AppIndicator/Copyous/removable-drive menus, inspect the clock, and repeat after
a full layout application rather than only an owned-schema lifecycle cycle.
GNOME 51 retains the external GSConnect `wl_clipboard.js:56` final-type restart
loop. The filtered `gnome-shell` journal contains no build 68 exception.

Build 68 validation: final focused `74 passed`; full suite `570 passed` with
the known PyGI and two headless Adwaita warnings. JavaScript syntax and diff
checks pass. PKGBUILD and package versions are unchanged. Final local and both
VM SHA-256 values:

- runtime controller:
  `27b7411b0558adfa7c0dc74b790e415f3ea88408419743feab1fce0c9a27fe27`;
- Taskbar runtime:
  `f13adc8bfe8e9217b9dad0de6beac9950fb4e8f3af78c043f490888b8b54c283`;
- Taskbar surface:
  `0308f10e05869cc48f0c1e74b8b26dc2c66182324aa7b36e24de28c0408799a9`;
- physical Panel host:
  `62b1746b2c1308f96b4c4d32d2ce5516376153649dc7826be96d012111a3edf9`;
- native status host:
  `2db448de623a9a1748e1818a4557cb56a0754d53947ad6bd77ebbab3fdea34b2`;
- inherited Panel bridge:
  `608ad91c1fcf4187f134f4c686cdec113a67cdcd36a63869f9c6936acb4f2ff2`;
- inherited Panel manager bridge:
  `6dd90d1eff9015c502b5e6f7d65782b7d3350d4a64559b68af4474a874c8fb37`;
- runtime audit:
  `0c3535990ac5035b174677a3f7debe6d4f94c0abd394179c23ce5610d9360dd8`.

Build 69 moves monitor topology and Shell hook lifecycle out of inherited
`PanelManager`. `TaskbarMonitorHost` now selects the primary monitor, creates
the exact panel set, owns topology settings and `monitors-changed`, rejects
stale asynchronous refreshes, and serializes resets. `TaskbarShellHooks` owns
the 15 inherited Shell shims/injections, stores exact original property
descriptors, and restores only properties still owned by the runtime. External
replacement is reported as a conflict instead of being overwritten.

The behavior callbacks remain inherited and unchanged. Official Dash-to-Panel
master still installs the same private Shell hooks and has no newer public
GNOME API for these integrations. This slice therefore changes lifecycle
ownership, not behavior. A missing explicit native-surface branch in
`RuntimeController` was found by the first live `Hybrid -> Minimal` check: the
expected profile changed but the active Taskbar remained. Build 69 now always
deactivates both managed surfaces for `Minimal` and rejects unknown surfaces.

GNOME 50.4 passed a real topology-setting reset, 10 slow and 20 rapid
`Hybrid <-> Minimal` cycles, and finished in its original `Minimal` state.
GNOME 51.beta passed the same topology reset and cycle matrix and finished in
its original `Hybrid` state. Every accepted endpoint had one `1280x800`
monitor, exact actor count, settled monitor ownership, all hooks either fully
owned or fully restored, zero reset failures, zero restoration conflicts, and
zero stage residue. Maximized GNOME 51 Brave retained the exact
`1280x762` work area with a `1280x38` Panel.

Strict audits on both VMs report zero failures and only the SSH `tty` warning.
GNOME Shell journals contain no build 69 exception. GNOME 51 separately logs
Copyous startup rejection at `extension.js:5` followed by enable failure at
`clipboardItem.js:283`, plus the known GSConnect final-type failure and retired
Community Dock metadata lookup. These are external extension debt; do not add
Panel delays or teardown workarounds.

Build 69 validation: focused `133 passed`; full suite `573 passed`, with one
known PyGI warning. All runtime/inherited JavaScript syntax and diff checks
pass. PKGBUILD and package versions are unchanged. Final local and both-VM
SHA-256 values:

- runtime controller:
  `f45321369b3d696b2b80975eccc005287620de931a5672cbcf53031f8d493a31`;
- Taskbar surface:
  `02dd68de36c24cd6e66e8f55f3a6260b2fd94bcac3abfa0045e94c63953a9dde`;
- monitor host:
  `fb1acb42dae183f4a2e06a8f8f06a769d952b34daf1b8ff6564da2746491f932`;
- Shell hook host:
  `a70b54574623f38c19224cd328478aa12aad59e1756a6a70209c5072b80b106e`;
- inherited Panel manager:
  `5d0ea06fe3740b1fd0219850d3dff0a65fb8b35738977826bb099c83c3f0b4aa`;
- runtime audit:
  `ab808accf2ef5d9437b827c4dcd8da28a0184d41d2e52f8fc80311f5d89740e4`.

Build 70 moves the remaining manager-service lifecycle behind
`TaskbarServiceHost`. The host owns construction, activation order, binding,
panel release, and reverse-order teardown for inherited Overview and
notification services, DING usable-area integration, the seven manager signal
groups, and the intellihide keybinding. `PanelManager` keeps its accepted
behavior callbacks and compatibility references, but no longer constructs or
destroys these services directly.

This was a lifecycle boundary, not an implementation rewrite. Official
Dash-to-Panel master still constructs the same private services directly and
does not expose a newer public GNOME API. At build 70, inherited `overview.js`,
`notificationsMonitor.js`, and `desktopIconsIntegration.js` implementations
remained loaded behind the owned host until their individual replacements
passed the behavior and restoration gates.

`TaskbarServiceHost` cancels pending DING margin idles and performs
transactional partial cleanup after activation errors. Compatibility references
are cleared only if they still point to the owned instance. Telemetry records
ownership and activation, launcher subscription, Unity D-Bus ownership,
notification applications, exact per-monitor desktop margins, pending margin
work, seven signal groups, keybinding ownership, failures, and the last error.
The strict audit requires one-monitor margin coverage and exact equality between
the bottom DING margin and physical Taskbar height.

GNOME 50.4 retained its original Classic layout; GNOME 51.beta retained Hybrid.
Each passed 10 slow and 20 rapid Taskbar-to-Minimal lifecycle cycles, 10 slow
and 20 rapid native Overview cycles, one real notification, a 38 -> 56 -> 38 px
DING margin cycle, and intelligent-hide `Super+I` reveal/release. Final strict
audits report zero failures and only the SSH `tty` warning. Both finish with one
`1280x800` monitor, empty height and visibility override maps, and the original
empty Overview keybinding. GNOME 50 and GNOME 51 journals contain no build 70
JavaScript exception.

Build 70 final validation: focused `78 passed`; full suite
`574 passed`, with one known PyGI warning and two headless Adwaita warnings.
Runtime and inherited JavaScript syntax and diff checks pass. PKGBUILD and
package versions are unchanged. Final
local and both-VM SHA-256 values:

- runtime controller:
  `6282781a48fe0f859cbfd2156d7125ef0ec749f5cc5030a994b8140cf98f178c`;
- Taskbar surface:
  `2daa153ffde844a3f80376b8717fbb1f00c8a4a86ec52a9a5fe16211d1a5e3a2`;
- monitor host:
  `e1820ef3f9827c9eacd16045334d78e53827a94885da70d6ea629ff5c6b4217d`;
- service host:
  `4fa9f070c8a7c27f0b9d03c8bf1d32807d8ad15106e900218ac9c62a76945e28`;
- inherited Panel manager:
  `fb25771f6ce5964489047071c6f2d6b232c3125f332a660def545c63142045b8`;
- runtime audit:
  `64c8346bdf418c73714e09fa05f4c701e34ddd0ddd480c681632d7ecf1cc7f0e`.

Build 71 replaces both inherited DING usable-area implementations with one
shared runtime-owned module. Dock uses `community-dock@communitybig.org` and
Taskbar uses `community-panel@communitybig.org` as stable margin owners. The
implementation preserves the official DING sentinel, 100 ms coalescing,
extension-state reconnection, and `setMarginsForExtension()` protocol.
Telemetry exposes ownership, connection, pending dispatch, dispatch count, and
the exact enabled DING recipients. Strict audit rejects inherited ownership,
disconnection, pending work, or recipient drift.

The first GNOME 50 Taskbar activation caught an invalid owner object before any
actor leaked. The root cause was that the runtime surface manager is not an
extension record and has no UUID. Passing the explicit stable Taskbar owner
fixed activation transactionally; no timer workaround was added.

GNOME 50 accepted BigGnome and Taskbar exact-margin checks, including a 38 ->
56 -> 38 px update, dynamic DING activation, 10 slow and 20 rapid transitions,
and zero strict-audit failures. GNOME 51 accepted the same exact 38/56 px
geometry, dynamic recipient telemetry, 10 slow and 20 rapid transitions, and
zero strict-audit failures. Both finish with one monitor and their original
layout, override-map, and DING state.

One discarded GNOME 51 rapid block coincided with GSConnect 72 repeatedly
failing `Cannot inherit from a final type`. A captured stack showed the Shell
main thread and dconf worker deadlocked in GJS/GObject toggle-reference cleanup.
After a session restart, five replacement rapid cycles passed individually with
GSConnect temporarily disabled. Its original enabled/error state was restored;
this external failure is not attributed to build 71.

The runtime-owned implementation retains the upstream 1-clause BSD notice.
Both unreferenced inherited copies were removed only after live acceptance.
Two engine boundaries remain: Overview, then the final inherited
status/fullscreen behavior and exact-teardown gate.

Build 71 final validation: focused `79 passed`; full suite `575 passed`, with
one known PyGI warning. All runtime and inherited JavaScript syntax and diff
checks pass. PKGBUILD and package versions are unchanged. Final local/GNOME 50/
GNOME 51 SHA-256 values match:

- runtime controller:
  `79c78c2e234d5a227e4a061fd93e43437a2c80de750254abc28c282e902b7eed`;
- Taskbar service host:
  `f1eb7afa540c3cca2ee52e141668308ce7df124614f0eaeec81cc85baf28ba15`;
- shared DING bridge:
  `7e78f4953c79898c95d145fa69cfb13984cebfc81294256bca0f722cbd03f538`;
- Dock imports:
  `88a8d26e2ac62fe2747371f266b36cc05aec1579d8ed1c349fba5a7c705b3d62`;
- Dock runtime:
  `9672f688e01e7094b11dab3c1cddcce51e66a3c3ba512226da69f4bbdd4eba03`;
- runtime audit:
  `efb56a7f4981f0964df79de2a32e13dc993436fadf3c18a7eb045316388adc8e`;
- complete unified-runtime payload:
  `eccff7810be42f25a4beb973ba1b2240eed71e265748628db5edb4344be5bd2b`;
- complete Community Panel compatibility payload:
  `1963a060026a0ee8b1ca63d23d72f4f4b182c57142eb3388d5d539568d27bdac`.

Build 72 replaces the inherited Taskbar notification monitor behind the
existing owned lifecycle. The runtime implementation aggregates multiple live
message-tray sources for one desktop application, combines their counts with
Unity launcher updates, preserves application-ID normalization, and clears
counts and urgency when the application gains focus. It transactionally owns
the Shell focus/tray signals, launcher subscription, and
`com.canonical.Unity` bus name.

Official GNOME Shell 50.4 and main message-tray contracts and current
Dash-to-Panel `notificationsMonitor.js` were reviewed first. Dash-to-Panel still
uses the same private Shell signals and exposes no newer public notification
API. The owned port keeps that contract but fixes source aggregation and stale
Unity urgency without adding timers.

Telemetry exposes implementation and connection ownership, tracked source and
state counts, total notifications, urgent desktop IDs, update count, and the
last updated app. Strict audit rejects inherited ownership, disconnected
signals, negative or incoherent counts, and non-desktop urgent IDs. Contract
tests require source add/remove, focus tracking, launcher subscription, Unity
bus ownership, and transactional cleanup.

GNOME 50 accepted a real transient notification, visible Brave badge, focus
clearing, 10 slow and 20 rapid Unity cycles, exact Taskbar teardown/re-entry,
and a final zero-failure BigGnome audit. GNOME 51 accepted the equivalent real
notification and focus tests, 10 slow and 20 rapid cycles, and a final
zero-failure Hybrid audit. Both finish with one `1280x800` monitor. A discarded
GNOME 50 repeated full-layout stress sequence reached the existing GJS/dconf
futex deadlock after many extension reloads; no runtime exception was logged,
and the restarted session passed. Layout tests must use the complete app
workflow: apply the full `LayoutApplier.apply()` snapshot and, only after
success, persist the same label through `Settings().set("active_layout", ...)`.
Changing only runtime `active-layout`, or omitting the app state, creates a
mixed visual state and is not a valid transition test. Strict audit now rejects
application/runtime layout drift.

The dormant inherited notification monitor was removed only after both live
matrices passed. Focused tests: `80 passed`. Full suite: `576 passed`, one known
PyGI warning. Changed JavaScript syntax and diff checks pass. PKGBUILD and
package versions are unchanged. Final local/GNOME 50/GNOME 51 SHA-256 values
match:

- runtime controller:
  `eebb4822151d9cd3d585ca530f00f678c365f8e3696ec09494dc9c15cc7a57cd`;
- Taskbar service host:
  `69ecf8b1e59257d5f715ef3ebcb96bc10413a62f3916ae65d0c134e26aef6c66`;
- Taskbar notification monitor:
  `e2521f86fe4612cc48b4a13c822785fe9441bc9a37fcf794bced7e00bdcb3559`;
- runtime audit:
  `74335c366544efb2c393eea4febdb9e16816c5468f809a6500ec58b9126ccf4e`;
- complete unified-runtime payload:
  `01e436ca5c25a9fbf47eb6397f5693041a6fb0854f7cbacd5fc0c390e3a5c69b`;
- complete Community Panel compatibility payload:
  `6ec10936aca90596ded0a07d82a5b49725533d32cab652169126e875586280d6`.

Build 73 replaces the inherited Taskbar Overview implementation behind the
existing owned service lifecycle. `TaskbarOverviewIntegration` owns dash
visibility, Overview allocation, optional workspace isolation, number hotkeys
and previews, and empty-space exit. It records exact property descriptors,
signals, keybindings, and timeouts, and refuses to overwrite a hook replaced by
another extension during restoration.

GNOME Shell 50.4 target
`233322b9b675b0385767147c1a6cfc6ff7325160`, Shell main
`6db7eaf5377e24d85eb9251316a8b2b5ca407cc4`, Dash-to-Panel master
`1c0c1f1354bfaccbf2539ef516ec527bea498a51`, and official GJS lifecycle and
`InjectionManager` guidance were reviewed first. Both Shell versions retain the
same central private Overview contracts; no public replacement exists.

Telemetry and strict audit require runtime ownership, active connections,
configured hook/keybinding state, coherent Overview/search/app-grid state,
exact restoration state, zero conflicts, zero pending preview/timeouts, and
zero orphan actors. Contract tests reject the inherited import and require the
owned module. The inherited `overview.js` was removed only after both live
matrices passed.

GNOME 50.4 passed in Classic and GNOME 51.beta passed in Hybrid: first entry,
normal and maximized windows, search, app grid, application activation,
workspace switching, menus, empty-space exit, 10 slow and 20 rapid cycles in
each window state, native Minimal restoration, and Taskbar re-entry. Final
strict audits report zero failures; GNOME 50 is BigGnome, GNOME 51 is Hybrid,
application/runtime labels match, and each VM has one `1280x800` monitor.
Current-shell journals contain no new-module error. GNOME 51 retains the
external GSConnect `wl_clipboard.js` final-type failure.

Focused tests: `80 passed`. Full suite: `576 passed`, one known PyGI warning.
Changed JavaScript syntax and diff checks pass. PKGBUILD and package versions
are unchanged. Final local/GNOME 50/GNOME 51 SHA-256 values match:

- runtime controller:
  `9d918d47d5c48e8ab94fbafb662e157ad65489a322f01d392d29538f3fbd36ee`;
- Taskbar service host:
  `a53bc122e5ddacd00f701d272c73692d3f88f1e60f3d92dd098a6d52931fb72d`;
- Taskbar Overview integration:
  `0411e487cce6475141ae75eb88dbe292a7eed5d8116b30a30b8eea6fbd7170dc`;
- runtime audit:
  `a96b9abf4c1a75bf023bbf990f49a7a6e264aa72d602390691265b18e4e4d770`;
- complete unified-runtime payload:
  `50236f08080c1fddc1529fe9fe19d358887717eea4f07ac320c6ba78e865c60a`;
- complete Community Panel compatibility payload:
  `ee34534c3b866291f5e13a0122bc5f69421177601ec54b3080714e6192bb6bb1`.

Final Panel slice: port remaining inherited status/fullscreen behavior and pass
the exact-teardown gate. Do not start it in build 73.

Post-migration product backlog, explicitly outside the final engine boundary:

- BigGnome Dock applications-menu side, with right preserved as the default
  and left offered as a per-layout choice.
- A third Dock hover card for pointer-distance magnification. Icons must grow
  and shrink progressively like the macOS Dock, without replacing Standard or
  Gentle lift.

### 3. Finish settings ownership

Build 61 completes the first exclusive owned-setting slice. While the unified
Taskbar runtime is active, Panel visibility reads and writes only
`panel-visibility-overrides`; it no longer mirrors live writes to the inherited
Community Panel schema. Existing users retain a one-time legacy import, and the
standalone compatibility path still mirrors until upgrade coverage permits its
removal. The runtime listens to the owned override key and applies changes
without rebuilding the Taskbar.

Live validation exposed an inherited Dash-to-Panel ordering defect when leaving
intellihide: `disable()` restored the strut before revealing the translated
Panel actor. Mutter could therefore retain a maximized `1280x838` allocation
after returning to always visible. Build 61 restores the actor first, then its
strut, following the actual geometry dependency. It adds no timer, window
resize, or compositor repair shim.

GNOME 50.4 and 51.beta each passed 10 slow and 20 rapid owned-schema visibility
cycles with a maximized Brave window. Final visible frame/work-area geometry
was respectively `1280x745` with a 55 px Panel and `1280x762` with a 38 px
Panel. Controlled non-maximized cycles preserved exact frames
`60,107 1160x530` and `38,59 1106x556`. GNOME 51 also passed a subsequent
maximized minimize/restore cycle at `1280x762`. Strict audits report zero
failures and only the SSH `tty` warning. Both VMs retain one `1280x800` monitor;
GNOME 50 retained its pre-existing Desk UX/Classic visibility overrides and
GNOME 51 retained an empty map.

Build 61 validation: focused `93 passed`; full suite `550 passed`, with the
known PyGI warning and two headless Adwaita warnings. JavaScript syntax, focused
Ruff, and diff checks pass. Final local/VM file SHA-256 values:

- runtime controller:
  `1aad43cf7213c1de0ab11f2788698a51bc0f25bee7fdb7e891031a39af4d1619`;
- Panel intellihide:
  `aa9de9b7b7274c20de02f224afbd40c7c35e5d88c0622417b1d2ada97b6dbd08`;
- settings backend:
  `730a16681a92137974390688da2ad095586be85756b4ccbdf95b3b61af08e04d`;
- Panel/Dock page:
  `d9196a2711bc0741a4f796c13d7cb1ed7998abbeb9190e0bc781723f019eefcd`.

Build 62 adds Taskbar Panel height to the exclusive owned-setting boundary. The
GTK backend reads/writes only `panel-height-overrides` while the unified runtime
is active. One-time import still reads the inherited `panel-sizes`, and the
standalone compatibility path still mirrors it. Runtime changes are clamped to
32-56 px and applied through Dash-to-Panel's official per-monitor
`PanelSettings.setPanelSize()` API. This keeps monitor IDs and native
`changed::panel-sizes` geometry resets instead of duplicating its JSON logic.

GNOME 51 passed 38 -> 56 -> 32 -> 38 with a maximized Brave window. Exact
frame/work-area geometry followed each visible Panel height: `1280x744` at 56,
`1280x768` at 32, and `1280x762` at the restored 38. GNOME 50 passed 56 and 32
in intelligent overlay mode; at 56 the normal Brave frame remained
`60,135 1160x530`, work area remained `1280x800`, and `affectsStruts` remained
false. Both versions passed 10 slow and 20 rapid cycles without rebuilding the
Taskbar manager.

Final maps were restored exactly: GNOME 51 height/visibility maps are empty;
GNOME 50 retains `{'Classic': 36}` for height and
`{'Classic': 'always-visible', 'Hybrid': 'intelligent'}` for visibility. Both
use monitor ID `RHT-0x00000000` internally at 38 px, retain one `1280x800`
monitor, and pass strict audit with zero failures and only the SSH `tty`
warning. The GNOME Shell journals contain no runtime/Panel exception; GNOME 51
still has the separate GSConnect final-type error.

Build 62 validation: focused `95 passed`; full suite `552 passed`, with one
known PyGI warning. JavaScript syntax, focused Ruff, and diff checks pass.
Final local/VM SHA-256 values:

- runtime controller:
  `a1b41da01a840e02b0ab7abcad710310288f0a50f3d6d6152c30ccd42294c753`;
- Taskbar runtime:
  `8f9068c8889c98cee78efb5fb8b378f38964a11af98613ddb0d4816c431cb69a`;
- Taskbar surface:
  `386e61b153d174986e79dc35c024e07cee2f1c6db8d8d6092a9edf392c1464d0`;
- settings backend:
  `97055a24a14dfb5b32d24215856e0ab268cc967be6e0595a2f3a6184ff6a347c`.

Build 64 moves Taskbar Panel opacity to the exclusive owned-setting boundary.
The GTK backend reads and writes only `panel-opacity-overrides` while the
unified runtime is active. One-time import still reads inherited opacity, and
the standalone compatibility path still mirrors it. Runtime updates use the
inherited Dash-to-Panel renderer with custom static opacity enabled and dynamic
opacity disabled. Audit telemetry compares the configured value with every
effective actor alpha.

GNOME 50.4 and 51.beta each passed 20% and 90% extremes, 10 slow transitions,
and 20 rapid transitions without rebuilding `PanelManager` or duplicating the
Taskbar actor. A maximized Brave window remained exactly `1280x762` while
opacity changed 90 -> 20 -> 70. GNOME 50 retained its original empty opacity
map; GNOME 51 retained `{'Hybrid': 70}`. Both finish on Hybrid with one
`1280x800` monitor.

GNOME 51 launch-by-number testing also exposed an upstream compatibility
boundary: Mutter 51 adds a `ClutterSprite` parameter to
`MetaDisplay::grab-op-begin`, while current Dash-to-Panel code emits the GNOME
50 two-parameter form. Runtime build 64 queries the loaded GObject signal and
emits its exact parameter count. `Super+2`, launch, focus, overview exit, and
maximize pass on both Shell versions without a runtime JS exception.

Strict audits report zero failures and only the expected SSH `tty` warning.
Shell journals contain no Layout Switcher or Community Panel exception after
the build 64 session restart. Known external warnings remain: Copyous and
GSConnect on GNOME 51, retired Community Dock metadata lookup, KMS priority,
and Brave's corrected invalid Wayland geometry warning.

Build 64 validation: focused `98 passed`; full suite `557 passed`, with one
known PyGI warning. All runtime JavaScript syntax, strict schema compilation,
and `git diff --check` pass. Ruff remains blocked by nine pre-existing findings
outside this slice. Final local and both-VM SHA-256 values:

- layout profiles:
  `0638c8f91382071fa7aaf08b889ebbacdd6991b1dfcfd26ecfe9e9f19bd84c32`;
- runtime controller:
  `64576aee4a6fee6ccbe59d64a5f6083f18b79b373d0cd6e0b28c31205ddac2c2`;
- Taskbar runtime:
  `66b386dca89c2b6ac72c586fa2235e4358195fce0ae3572cb2ac01e1431419e7`;
- Taskbar application actions:
  `3b6e4d51e6c4b69f110a6f1ef08bab6388e5841b4fe9c9839ad37d447f778961`;
- settings backend:
  `335c4f6aadc76cdf84b92c27f40a8ca0b45125eb60aab6b0b52149bd41d5f7a2`;
- runtime audit:
  `99df26dc744f920e3fbf946e3b14b10e50a896ebe1b7dfa5f23177557c467af1`.

Build 65 completes the supported-setting ownership boundary. Indicator style
and hover now read and write only owned per-layout overrides while the unified
runtime is active. Dock opacity, size, and visibility use the same boundary.
The GTK backend reads legacy values only for one-time import or standalone
rollback. Classic ignores stale indicator overrides and remains label-only.

Dock updates are live. Indicator, hover, opacity, icon size, and visibility no
longer destroy and reconstruct an active Dock. Runtime telemetry reports a
manager generation plus configured and effective Dock opacity and icon size.
The owned Dock indicator and hover controllers no longer read the old custom
Community schema. Inherited Dash-to-Dock and Dash-to-Panel settings remain only
as private renderer adapters; they are not the Layout Switcher persistence
contract.

GNOME 50.4 and 51.beta each passed Taskbar indicator/hover 10 slow and 20
rapid cycles, the Classic no-indicator guard, and Dock indicator/hover/opacity/
size/visibility 10 slow and 20 rapid cycles. Dock extremes were 20%/90%,
28/64 px, and all three visibility modes. `managerGeneration` remained `1`
through every same-layout Dock update. Legacy custom indicator and hover
values were unchanged. Original override maps were restored exactly.

Both VMs pass strict audit with zero failures and only the expected SSH `tty`
warning. Their Shell journals contain no runtime, Dock, or Panel exception.
Each finishes on Hybrid with one `1280x800` monitor. Focused tests:
`106 passed`; full suite: `565 passed`, with the known PyGI and two headless
Adwaita warnings. JavaScript syntax, strict schemas, focused Ruff, and diff
checks pass. Final local and both-VM SHA-256 values:

- unified runtime tree:
  `5675f1c607206569d9ecd060a522935ddab196c08f4e173aee0cd30a741169d7`;
- runtime controller:
  `036bef314b23fb17646a4646feac5d2f7d24c3a52e2e9f8145b8a0e632db5c25`;
- Dock runtime:
  `d0684de8766306a7f0f03fe54da04261dbd1ca9dab194449def7438202145065`;
- Taskbar runtime:
  `a6b96e8e49dfbb1b384e7d769d9c7181165b9305374e69a7108f907066f5f4e2`;
- settings backend:
  `0d643b27939331b290d485ca23d3d3492e66b32ac97bb043ef721c747439856c`;
- runtime audit:
  `3cba44badea074f415a6956bda5b9c9225182d0053d275958c7399eab70302f9`;
- runtime audit payload:
  `16aed076c4f97263fa237fbf131b2cbdc83bf882419ad57fe8e61de1fbadd344`.

User visual acceptance remains required. Direct owned-schema cycles prove the
runtime and renderer contract, but do not replace checking the GTK controls,
indicator pixels, hover motion, and visibility transitions by eye.

- [x] Stop mirroring new writes to inherited Dock and Panel schemas while the
  unified runtime owns the active component.
- [x] Move every supported runtime key to the Layout Switcher-owned schema.
- [x] Keep one-time import for existing stable and testing users.
- [x] Preserve unrelated extensions and user settings during migration.
- [x] Make `Restore layout defaults` clear only the active layout overrides.
- [ ] Remove obsolete schema adapters after upgrade validation.
- [ ] Remove dormant Dash to Dock and Dash to Panel sections from saved layouts
  only after the owned schema contains every required value.

Gate: clean install and stable-to-new upgrade produce the same accepted layout.

### 4. Stable migration and rollback validation

- [ ] Test upgrade from the current stable package without opening Layout
  Switcher before the first login.
- [ ] Test upgrade from the testing package and all intermediate Community UUIDs.
- [ ] Confirm the menu icon, helper, unified runtime, and active layout survive
  logout/login and reboot.
- [ ] Confirm old external extension packages remain installed but disabled when
  the selected layout does not use them.
- [ ] Confirm unrelated user extensions remain untouched.
- [ ] Test downgrade or package rollback to the safe checkpoint.
- [ ] Retain compatibility engines for one complete testing-repository cycle.

Gate: clean installation, stable upgrade, testing upgrade, and rollback accepted.

### 5. Final cleanup

- [ ] Delete unused inherited runtime branches, schemas, assets, translations,
  and compatibility hosts.
- [ ] Keep required upstream license and attribution files.
- [ ] Remove stale references to standalone Community Dock and Community Panel
  activation.
- [ ] Update extension descriptions and architecture documentation.
- [ ] Record final installed bytes and JS/CSS line count.
- [ ] Run gettext extraction and LangForge only after UI strings stabilize.
- [ ] Validate PO files and compile catalogs.
- [ ] Build the package in CI and run the complete automated suite.

Gate: GNOME 50 and GNOME 51 matrix accepted before testing publication.

## Safe execution rules

Every implementation slice must:

1. change one behavior or lifecycle boundary only;
2. add a focused regression test before removing inherited code;
3. pass focused tests, the full suite, JavaScript syntax, and strict schema
   compilation;
4. deploy exact files and verify local/VM hashes;
   package-managed extension UUIDs must exist only under `/usr/share`; never
   shadow them with a second copy under `~/.local/share/gnome-shell/extensions`;
   after a direct file sync, compile every extension-local schema before
   reloading the runtime (`community-dock`, `community-panel`, and
   `frosted-glass`);
5. restart only the Shell session when required;
6. replay the affected source/target layout transitions on GNOME 50;
7. replay them on GNOME 51 after GNOME 50 approval;
8. obtain user visual approval;
9. create a checkpoint commit before the next slice;
10. restore the previous checkpoint immediately if duplicate actors, missing
    surfaces, login loops, Shell D-Bus stalls, or stale theme state appear.

Never combine lifecycle extraction, visual redesign, schema deletion, and
package migration in one change.

## Deferred product options

These are not required for the runtime migration:

- Dock position selector beyond accepted layout defaults.
- Dock fill-versus-fit selector.
- Multi-monitor target selector.
- Applications, Trash, and mounted-volume toggles.
- Arbitrary alignment, spacing, padding, margins, or element ordering.
- Advanced mouse actions, scroll actions, animations, and preview tuning.

Add a deferred option only after a concrete user need and a separate approval.

## Definition of done

- [ ] Only the unified runtime implements Dock and Taskbar actors.
- [ ] Compatibility engines are absent from the shipped package.
- [ ] All supported configuration exists only in Layout Switcher.
- [ ] The six layout contracts match the accepted visual baseline.
- [ ] Light/dark transitions and status icons never retain stale state.
- [ ] Clean install, stable upgrade, testing upgrade, reboot, and rollback pass.
- [ ] GNOME 50 and GNOME 51 pass the complete live matrix.
- [ ] Full automated tests, package build, translations, and documentation pass.
- [ ] User approves publication to the testing repository.
