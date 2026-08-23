# Shell Runtime Remaining Work

Last update: 2026-08-23
Safe checkpoint: `13c4da6`
Status: unified controller accepted; compatibility-engine extraction pending

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
- Community Dock and Community Panel are disabled as standalone extensions;
- their accepted runtime engines are still imported internally as rollback
  modules;
- independent Dock and Panel preference screens are removed;
- supported controls and per-layout defaults belong to Layout Switcher;
- external Dash to Dock and Dash to Panel packages are not package dependencies
  and are not modified or uninstalled from user systems.

The earlier direct `DockManager` replacement was removed because its teardown
callbacks outlived cleared extension settings and could wedge Shell D-Bus during
a Classic-to-BigGnome transition.

## Current architecture

```text
Layout Switcher GTK app
  -> owned runtime schema and per-layout overrides
  -> helper extension for safe switch orchestration
  -> unified Shell runtime UUID
       -> Dock compatibility engine for BigGnome and G-Unity
       -> Taskbar compatibility engine for Hybrid, Desk UX, and Classic
       -> native GNOME surface for Minimal
```

Current internal payload:

| Module | Bytes | JS/CSS lines | Public UUID enabled |
|---|---:|---:|---|
| Unified controller | 11,005 | 336 | yes |
| Dock compatibility engine | 632,843 | 14,652 | no |
| Taskbar compatibility engine | 1,201,543 | 12,854 | no |
| Total | 1,845,391 | 27,842 | one public runtime |

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
- [ ] Port favorites, running applications, launch, focus, minimize, and
  multiple-window behavior.
- [ ] Port notification badges and application context menus.
- [ ] Port the three accepted running indicators.
- [ ] Port standard and soft-lift hover behavior without hover rectangles.
- [ ] Port always visible, always hidden, and intelligent hiding.
- [ ] Port bottom placement for BigGnome.
- [ ] Port left placement for G-Unity.
- [ ] Validate overview, fullscreen, workspace changes, monitor changes, and
  teardown/re-enable behavior.
- [ ] Remove each inherited Dock branch only after its replacement is accepted.

Gates:

1. BigGnome accepted on GNOME 50, then GNOME 51.
2. G-Unity accepted on GNOME 50, then GNOME 51.
3. Dock compatibility engine removed only after both gates pass.

### 2. Extract the Taskbar and Panel engine incrementally

- [ ] Isolate panel and taskbar lifecycle ownership.
- [ ] Preserve the native status area, clock, menus, and panel interaction.
- [ ] Port application buttons, launch, focus, minimize, grouping, and
  multiple-window behavior.
- [ ] Port Hybrid, Desk UX, and no-indicator renderers with exact geometry.
- [ ] Port Classic labels without changing its no-indicator contract.
- [ ] Port always visible, always hidden, and intelligent hiding as an overlay;
  maximized windows must use the released work area.
- [ ] Preserve open menus while the pointer leaves the panel.
- [ ] Validate Quick Settings, date menu, AppIndicator, JamesDSP, GSConnect,
  removable drives, notifications, and fullscreen transitions.
- [ ] Remove each inherited Panel branch only after its replacement is accepted.

Gates:

1. Hybrid accepted on GNOME 50, then GNOME 51.
2. Desk UX accepted on GNOME 50, then GNOME 51.
3. Classic accepted on GNOME 50, then GNOME 51.
4. Taskbar compatibility engine removed only after all three gates pass.

### 3. Finish settings ownership

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
