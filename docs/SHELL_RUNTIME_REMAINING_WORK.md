# Shell Runtime Remaining Work

Last update: 2026-08-26
Safe checkpoint: `5c01c96`
Status: Taskbar visibility and height setting ownership accepted

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
       -> owned Taskbar lifecycle with inherited visual modules
          for Hybrid, Desk UX, and Classic
       -> native GNOME surface for Minimal
```

Current internal payload:

| Module | Bytes | JS/CSS lines | Public UUID enabled |
|---|---:|---:|---|
| Unified runtime with Dock and Taskbar lifecycle | 504,427 | 14,366 | yes |
| Dock resource host | 176,013 | 1,713 CSS | no entry point |
| Inherited Taskbar visual modules | 1,198,149 | 12,737 | rollback adapter only |
| Total | 1,878,589 | 28,816 | one public runtime |

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
- [ ] Preserve the native status area, clock, menus, and panel interaction.
- [x] Port application buttons, launch, focus, minimize, grouping, and
  multiple-window behavior.
- [x] Port Hybrid, Desk UX, and no-indicator renderers with exact geometry.
- [x] Port Classic labels without changing its no-indicator contract.
- [x] Port always visible, always hidden, and intelligent hiding as an overlay;
  maximized windows must use the released work area.
- [x] Preserve open menus while the pointer leaves the panel.
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

Next slice: move Taskbar Panel opacity to exclusive owned-schema control. Do
not remove all inherited schema adapters until every required setting and the
stable/testing upgrade matrix are accepted.

- [ ] Stop mirroring new writes to inherited Dock and Panel schemas.
- [ ] Move every required runtime key to the Layout Switcher-owned schema.
- [ ] Keep one-time import for existing stable and testing users.
- [ ] Preserve unrelated extensions and user settings during migration.
- [ ] Make `Restore layout defaults` clear only the active layout overrides.
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
