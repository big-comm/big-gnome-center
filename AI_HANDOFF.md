# AI handoff — Layout Switcher

> Active continuation document. Read this file before changing the repository.
> Update the checklist and decision log after every verified task.
> Last updated: 2026-08-22.

## Current objective

Stabilize and polish the application on GNOME 50 first. GNOME 51 work is
deferred until its expected release on 2026-09-15 unless the user explicitly
changes the priority.

The local repository is always the source of truth. Changes are made locally,
checked locally, and only then copied to the target VM for live validation.

## Safety rules

- Preserve all existing user changes. The worktree is intentionally very dirty.
- Never reset, clean, checkout, or overwrite unrelated files.
- Fix root causes with the smallest practical patch. Avoid broad refactors.
- Start with focused tests. Run the full suite before declaring a risky change done.
- Do not hand-edit layout dumps unless the user explicitly requests it.
- Do not bump versions during iterative work.
- Keep code, comments, internal docs, and commit messages in concise English.
- Do not store VM passwords or other credentials in the repository.
- Do not use destructive `rsync --delete` deployment commands.
- Copy only reviewed files to a VM. Confirm destination paths before privileged writes.
- Treat a VM deployment as incomplete until the deployed files match the local hashes.
- Do not begin GNOME 51 compatibility changes while GNOME 50 is the active target.

## Test environments

| Target | SSH | Priority | State |
|---|---|---:|---|
| GNOME 50 | `tales@192.168.128.230` | Active | Current validation target |
| GNOME 50 clean migration | `tales@192.168.128.206` | Verified | Stable Hybrid upgraded in place; automatic migration accepted |
| GNOME 51 | `tales@192.168.128.114` | Deferred | Revisit on/after 2026-09-15 |

Credentials are supplied out of band by the user and intentionally omitted here.

System installation root used by the application:
`/usr/share/layout-switcher/`.

## Architecture landmarks

- `usr/share/layout-switcher/layout_applier.py`: critical live-apply flow.
- `usr/share/layout-switcher/helper_client.py`: client for the in-shell helper.
- `usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/`:
  live layout switching and shell-owned operations.
- `usr/share/gnome-shell/extensions/community-menu@communitybig.org/`:
  bundled application menu.
- `usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/`:
  overview/application blur.
- `usr/share/layout-switcher/ui/page_desktop.py`: desktop page and Python-built
  menu-style previews.
- `usr/share/layout-switcher/ui/styles.py`: application CSS, including preview
  styling and default badges.
- `tests/`: regression contracts. Some UI tests inspect source because GTK is not
  available in the headless unit-test environment.

The current extension UUIDs end in `@communitybig.org`. Do not restore obsolete
`@bigcommunity.org` paths that appear as deletions in `git status`.

## Worktree warning

The repository contains a large, intentional migration with modified, deleted,
and untracked files. In particular, `page_desktop.py` and its focused test are
currently untracked. Their contents are active user work, not disposable files.
Always inspect `git status --short` and the exact diff of files touched by the
current task.

Older `CONTEXT.md`, `ARCHITECTURE.md`, and `PLANNING.md` notes contain useful
history but are stale in several areas. This file defines the current priority
and operational checklist. Verify old architectural claims against current code.

## Active task checklist

### Clean GNOME 50 package migration

- [x] Record the pre-upgrade baseline: GNOME Shell 50.4 and package
  `26.08.04-1821` from `community-stable`.
- [x] Confirm the published testing package is older than the current worktree.
- [x] Build a local `26.08.20-1` package from the current worktree.
- [x] Pass the PKGBUILD check phase: `436 passed`.
- [x] Verify critical package hashes against the worktree.
- [x] Upgrade through `pacman -U`; do not deploy loose source files.
- [x] Confirm new bundled extension directories, schemas, and migration autostart.
- [x] Confirm obsolete helper and Community Menu directories are absent.
- [x] Log out and back in to exercise the automatic UUID migration.
- [x] Confirm the new helper, Community Menu, and Community Panel can become active.
- [x] Upgrade an untouched legacy Hybrid session without manually applying a layout.
- [x] Preserve legacy Big Shot when the replacement UUID is not installed.
- [x] Preserve ArcMenu and migrate its custom icon path to the current UUID.
- [ ] Confirm the untouched first BigGnome desktop has a working task component.
- [ ] Confirm only Classic and Hybrid enable desktop icons by default.
- [ ] Exercise all six layouts and record visual acceptance.

The pre-login Shell process still reports the legacy enabled UUIDs. This is the
expected control state: GNOME Shell caches extension discovery, and the session
autostart guard performs user-setting migration on the next login. Do not run
the guard manually before the first-login test.

Post-login findings:

- Helper build 58, Community Menu, and Community Panel are active after applying
  Hybrid. BigGnome intentionally does not enable Community Menu.
- The installed `gnome-shell-big-shot 26.07.25-1540` still provides only
  `big-shot@bigcommunity.org`. Migration selected the unavailable
  `big-shot@communitybig.org`, and helper activation was rejected. Add an
  availability-aware fallback or align the dependency package before release.
- Community Dock cleanup touched an already disposed actor while switching from
  BigGnome. The switch completed, but helper actor tracking needs a lifecycle
  guard.
- Copyous emitted missing `highlight.min.js` and undefined-settings errors from
  the user's local extension copy. This is external to Layout Switcher.

Second-pass reset:

- Downgraded `.206` back to stable `26.08.04-1821` with the repository package.
- Restored the exact legacy Hybrid extension lists: old helper, GTK4 DING,
  AppIndicator, old Big Shot, Copyous, legacy theme switcher, GSConnect,
  Light Style, Dash to Panel, and ArcMenu.
- The next login must confirm the old Hybrid baseline. Apply Hybrid once in the
  old application before reinstalling the local current package.
- Old Hybrid baseline was confirmed active: legacy helper, Dash to Panel,
  ArcMenu (`enterprise`), GTK4 DING, and legacy Big Shot.
- Reinstalled local `26.08.20-1` through `pacman -U`. The legacy enabled list
  remains untouched before logout, and all new bundled extension directories
  are present. At that checkpoint no layout was applied before the post-upgrade
  login migration.

Final clean migration result:

- Repeated from stable `26.08.04-1821` with the exact legacy Hybrid lists and
  icon path, then installed the rebuilt `26.08.20-1` package through pacman.
- First login completed without opening Layout Switcher. Helper build 59
  detached ArcMenu, replaced Dash to Panel with Community Panel, then restored
  ArcMenu after the new panel was live.
- The persisted ArcMenu icon path moved from the retired
  `community-menu@bigcommunity.org` directory to
  `community-menu@communitybig.org`; the button and menu are visible.
- Availability-aware migration kept `big-shot@bigcommunity.org` active because
  `big-shot@communitybig.org` is not installed.
- Final states: current helper, Community Panel, ArcMenu, and legacy Big Shot
  ACTIVE; legacy Dash to Panel INACTIVE; Community Menu INITIALIZED because
  legacy Hybrid continues using ArcMenu.
- Final helper reply: protocol 7, build 59, idle. The migrated lists and icon
  path are present in both live dconf and `settings.gnome`.
- Package check passed all 445 tests. Final test package SHA-256:
  `830e5d7eb833b4cfd11be3f9759bea86cd16cb59b71bf5ccbd1415bdce0c35c9`.
- Remaining journal errors are external: the user-local Copyous installation
  lacks `highlight.min.js`; portal/Mesa warnings come from the VM session.

### Frosted Glass overview polish (GNOME 50)

- [x] Set the clean-install blur-strength default to 23%.
- [x] Set the material-opacity default and original-layout reset to 37%.
- [x] Make material opacity cover the real 0-100 range.
- [x] Keep wallpaper blur independent from material opacity and accent color.
- [x] Make search provider cards and focused results translucent.
- [x] Cover GNOME 50 `overview-tile` focus and checked app states.
- [x] Apply the same dynamic material to opened application-folder dialogs.
- [x] Compile and deploy both extension-local and system schema copies.
- [x] Verify the five deployed source hashes against the local repository.
- [x] Pass the full local suite: `436 passed`.
- [ ] Reload the GNOME 50 session and complete visual acceptance.

GNOME 50 deployment notes:

- Opacity is supported on GNOME 50; it is not a GNOME 51-only control.
- The ineffective 0% value came from an opaque Shell search theme plus a tint
  actor that could fall behind a recreated wallpaper actor.
- The package intentionally installs the same Frosted Glass schema in the
  extension directory and `/usr/share/glib-2.0/schemas/`; both must be compiled.
- Current deployed hashes: `extension.js`
  `dc63744dda48d4778fb9a13a1b3e8aa18c59d5dc1eb64279087d642dceee3181`,
  `overviewController.js`
  `92b278a533f7c051f91a1862f92c94a02fa15153f84f876f164a2cd47f69abf5`,
  `stylesheet.css`
  `2f49740a30e7cda3d9d8b629b4e616366e1fa2513244ab9fccbdd3888e16490a`,
  schema XML
  `b966c87cc331f7b58d0aef3bcf482aead08ecbcfcf87247d37cd5fed6828bd8e`,
  and `ui/frosted_glass.py`
  `b003be1386e69d0508821550cef71ee53c237ecef531aa1ececf2baa676acfc2`.

### Native panel and dock replacement roadmap

Goal: remove runtime dependence on Dash to Dock and Dash to Panel without a
visible or behavioral regression. The existing layouts remain authoritative
references until their replacements pass side-by-side GNOME 50 validation.

Covered layouts:

- BigGnome: bottom floating dock. First implementation target.
- G-Unity: left dock.
- Classic: bottom taskbar and system panel.
- Desk UX: bottom taskbar and system panel.
- Hybrid: bottom taskbar and system panel.
- Minimal: preserve its current near-native behavior; expose only applicable
  controls.

Architecture decisions:

- Add a dedicated bundled Shell extension. Do not grow the switch helper into
  a dock/taskbar runtime.
- Start Community Dock from the packaged Dash to Dock 106 code already used by
  GNOME 50 and present on the GNOME 51 beta VM. Preserve GPL-2.0-or-later,
  original attribution, and upstream history.
- Keep actor geometry, favorites, running applications, click actions,
  previews, workspace scrolling, intellihide, multi-monitor behavior, mounts,
  trash, and launcher integration equivalent before simplifying internals.
- BigGnome and G-Unity are accepted on Community Dock. The external Dash to
  Dock package, runtime UUID, and package dependency are removed.
- The `Panel and Dock` sidebar page owns live opacity and visibility controls.
  Structure/position and running-indicator selection remain later phases.
- Replace Dash to Panel separately after Community Dock is stable. Classic is
  explicitly in scope together with Desk UX and Hybrid.

Compatibility policy:

- GNOME 50 is the live acceptance target.
- Every bundled Shell extension must declare and pass syntax/API checks for
  GNOME 50 and 51.
- A `shell-version` entry is not proof of compatibility. GNOME 51 requires a
  live smoke test on the 51 VM after the GNOME 50 milestone is stable.
- The GNOME 51 VM currently reports `GNOME Shell 51.beta`; its packaged Dash to
  Dock 106 declares Shell 45 through 51. This supports the fork baseline but
  does not validate Layout Switcher helper behavior on 51.

BigGnome parity baseline from `biggnome.txt`:

- Bottom dock, 39 px maximum icon size, 90% maximum length, multi-monitor.
- Fixed 77% black background, compact theme, custom alpha range.
- Intellihide for focused-application windows, fullscreen autohide.
- Pressure reveal threshold 100, 100 ms hide delay, 500 ms animation.
- Click minimizes or opens previews; wheel switches workspaces.
- Mounts hidden; primary monitor preferred.
- Running indicators are selectable: 6 x 6 dot, 18 x 4 Hybrid line, or Desk UX
  line (8 x 3 unfocused and 18 x 3 focused). Focused uses the Shell accent;
  unfocused uses neutral gray.

Initial implementation checklist:

- [x] Record Classic and all other layout coverage.
- [x] Inventory the current BigGnome Dash to Dock settings.
- [x] Confirm the packaged baseline is Dash to Dock 106 on GNOME 50 and 51 beta.
- [x] Vendor the licensed baseline as Community Dock with a distinct UUID.
- [x] Add Community Dock to helper/applier lifecycle ownership.
- [x] Switch only BigGnome to Community Dock; keep rollback available.
- [x] Add package/schema and static regression contracts.
- [x] Install reviewed files on GNOME 50 and verify hashes.
- [x] Restart the graphical session with approval to load helper build 54.
- [x] Validate exact BigGnome behavior on GNOME 50.
- [x] Obtain user parity approval before starting G-Unity.

First implementation evidence:

- New UUID: `community-dock@communitybig.org`, version 1.
- Core baseline: packaged Dash to Dock 106, GPL-2.0-or-later.
- `docking.js` and `dash.js` hashes are identical on GNOME 50, GNOME 51 beta,
  the local fork, and the GNOME 50 deployment.
- The existing `org.gnome.shell.extensions.dash-to-dock` schema is bundled so
  current settings migrate without value conversion or visual drift.
- BigGnome and G-Unity enable Community Dock. No layout references the external
  Dash to Dock UUID.
- Helper deployment marker advanced from build 53 to 54.
- Focused integration suite: `125 passed` for the first slice; indicator and
  panel/dock contracts pass independently.
- Full suite after the G-Unity migration: `407 passed, 1 known unrelated failure` in
  `test_app_grid_menu_uses_monitor_center_anchor`.
- JSON, schema, Python, PKGBUILD, and all bundled JavaScript syntax checks pass.
- GNOME 51 beta `messageTray.js` retains `_bannerBin` with the same X/Y
  alignment API used by notification build 53. Notification positioning is
  source-compatible with 51 beta; the complete helper still needs live 51
  smoke testing before release certification.

GNOME 50 local/remote SHA-256:

- Community Dock `docking.js`:
  `07b9376d63f718812d2a7b701eb2258be1154fa1b9069bc036d8c4f1b8f0d3f8`
- Community Dock `dash.js`:
  `2a561992aa912a502464133437f30d7f63d7b29ef8f0ffe7a88b7460638a60f1`
- Community Dock `metadata.json`:
  `34d1e27213e7194bb2703813684be2d84f880f7d0bc606888c22db8b6eb9fbc8`
- Helper build 54 `extension.js`:
  `1164a1c2b5c7cfe885ddad66321361ee81a67703ace77040f1492b3cd2e373fe`
- `layout_applier.py`:
  `84abb61add325dd107a4bf4f4ffd020ed24677af27616f11fbdbe71f294a27be`
- `biggnome.txt`:
  `672679fec3640d8f2216e67bfe980875a5fffb48fe54adf50686c9c768acc0f8`

### 2026-08-19 — Persistent indicator and Panel/Dock controls

- [x] Confirm the active BigGnome dock is Community Dock; external Dash to
  Dock remains disabled.
- [x] Move persistent running indicators into the Community Dock stylesheet.
- [x] Set the BigGnome layout to `running-indicator-style='DEFAULT'` so another
  layout cannot leak a drawn-dot style into it.
- [x] Add the `Panel and Dock` sidebar category in the GTK application.
- [x] Add independent 0–100% opacity controls for dock and panel.
- [x] Add always visible, edge-revealed auto-hide, and intelligent hiding for
  both components.
- [x] Preserve current defaults: dock 77% with intelligent hiding; panel 65%
  and always visible.
- [x] Translate the complete UI to pt-BR and compile the catalog.
- [x] Add illustrated Dot, Hybrid line, and Desk UX line choices. Active marks
  use the Shell accent; inactive marks remain gray.
- [x] Install all reviewed runtime files and compile the extension schemas on
  GNOME 50. Local and remote hashes match.
- [x] Restart the GNOME 50 graphical session so the new Shell controller is
  imported.
- [ ] Complete user visual approval and edge-reveal testing.

Implementation notes:

- Panel settings schema: `org.communitybig.panel-and-dock`.
- Future unified runtime schema: `org.communitybig.layout-switcher.runtime`.
  Defaults live in `runtime_settings.py`; only per-layout overrides are persisted.
  `PanelDockSettings` mirrors current Dock/Panel writes during migration.
- Dock controls map to the Community Dock-local Dash to Dock schema; no
  external extension is enabled.
- “Always hidden” is auto-hide, not permanent removal: panel and dock return
  when the pointer reaches their screen edge.
- Panel intelligent hiding checks focused-window overlap and keeps the panel
  accessible from a two-pixel top reveal zone.
- Current GNOME 50 deployment hashes: `indicatorController.js`
  `9b6e9197c346f9fb447fd59bb7e26d38ba9792b139fa15e16e4f844d83e0cd47`,
  `stylesheet.css`
  `b1254b738070c2e80e736ad1d593af96b63f7f7320b74d80d168b93f8904998c`,
  `page_panel_dock.py`
  `aff2c1f73575c6d7376869c24e47ac15789bb6001e902200b8514b477fcebb13`.
- GTK preview geometry uses explicit centered sizes; cross-axis expansion made
  all three drawings appear identical before this correction.
- GNOME 50 GDM restarted with approval at 2026-08-20 00:28. Community Dock is
  ACTIVE, `indicator-style` remains `hybrid`, the native indicator remains
  `DEFAULT`, and the new Shell session journal contains no extension errors.
- Live testing then exposed two runtime races: container-only style ownership
  did not reliably update rebuilt icons, and `WindowTracker.focus_app` lagged a
  newly focused window. The correction assigns the selected style to every app
  icon, listens to `notify::focus-window`, checks the actual focused window,
  and recomputes focus whenever running state changes.
- Current GNOME 50 hashes after the focus/style correction: `appIcons.js`
  `7aa4db7187e4db80396f0555c7dd341dbe107aa92394cf9f9557068da009c523`,
  `stylesheet.css`
  `e6fd2a62bc01c520acfd63985ac909c83fd24aa0ea9768361c686b3bc3e9d560`.
- Theme CSS still retained the native marker geometry in the 00:36 session.
  The final correction writes geometry and accent/neutral color directly to
  each native dot actor on style, focus, and icon-theme updates.
- [x] User accepted the corrected BigGnome behavior and authorized the G-Unity
  phase.

### 2026-08-20 — G-Unity Community Dock migration

- [x] Preserve the authoritative G-Unity left-dock settings.
- [x] Replace only the enabled dock UUID with Community Dock.
- [x] Initially keep external Dash to Dock as rollback; remove it after user
  acceptance.
- [x] Add static contracts for owner, position, geometry, opacity, click,
  scrolling, multi-monitor, and mounts behavior.
- [x] Run focused and full regression suites.
- [x] Install the updated layout dump on GNOME 50 and verify its hash.
- [x] Orient custom indicators to the dock edge; vertical docks swap marker
  geometry and align it to the left/right side.
- [x] Apply G-Unity from Layout Switcher and complete live visual validation.
- [x] Obtain user acceptance for the G-Unity phase.

Preserved baseline: left, fixed, extended height, 39 px maximum icons, 80%
background opacity, multi-monitor, minimize-or-previews click, workspace
scrolling, and hidden mounts. The user-selectable Community Dock indicator
style intentionally owns the native Dash to Dock indicator rendering.

Focused checks: `129 passed`. Full checks: `407 passed, 1 known unrelated
failure` in `test_app_grid_menu_uses_monitor_center_anchor`. JavaScript syntax,
Ruff, and `git diff --check` pass. Installed `g-unity.txt` SHA-256 on GNOME 50:
`59792a74d46eb340f07b346fabda0e4dde97c5ddecf2a24539ce51ce9cd39373`.
Corrected local/remote `appIcons.js` SHA-256:
`98afbb564e996ec3fbb4003306f78369eda31a1941e2d73fc68337627d838af3`.

### 2026-08-20 — External Dash to Dock removal

- [x] Remove `gnome-shell-extension-dash-to-dock` from PKGBUILD dependencies.
- [x] Remove the external UUID from every layout and Shell lifecycle owner.
- [x] Keep the inherited dconf schema path owned by Community Dock.
- [x] Rename the user-facing Frosted Glass target to Community Dock and rebuild
  pt-BR catalogs.
- [x] Run `133` focused tests and the full suite (`408 passed`, one known
  unrelated Community Menu failure).
- [x] Deploy all runtime files to GNOME 50 and verify matching hashes.
- [x] Remove package `gnome-shell-extension-dash-to-dock` from GNOME 50.
- [x] Verify its extension directory is absent and Community Dock remains
  enabled and ACTIVE.

The currently installed `layout-switcher` package was built before this source
change, so Pacman retains its old dependency metadata until the next package
build. The external package was removed with dependency checks bypassed on the
development VM. The next PKGBUILD no longer declares it.

### Community Panel migration — complete on GNOME 50

Goal: replace external Dash to Panel in Classic, Hybrid, and Desk UX without
visible or behavioral drift.

- [x] Inventory the complete Dash to Panel settings in Classic, Hybrid, and
  Desk UX.
- [x] Record shared settings and intentional per-layout differences.
- [x] Confirm the packaged baseline and source-audit GNOME 50/51 targets.
- [x] Vendor the licensed baseline under a distinct Community Panel UUID.
- [x] Add helper, applier, schema, package, and regression ownership.
- [x] Switch Classic layout ownership to Community Panel.
- [x] Switch Hybrid layout ownership to Community Panel.
- [x] Switch Desk UX layout ownership to Community Panel.
- [x] Run static, focused, and full regression checks.
- [x] Install Community Panel and helper build 56 files on GNOME 50.
- [x] Restart the GNOME 50 graphical session with explicit approval.
- [x] Validate Classic on GNOME 50.
- [x] Validate Hybrid on GNOME 50.
- [x] Validate Desk UX on GNOME 50.
- [x] Obtain user acceptance for all three layouts.
- [x] Remove the external Dash to Panel dependency and package after
  acceptance.

Parity includes taskbar position and geometry, grouping, favorites/running
apps, indicators, click/scroll actions, previews, panel elements, clock and
system menus, multi-monitor behavior, transparency, and intelligent hiding.
GNOME 51 remains a declared/source-audited target until its later live phase.

Baseline evidence:

- Both VMs package Dash to Panel `73-1`; core files are byte-identical.
- GNOME 50 reports Shell `50.4`; GNOME 51 reports `51.beta`.
- Upstream metadata declares through Shell 50 only. Community Panel declares
  50/51, but 51 remains uncertified until its later live smoke test.
- New UUID: `community-panel@communitybig.org`; fork version 1, upstream 73.
- GPL-2.0-or-later COPYING, provenance, inherited schema, and 22 compiled
  translations are bundled.
- Classic: bottom 38 px, ungrouped, left taskbar, 100% blue focus highlight,
  segmented indicators, 70% panel opacity.
- Hybrid: 38 px, grouped, centered taskbar, SIMPLE hover animation, 30% focus
  highlight, 3 px segmented indicators, 70% panel opacity.
- Desk UX: bottom 40 px, 3 px margins, grouped centered taskbar, METRO/DASHES
  indicators, black 65% panel.
- Focused migration suite: `139 passed`.
- Full suite: `417 passed`, one known unrelated Community Menu failure.
- GNOME 50 local/remote hashes match: `metadata.json`
  `a4b05eda603b9c4bd279d5e58429c37244e4028443843eb34852b0d52704e430`,
  `panel.js`
  `f1b771a838802bddcd82b2e8e2ce0e3b7af30c40f829c7e68805e49e2fe691a8`,
  `taskbar.js`
  `3b70a094b701291c2b6360d0105e8801610fe841c2120076e94fd1d5091fe427`,
  helper build 55
  `b51cd75e14a21e338cc2b1ebe43525c11fc4a6fe79931144e553dc320f3890bd`.
- The current Shell session does not discover the newly installed system UUID;
  GDM was restarted with approval. The VM is at the login screen; post-login
  extension discovery and helper build verification remain pending. External
  Dash to Panel 73 stays installed and disabled for rollback.

Post-login evidence:

- Community Panel is enabled and ACTIVE in Hybrid; external Dash to Panel is
  disabled and INITIALIZED.
- Helper Ping reports protocol 7, build 55, idle.
- Hybrid live settings report panel opacity 70% and intellihide disabled,
  matching its authoritative baseline.
- The Panel and Dock page initially disabled both groups because availability
  checked only Community Dock. Root fix detects components independently:
  dock-only controls remain unavailable, while Community Panel opacity and
  visibility controls are active and map to its inherited schema.
- Community Panel visibility mapping: intellihide off = always visible;
  intellihide on without window proximity = always hidden/edge reveal;
  intellihide on with focused-window proximity = intelligent.
- UI correction checks: `118 passed`; full suite: `419 passed`, one known
  unrelated Community Menu failure.
- Corrected UI was installed and the app relaunched without Shell restart.
- A follow-up found the indicator selector still inherited the dock group's
  availability. For Community Panel layouts, that group is now presented as
  `Taskbar`; dock-only opacity and visibility rows are hidden, and indicator
  choices remain active.
- Community Panel indicator mapping: Dot = `DOTS/DOTS` at 6 px, Hybrid =
  `SEGMENTED/SEGMENTED` at 3 px, Desk UX = `METRO/DASHES` at 3 px. All use the
  inherited `dot-style-focused`, `dot-style-unfocused`, and `dot-size`
  settings.
- Community Panel locally constrains Desk UX indicator width to match
  Community Dock: 8 px unfocused and 18 px focused. The upstream DASHES/METRO
  renderer was respectively too narrow and full-icon width.
- Desk UX geometry checks: `19 passed`; full suite: `421 passed`, same known
  unrelated Community Menu failure. GNOME 50 local/remote `appIcons.js` hash:
  `184121d5a1ca385e36911fc5d675b23dba646d36ea6c6dcfa144a28c6e39314c`.
  Community Panel reloaded ACTIVE without Shell restart or JavaScript errors.
- GNOME Shell ESM kept the previous `appIcons.js` module cached across the
  extension toggle. The user restarted the session and visually accepted the
  corrected Desk UX geometry. Keep this approved hash unchanged.
- Classic intentionally hides the entire running-indicator selector; its
  ungrouped taskbar entries already communicate application state. Other
  layouts retain their applicable controls.
- Final removal: `gnome-shell-extension-dash-to-panel 73-1` uninstalled from
  GNOME 50; external directory, package hook, patch script, and UUID entries
  are absent. Community Panel remained enabled and ACTIVE.
- Layouts, applier, helper, package dependencies, Community Menu integration,
  Frosted Glass labels, and gettext catalogs now reference only Community
  Panel. Focused migration suite: `199 passed`; full suite: `421 passed`, same
  known unrelated Community Menu failure.
- The installed development package database still contains its pre-migration
  dependency list because it predates the current PKGBUILD. The next package
  build/install clears that metadata; runtime files and source are already
  clean. Helper build 56 and Community Menu's new module load on the next
  session because GNOME Shell caches ES modules.
- Updated pt-BR source/template/catalogs. Focused checks: `119 passed`; full
  suite: `420 passed`, same known unrelated Community Menu failure.
- GNOME 50 live round trip succeeded: Hybrid -> Desk UX -> Hybrid. Community
  Panel remained ACTIVE. Local/remote hashes match for
  `panel_dock_settings.py` (`8a249bb80adcbe4003e3c7794c1289a0790ce637642b7a62b20285c889a12e09`)
  and `page_panel_dock.py`
  (`5b1f05b8041a2058f72804d69fc5b1c8bbdc8515ebae47e788f0b3696206f07f`).

### 2026-08-19 — Hybrid menu preview and default badge

- [x] Interpret the annotated GNOME 50 screenshot.
- [x] Keep Classic and Desk-UX preview geometry unchanged.
- [x] Align the Hybrid header block with its narrower left category column.
- [x] Reduce the Hybrid left category column from 31 px to 27 px.
- [x] Remove the Hybrid footer's decorative left rectangle.
- [x] Move the Hybrid footer action dots to the left.
- [x] Make the `Default` badge background explicitly translucent at 50% alpha.
- [x] Add focused source-level regression contracts.
- [x] Run focused tests and formatting/lint checks.
- [x] Copy only the changed runtime files to the GNOME 50 VM.
- [x] Verify remote files match local hashes.
- [x] Relaunch the installed application on GNOME 50 without restarting Shell.
- [x] Inspect the rendered result visually on GNOME 50.
- [x] Obtain user visual approval from the GNOME 50 result.

Implementation details:

- Hybrid preview uses one `rail_width = 27` value for the top user block and
  category column, keeping their right edges aligned.
- `_build_preview_categories()` now accepts a keyword-only width with the old
  31 px default, so Classic stays unchanged.
- `_build_preview_footer(user=False)` no longer creates a divider and aligns the
  action dots at the start. The `user=True` Desk-UX path remains right-aligned.
- `.menu-style-default` uses `alpha(@accent_bg_color, 0.50)`.

Validation evidence:

- Focused test: `12 passed in 0.03s`.
- Focused Ruff lint: passed.
- Focused Ruff format check: passed.
- Python byte compilation: passed.
- Full suite: `383 passed, 1 failed`. The unrelated failure is
  `test_app_grid_menu_uses_monitor_center_anchor`; its source contract expects
  a Desk-UX string absent from the current `community-menu/menu.js`.
- Full Ruff: six pre-existing findings outside this task's files.
- GNOME 50 reports `GNOME Shell 50.4`.
- Remote/local SHA-256 `page_desktop.py`:
  `70724f505a2dcc43641e832910f80f84ddb2fd50aefea55bd38d638721d1f9f2`.
- Remote/local SHA-256 `styles.py`:
  `539e637047f0e9aa1d594e21fac668fbcd410ae623fedad07144c7776a56821b`.
- App relaunched successfully as PID `87550`; transient service active with no
  startup error. Visual approval remains pending.
- Automated screenshot was blocked by GNOME Shell with
  `org.freedesktop.DBus.Error.AccessDenied`; inspect the already-open VM window.

### 2026-08-19 — Normalize Copyous across layouts

- [x] Compare Copyous sections in every layout against BigGnome.
- [x] Replace divergent settings in Classic, Desk-UX, G-Unity, Hybrid, and Minimal.
- [x] Preserve BigGnome as the canonical source without modifying its block.
- [x] Add a regression contract requiring exact section equality.
- [x] Run focused tests: `18 passed in 0.04s`.
- [x] Run focused Ruff lint: passed.
- [x] Run full suite: baseline unchanged at `383 passed, 1 unrelated failure`.
- [x] Deploy the five changed layout dumps to GNOME 50.
- [x] Verify every installed Copyous block is identical to BigGnome.
- [x] Verify local and remote hashes match.
- [x] Normalize the active Hybrid settings and reload only Copyous.
- [x] Verify Copyous is `ACTIVE` with history 70 and `Super+V`.
- [x] Verify the active settings were persisted by `dconf-sync-gnome.service`.
- [x] Obtain user confirmation that `Super+V` opens Copyous after the reload.

Canonical shipped block:

```ini
[org/gnome/shell/extensions/copyous]
history-length=70
open-clipboard-dialog-shortcut=['<Super>v']
paste-on-copy=false
```

Copyous 2.0.1 migrates the deprecated `paste-on-copy=false` user value to
`swap-copy-shortcut=true` and resets `paste-on-copy` to its default. Therefore
the effective live state after enabling the extension matches BigGnome but is
persisted using the new key.

The GNOME 50 VM contains both system and per-user Copyous installations. GNOME
Shell currently loads `/home/tales/.local/share/gnome-shell/extensions/` and
explicitly ignores the system copy. Do not remove either installation as part of
layout normalization; handle that separately only if the user requests it.

Remote/local layout hashes:

- `classic.txt`: `a860a1bf5be24df628bf0e8f4207a4b34b17d584ede05a824b6060efef57dfb3`
- `desk-ux.txt`: `a4d9d05711dfeb99f08da064326d73c86cd7835946b9c7a25aa48094099a4d2a`
- `g-unity.txt`: `0697143a1456941e892c912e0978591bfb83abad92e6a764b82b21836c3ce950`
- `hybrid.txt`: `e16fa1e6fb20cbf922604bc2e0c999124e4f4d300a3d1ec80dc680cece2170fc`
- `minimal.txt`: `e8a30ab5f26581c272370567f65c76024c152e90682e89b348fb3cbc5b5755e7`

### 2026-08-19 — Desk-UX taskbar indicator colors

- [x] Preserve Desk-UX `METRO` focused and `DASHES` unfocused geometry.
- [x] Add Desk-UX to the helper's native accent panel path.
- [x] Reuse Hybrid's desaturation for the unfocused indicator.
- [x] Keep `HYBRID_INDICATOR_SCALE = 0.8` exclusive to Hybrid.
- [x] Force scale `1` for Desk-UX so DTP owns its existing sizes.
- [x] Advance the helper deployment marker from build 51 to 52.
- [x] Update focused regression contracts.
- [x] Focused helper checks: `35 passed`, Ruff clean, JavaScript syntax valid.
- [x] Initial full suite: baseline unchanged at `383 passed, 1 unrelated failure`.
- [x] Copy `extension.js` to the GNOME 50 VM and verify its SHA-256.
- [x] Attempt a non-disruptive helper self-reload.
- [x] Restart GDM with explicit user approval.
- [x] Complete graphical login and verify helper `Ping` reports build 52.
- [x] Switch to Desk-UX and identify the first runtime result as incorrect.
- [x] Trace the failure to `Desk-UX` versus canonical `Desk UX` label spelling.
- [x] Fix `_LAYOUT_DISPLAY_NAMES["desk-ux"]` at the Python source.
- [x] Add a regression test for the canonical helper label.
- [x] Run 100 focused tests successfully after the label fix.
- [x] Run final full suite: `384 passed, 1 unrelated failure`.
- [x] Deploy `layout_applier.py` and verify local/remote SHA-256.
- [x] Reload helper build 52 and restart only the GTK application.
- [x] Obtain visual approval for the corrected focused/unfocused colors.

Implementation: both Hybrid and Desk-UX receive the existing
`layout-switcher-native-accent-panel` class. The focused DrawingArea keeps
`-st-accent-color`; the unfocused DrawingArea receives the same
`Clutter.DesaturateEffect` used by Hybrid. Scale is selected by layout: `0.8`
only for Hybrid, otherwise `1`.

Deployment evidence:

- Local/remote `extension.js` SHA-256:
  `b2ad014813775790f46fd8ddaf513f8e99a33534f1f4325d5ead580bb9ef3b5c`.
- GNOME Shell 50.4 initially retained cached build 51 after `ReloadExtension`.
  The approved GDM restart loaded build 52; `Ping` now reports `"build":52`.
- First Desk-UX apply still showed a white focused indicator. Root cause: the
  applier sent `Desk-UX`, while every helper condition expects `Desk UX` and the
  persisted settings already use `Desk UX`.
- `layout_applier.py` local/remote SHA-256:
  `c929b6fb0ae930429056647dd3a47731ec52760277cf1f489743df71a1e8486b`.
- Helper is `ACTIVE`; the corrected GTK application runs as PID `117027`.
- User confirmed the Desk-UX indicator colors are correct.

### 2026-08-19 — Notification banner position selector

- [x] Add six visual choices to the Desktop page.
- [x] Preserve the requested default for every layout.
- [x] Persist explicit choices per layout.
- [x] Apply alignment through the in-shell helper.
- [x] Send a real preview notification after a successful choice.
- [x] Avoid persistence and preview when Shell application fails.
- [x] Restore the native banner alignment when the helper is disabled.
- [x] Reapply saved/default alignment at login, layout switch, and rollback.
- [x] Add focused regression contracts.
- [x] Update the gettext template and Brazilian Portuguese catalog.
- [x] Copy runtime files to GNOME 50 and verify matching hashes.
- [x] Relaunch the GTK application without startup errors.
- [x] Restart the graphical session and verify helper build 53.
- [x] Fix the selector remaining insensitive after its first request.
- [ ] Verify all six live positions and the click-triggered preview on GNOME 50.
- [ ] Obtain user visual approval.

Requested defaults:

- Classic, Hybrid, Desk UX: `bottom-right`.
- Minimal, BigGnome: `top-center`.
- G-Unity: `top-right`.

Implementation details:

- `Main.messageTray._bannerBin` keeps the stock GNOME banner, animation, and
  dimensions. The helper changes only `x_align` and `y_align`.
- `notification_positions` stores stable position IDs by canonical layout
  label. Missing or invalid entries fall back to the layout default.
- The GTK page calls `SetNotificationPosition` before writing settings. On
  success it sends `Gio.Notification` after 200 ms so the new alignment is
  already active.
- Helper deployment marker advanced from build 52 to 53. GNOME Shell 50 keeps
  the old ES module cached after extension reload, so graphical-session restart
  approval is required before live validation.

Validation evidence:

- Focused suite: `46 passed, 1 warning`.
- Full suite: `390 passed, 1 known unrelated failure` in
  `test_app_grid_menu_uses_monitor_center_anchor`.
- Focused Ruff lint and formatting: passed.
- Python byte compilation: passed.
- JavaScript syntax check: passed.
- Brazilian Portuguese `msgfmt --check --check-format`: passed.
- Other PO files were not mass-merged: the stale catalogs would have caused an
  unrelated 24,402-line rewrite. They safely fall back to the English msgids.
- Installed app restarted as PID `120422` without startup errors.
- Follow-up focused suite after the sensitivity fix: `47 passed, 1 warning`.
- Runtime evidence: helper build 53 reports `bottom-left`; settings persist
  `{'Desk UX': 'bottom-left'}`.
- Corrected `page_desktop.py` local/remote SHA-256:
  `35d310ec1a93adb195433a9a8be2f8be35cf9544b3ccb72991dc570cd08bf86d`.
- Corrected application restarted as PID `157009`.

Local/remote SHA-256:

- `page_desktop.py`: `35d310ec1a93adb195433a9a8be2f8be35cf9544b3ccb72991dc570cd08bf86d`
- `styles.py`: `c1ba1be712d2db1adf08a0fa1126d8a746c105264b9c04edb3279a0314999725`
- `helper_client.py`: `6929d32ccfc3eb375f234de81883b6b3bb6e3f2b1646ae1ccabfececc6e944c1`
- helper `extension.js`: `fc6cdd156d6fa03944ab43bd860b602986e6cd2a0fed889ea58302231bdefd67`
- pt_BR `layout-switcher.mo`: `67da3561c1b30d9c7e1dc37ed076cb5032022e13cb5eacac06db20d73fb968b2`

## Validation protocol

Run focused checks first:

```bash
pytest -q tests/test_desktop_icons.py
ruff check usr/share/layout-switcher/ui/page_desktop.py \
  usr/share/layout-switcher/ui/styles.py tests/test_desktop_icons.py
ruff format --check usr/share/layout-switcher/ui/page_desktop.py \
  tests/test_desktop_icons.py
```

For changes that can affect layout switching or bundled extensions, also run:

```bash
pytest -q
ruff check .
ruff format --check .
```

Record exact pass/fail counts and any blocked check below. Never describe an
unexecuted check as passing.

## GNOME 50 deployment protocol

1. Validate locally.
2. Stage only the changed runtime files under a unique directory in `/tmp` on
   the VM.
3. Inspect staged paths.
4. Copy regular files with `sudo install`, or copy directory *contents* to the
   exact destination. Never run `cp -a staged/usr /` (or the equivalent for
   `etc`): it can replace the ownership of `/usr`, `/etc`, and their shared
   directories with the staging user's ownership.
5. Compare local and remote SHA-256 hashes.
6. Restart only the affected application. A Shell or display-manager restart is
   unnecessary for Python UI/CSS-only changes.
7. Capture evidence or inspect the running UI before marking deployment done.

For the active task, the runtime deployment files are:

```text
usr/share/layout-switcher/ui/page_desktop.py
usr/share/layout-switcher/ui/styles.py
usr/share/layout-switcher/helper_client.py
usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/extension.js
usr/share/locale/pt_BR/LC_MESSAGES/layout-switcher.mo
```

Do not deploy `tests/test_desktop_icons.py` or this handoff document into
`/usr/share/layout-switcher/`.

GNOME 50 recovery note (2026-08-22): a broad archive copy left `/`, `/etc`,
`/usr`, `/usr/bin`, and `/usr/share` owned by `tales`. `systemd-tmpfiles` then
rejected unsafe path transitions, `/tmp/.X11-unix` was created by the GDM
greeter, and user login aborted while starting XWayland. Ownership was restored
non-recursively to `root:root`, the X11 socket directory was restored to mode
1777, and `systemd-tmpfiles --create` completed normally.

## Known review follow-ups

These items were identified during the broader review and are not part of the
current visual patch. Revalidate before editing because the worktree is evolving.

- [ ] Audit whether apply success can be reported before all helper operations
  have genuinely succeeded.
- [ ] Audit snapshot identity handling around `layout_id`.
- [ ] Reconcile package/application/extension version drift only at release time.
- [ ] Keep GNOME 51 compatibility and external extension failures deferred until
  the GNOME 50 milestone is accepted.
- [ ] Run and record a fresh full-suite baseline after the current migration
  settles.

## Decision log

### 2026-08-19

- GNOME 50 selected as the only active compatibility target.
- GNOME 51 deferred until the expected 2026-09-15 release.
- Hybrid visual correction kept inside the Python preview builder and app CSS;
  no menu backend or layout dump changes.
- VM passwords intentionally excluded from the repository.
- BigGnome selected as the exact Copyous configuration reference for all layouts.
- Active Hybrid repair reloads only Copyous; no full layout or Shell restart.
- Desk-UX reuses Hybrid indicator colors but explicitly keeps scale `1`.
- Notification positions are stored per layout; defaults remain effective until
  a user explicitly overrides that layout.
- Do not restart GDM to activate helper build 53 without user approval.

## Update template

Append one entry per completed change:

```markdown
### YYYY-MM-DD — Short task name

- Request:
- Files changed:
- Root cause:
- Fix:
- Focused checks:
- Full checks:
- GNOME 50 deployment/hash evidence:
- Visual result/user decision:
- Remaining risk or next step:
```

### 2026-08-20 — Desk UX Classic submenu direction and theme

- Request: open Classic category submenus on the right and match the light menu
  theme when Desk UX is active.
- Files changed: Community Menu `menu.js`, `layouts/baseLayout.js`,
  `layouts/appListLayout.js`, `sections.js`; focused static test updated.
- Root cause: `St.Side.RIGHT` describes an arrow on the popup's right edge, so
  the popup was placed left. The category popup is attached independently to
  `Main.uiGroup`, so it did not inherit `community-menu-light`.
- Fix: pass the normalized desktop layout into the menu layout. Only Desk UX's
  Classic menu requests a left-edge arrow (popup on the right) and synchronizes
  the parent popup's light style before opening.
- Focused checks: JavaScript syntax passed for all four changed modules; 18
  Community Menu tests passed, with the known unrelated center-anchor test
  deliberately deselected.
- GNOME 50 deployment/hash evidence: installed under `/usr/share`; local and
  remote hashes match: `menu.js` `43970f3f...`, `sections.js` `a25e775b...`,
  `baseLayout.js` `eb7ac45b...`, `appListLayout.js` `7e65835b...`.
- Visual result/user decision: pending VM test.
- Remaining risk or next step: restart the Shell session, then visually confirm
  the right-side light submenu. GNOME caches extension ES modules.

### 2026-08-20 — Desk UX unfocused indicator color

- Request: running applications without focus must use gray; only the focused
  application uses the theme color.
- Files changed: Community Panel `appIcons.js`; focused contract test added.
- Root cause: Desk UX selected `METRO/DASHES` geometry but inherited the theme
  dot color for both focused and unfocused drawing layers.
- Fix: the Desk UX unfocused layer now uses the same neutral gray as Community
  Dock (`rgba(160, 160, 168, 0.72)`). Focused color and all geometry are intact.
- Focused checks: JavaScript syntax passed; 20 Community Panel and Panel/Dock
  tests passed.
- GNOME 50 deployment/hash evidence: local and remote `appIcons.js` hash
  `083592c774860abec4860dc02acd3eae736ed325ad74184a81a7294e9d478da7`.
- Visual result/user decision: pending session restart and VM confirmation.
- Remaining risk or next step: GNOME caches extension modules; restart the
  session before visual validation.

### 2026-08-20 — Hybrid indicator geometry inside Desk UX

- Request: Hybrid focused and unfocused indicators must keep the same length
  when selected in Desk UX.
- Files changed: Community Menu `extension.js`; obsolete test expectations
  removed.
- Root cause: Community Menu still traversed Community Panel actors and forced
  the focused drawing area to half width based only on the desktop layout. It
  ignored the indicator style selected by the user.
- Fix: removed indicator geometry ownership from Community Menu. Community
  Panel now exclusively renders Dot, Hybrid, and Desk UX geometry.
- Focused checks: JavaScript syntax passed; 18 Community Menu tests passed with
  one known unrelated test deselected; 20 Community Panel/Panel-Dock tests
  passed.
- GNOME 50 deployment/hash evidence: local and remote Community Menu
  `extension.js` hash
  `5628f1be986365049953e2020478772881bd81d15f8a3aa20f87531906ce89e6`.
- Visual result/user decision: pending session restart and VM confirmation.
- Remaining risk or next step: restart the session, then confirm equal Hybrid
  lengths and unchanged Desk UX 18/8 px geometry.

### 2026-08-20 — Hybrid fixed-length renderer correction

- Request: Hybrid indicators must not span the full taskbar button width.
- Files changed: Community Panel `appIcons.js`; geometry contract extended.
- Root cause: after removing Community Menu's invalid focused-only resize, the
  upstream `SEGMENTED` renderer expanded both layers to the full actor width.
- Fix: Community Panel now renders `SEGMENTED/SEGMENTED` at a fixed 18 px for
  both focus states. Desk UX remains 18 px focused and 8 px unfocused.
- Focused checks: JavaScript syntax passed; 21 Community Panel/Panel-Dock tests
  and 18 Community Menu tests passed; one known unrelated test deselected.
- GNOME 50 deployment/hash evidence: local and remote `appIcons.js` hash
  `9aba98a769b734620e12807c9ad4f4050f29256093f3faf53bb48af059ec9e22`.
- Visual result/user decision: pending session restart and VM confirmation.
- Remaining risk or next step: restart session; confirm Hybrid 18/18 and Desk
  UX 18/8 visually.

### 2026-08-20 — Stable indicator allocation across layouts

- Request: the same Desk UX indicator style must have identical geometry when
  selected from Hybrid or used by the Desk UX layout.
- Files changed: Community Panel `appIcons.js`; allocation contract extended.
- Root cause: screenshots measured 14/6 px after a live style change in Hybrid,
  versus the correct 18/8 px after Desk UX rebuilt the panel. Upstream animation
  temporarily allocated drawing surfaces smaller than the custom geometry.
- Fix: custom Hybrid and Desk UX drawing areas now enforce minimum lengths
  before animation: Hybrid 18/18 px and Desk UX 18/8 px.
- Focused checks: JavaScript syntax passed; 21 Community Panel/Panel-Dock tests
  and 18 Community Menu tests passed; one known unrelated test deselected.
- GNOME 50 deployment/hash evidence: local and remote `appIcons.js` hash
  `df4445ec9577d045393532f2d6ec512c3d0f913c7f771560972a8f02e2621fe0`.
- Visual result/user decision: pending session restart and cross-layout test.
- Remaining risk or next step: restart session; select Desk UX style in Hybrid,
  then switch to Desk UX and compare 18/8 px geometry.

### 2026-08-20 — Focus-layer overlap regression

- Request: restore distinct Hybrid and Desk UX rendering, including gray
  unfocused Desk UX indicators.
- Files changed: Community Panel `appIcons.js`; focus-layer contract tightened.
- Root cause: the minimum-allocation guard assigned nonzero size to both the
  focused and unfocused drawing layers. The focused theme-colored layer then
  covered the gray layer, making both styles appear equal.
- Fix: enforce minimum size only on the currently visible focus layer. Hidden
  wide layers retain size zero. Hybrid stays 18/18; Desk UX stays 18/8 and its
  unfocused layer uses neutral gray.
- Focused checks: JavaScript syntax passed; 21 Community Panel/Panel-Dock tests
  and 18 Community Menu tests passed; one known unrelated test deselected.
- GNOME 50 deployment/hash evidence: local and remote `appIcons.js` hash
  `73ae6b2bb5724b142a511e480308fff588fedd5f025577734bfeb5932a3238b4`.
- Visual result/user decision: pending session restart and confirmation.
- Remaining risk or next step: restart session and validate all three choices
  before further indicator changes.

### 2026-08-20 — Layout-independent single-layer indicators

- Request: selecting the same indicator style must render identically in Hybrid
  and Desk UX. Four screenshots established Desk UX as the correct reference.
- Files changed: Community Panel `appIcons.js`; renderer contracts updated.
- Root cause: live style changes in Hybrid reused the upstream pair of animated
  drawing areas, while applying Desk UX rebuilt them. Their allocations and
  focus layers therefore diverged by layout.
- Fix: Hybrid and Desk UX styles now use one expanded drawing area. It reads
  current focus on repaint and directly renders Hybrid 18/18 or Desk UX 18/8.
  Unfocused custom indicators use neutral gray; Dot keeps the native renderer.
- Focused checks: JavaScript syntax passed; 21 Community Panel/Panel-Dock tests
  and 18 Community Menu tests passed; one known unrelated test deselected.
- GNOME 50 deployment/hash evidence: local and remote `appIcons.js` hash
  `bfa61bc9f4cff3c89db54965070b87b8f43ed1f928c305b5ab65ddd7f6e5ff9b`.
- Visual result/user decision: pending session restart and four-state replay.
- Remaining risk or next step: restart session; repeat Hybrid+Hybrid,
  Hybrid+Desk UX, Desk UX+Desk UX, and Desk UX+Hybrid comparisons.

### 2026-08-20 — Hybrid indicator clipping

- Request: custom indicators must match Desk UX geometry when rendered by the
  Hybrid layout.
- Files changed: Community Panel `appIcons.js`; clipping contract added.
- Root cause: pixel measurement showed Hybrid clipping the focused line to
  14 px, while Desk UX rendered the intended 18 px. The single-layer canvas was
  correct, but its parent actor had only 14 px available in Hybrid.
- Fix: custom indicator containers enforce 18 px minimum width, or minimum
  height for vertical panels. Dot and non-custom styles remain unchanged.
- Focused checks: JavaScript syntax passed; 21 Community Panel/Panel-Dock tests
  and 18 Community Menu tests passed; one known unrelated test deselected.
- GNOME 50 deployment/hash evidence: local and remote `appIcons.js` hash
  `d8e2f90d46cc077e46c7484fb17fd8abcf08cf5f6c33d44c5390485f41a33012`.
- Visual result/user decision: pending session restart and screenshot measure.
- Remaining risk or next step: after restart, measure Hybrid active at 18 px
  and Desk UX inactive at 8 px before accepting.

### 2026-08-20 — Centered compensation for clipped indicator canvas

- Request: Desk UX indicator geometry must be identical in Hybrid and Desk UX.
- Files changed: Community Panel `appIcons.js`; focused regression test updated.
- Root cause: post-restart screenshots confirmed the Hybrid drawing canvas was
  still 14 px while Desk UX provided 18 px. A CSS minimum on the child actor did
  not enlarge the parent allocation.
- Fix: custom indicators draw within the available canvas and apply a centered
  axis-only actor scale when the requested length is clipped. Hybrid remains
  18/18 px; Desk UX remains 18/8 px. Colors and native Dot rendering are intact.
- Focused checks: JavaScript syntax passed; 21 Community Panel/Panel-Dock tests
  and 18 Community Menu tests passed; one known unrelated test deselected.
- GNOME 50 deployment/hash evidence: local and remote `appIcons.js` hash
  `c96b978d476b9618cb7490e5079591db479efb87c10ef4b517df60fe49346b96`.
- Visual result/user decision: user confirmed the cross-layout indicator now
  appears correct after the GNOME Shell session restart.
- Remaining risk or next step: none for this indicator regression.

### 2026-08-20 — Minimal disables Panel and Dock navigation

- Request: controls unused by Minimal must not remain available in the app.
- Files changed: `ui/window.py`, `ui/page_layouts.py`; focused test added.
- Root cause: the page disabled its internal groups when both Community Dock
  and Community Panel were absent, but the sidebar entry remained selectable.
- Fix: Minimal disables the Panel and Dock navigation row. Applying or restoring
  another layout refreshes capabilities immediately and re-enables the row.
- Focused checks: Python syntax passed; 28 Panel/Dock and layout-file tests
  passed; diff check passed.
- GNOME 50 deployment/hash evidence: local and remote `window.py` hash
  `499fc9984f17dd236b9ba1f4c5ee9c16ecd4d1a030ed9675d0bfca05456b26c4`;
  local and remote `page_layouts.py` hash
  `78d9c0afd6f9e99ab1b50848d98cead40a4aba6a850fb40acf89f197b63ee7b8`.
- Visual result/user decision: pending app restart and confirmation.
- Remaining risk or next step: close and reopen Layout Switcher in Minimal;
  confirm Panel and Dock is disabled, then switch layouts and confirm re-enable.

### 2026-08-20 — Classic focus highlight follows GNOME accent

- Request: Classic active task button must use the selected GNOME accent; it
  remained blue after selecting green.
- Files changed: Layout Switcher Helper `extension.js`; focused test updated.
- Root cause: `_syncClassicFocusHighlight()` opened the Community Panel schema
  as a global schema. It is extension-local, so GNOME Shell logged `schema ...
  not found` and retained the layout baseline `#1c71d8`.
- Fix: helper build 57 obtains the settings through the active Community Panel
  extension object's `getSettings()`. The accent change signal remains the
  trigger, and the solution uses GNOME 50/51-compatible extension APIs.
- Focused checks: JavaScript syntax passed; 63 helper, Community Panel, and
  theme-manager tests passed; diff check passed. Pytest emitted only unrelated
  temporary-directory cleanup warnings.
- GNOME 50 deployment/hash evidence: local and remote helper hash
  `4bc91bc5640d1adfaa229bc980d09abdb8eaf17772e4b93a892b5614a25fc9bd`.
  The current focus highlight was changed from `#1c71d8` to green `#3a944a`
  for immediate testing.
- Visual result/user decision: pending confirmation.
- Remaining risk or next step: current green should repaint live. Restart the
  session once before testing subsequent accent changes so helper build 57 is
  the running module rather than cached build 56.

### 2026-08-20 — Restore G-Unity actors before layout teardown

- Request: G-Unity → Desk UX must retain the clock and let the taskbar use all
  space up to the systray; the transition hid the clock and clipped app icons.
- Files changed: Layout Switcher Helper `extension.js`, Community Panel
  `panelStyle.js`; focused tests added.
- Root cause: G-Unity-owned actors were restored only after Community Dock was
  disabled and Community Panel was enabled. The log confirmed cleanup touched
  an already-disposed dock actor. Date menu and panel allocation could then be
  attached to stale parents when Desk UX initialized.
- A second exception occurred while Community Panel was being disabled:
  its padding refresh reparented systray buttons after their backing indicator
  had already been destroyed, interrupting panel style cleanup.
- Fix: helper build 58 tears down the G-Unity shell and clears its surface
  classes behind the transition curtain, before disabling any extension. The
  target Community Panel therefore starts from the normal date-menu/systray
  structure and computes the taskbar boundary against the live systray.
  Community Panel now restores inline styles without reparenting status buttons
  during teardown; live setting changes keep the existing refresh behavior.
- Focused checks: JavaScript syntax passed; 49 helper/layout transition tests
  passed; 14 focused helper/Community Panel checks passed; diff check passed.
  Pytest emitted only unrelated temp cleanup warnings.
- GNOME 50 deployment/hash evidence: local and remote helper hash
  `a81f1b15b15c42cdde14d370047a497ef628fa63a1991080686b856938d23383`;
  local and remote `panelStyle.js` hash
  `db2c9ddf2edd11ebb12503eaa8e271df3ebc7d6c454989191d1f1ba5fa79dbb1`.
- Visual result/user decision: pending session restart and transition replay.
- Remaining risk or next step: restart the GNOME 50 session, apply G-Unity,
  then Desk UX. Confirm clock returns and all taskbar icons fit before systray.

### 2026-08-20 — Testing repository release preparation

- Request: make the update safe for users with existing extensions and prepare
  the tree for a package build and commit.
- Session migration: `HelperClient.required_extension_lists()` now migrates
  the legacy helper, Community Menu, and Big Shot UUIDs while preserving the
  enabled/disabled state of unrelated extensions. The autostart guard applies
  this migration before users need to open Layout Switcher.
- External docks/panels: Dash to Dock and Dash to Panel remain installed and
  have no package file conflicts with the bundled Community UUIDs. Applying a
  layout disables the external UUIDs and intentionally updates their shared
  settings branches.
- Packaging: static `pkgver=26.08.20`, `pkgrel=1`; `git` added to
  `makedepends`; `python-pytest` added to `checkdepends`; `check()` runs the
  complete suite. PKGBUILD passes namcap and install scripts pass shellcheck.
- Validation: 431 tests passed. Ruff check/format, JavaScript syntax, strict
  schema compilation, gettext catalogs, desktop files, Python compilation,
  shellcheck, namcap, and diff whitespace checks passed.
- Package staging: `package()` succeeded in a temporary root with 407 files,
  all five bundled Shell extensions, all three compiled local schemas, and all
  required license files (7.6 MiB unpacked staging tree).
- Build workflow: the VCS source follows the repository default branch
  (`main`). Merge/push the release commit to `main` before running `makepkg`,
  or the generated package will not contain the current `dev-talesam` work.
- GNOME 51: metadata and syntax contracts pass, but live GNOME 51 validation
  remains deferred. GNOME 50 is the visually accepted release target.

### 2026-08-20 — Upgrade migration and locale completion

- Upgrade migration now replaces enabled legacy Dash to Dock and Dash to Panel
  UUIDs with the bundled Community Dock and Community Panel UUIDs. Installed
  legacy packages remain untouched. Clean-upgrade validation is still pending.
- Desktop icon activation is layout-owned. Classic and Hybrid enable GTK4-DING;
  BigGnome, Desk UX, G-Unity, and Minimal disable it. Detailed icon settings
  remain preserved across layouts.
- The Layout Switcher template matches all 373 current source messages. All 29
  catalogs contain 373 translated messages with no fuzzy, untranslated, or
  obsolete entries. One LangForge newline-token artifact in Greek was fixed.
- All 29 `layout-switcher.mo` catalogs were rebuilt in their existing locale
  destinations. Placeholder, gettext syntax, and hardcoded-string checks pass.
- Validation: 435 tests passed. Ruff check/format and diff checks pass.
- GNOME 50 login-loop incident was unrelated to this package. GNOME Shell
  aborted XWayland because `/tmp/.X11-unix` was owned by `gdm-greeter`; restoring
  `root:root` and mode `1777` restored login.
- Next: test an upgrade from the previous testing package on a clean GNOME 50
  installation. Confirm the menu remains available at first login and verify
  the six desktop-icon defaults before publishing another package.

## 2026-08-21 — Focused Shell runtime roadmap

- User approved replacing the bundled Dash to Dock and Dash to Panel forks
  incrementally with a focused Layout Switcher-owned Shell runtime.
- All user-facing Dock and Panel settings must exist only in Layout Switcher.
- The runtime remains a GJS extension because Shell actors cannot run in the
  external GTK process. Keep it separate from the D-Bus helper for isolation.
- First new controls: safe dock size/thickness and panel height, saved per
  layout, live-applied, with a restore-default action.
- Keep current icon spacing fixed. The user explicitly rejected a spacing
  control because the accepted value is already correct.
- Product direction: curated Deepin-like controls, strong defaults, and visual
  cards. Do not expose arbitrary alignment, padding, margin, or element order.
- Add an illustrated Dock hover option for the accepted Hybrid-style icon lift.
- Keep Applications, Trash, and mounted-volume visibility at current defaults;
  they are possible future controls, not initial scope.
- Do not start by deleting inherited code. Inventory, test, extract, obtain
  live approval, then remove the replaced code.
- Detailed phases, gates, layout contracts, and candidate settings are in
  `docs/SHELL_RUNTIME_MIGRATION.md`.

## 2026-08-22 — Passive unified runtime foundation

- Added `layout-switcher-runtime@communitybig.org` as the future single visual
  runtime for Dock and Taskbar.
- Build 1 is intentionally passive: it reads the owned runtime schema and maps
  all six profiles, but an explicit gate prevents actor activation.
- Added separate Dock and Taskbar modules under one extension lifecycle.
- Original layout applies now persist the canonical active layout in
  `org.communitybig.layout-switcher.runtime` without requiring the settings
  page to be opened.
- Community Dock and Community Panel remain enabled by the accepted layouts;
  no layout enables the new runtime in this gate.
- Package staging and JavaScript/schema/JSON checks passed. Full suite:
  `478 passed`.
- Installed and hash-verified on GNOME 50 and 51. The new UUID was absent from
  both sessions' enabled-extension lists; no graphical restart was performed.
- `PKGBUILD` was not changed.

### 2026-08-22 — GNOME 50 zero-drift sync and stable migration audit

- Local source and `192.168.128.230` now match by checksum for the application,
  Community Menu, Frosted Glass, helper, unified runtime, Community Dock, and
  Community Panel.
- System copies are `root:root`; deploy only to exact package-owned paths.
  Never copy a staged `usr/` or `etc/` tree over the filesystem root.
- Community Dock and Community Panel remain bundled as internal runtime source
  modules. They are not enabled as standalone extensions and must stay in sync.
- Login migration maps stable Dash to Dock/Panel UUIDs and intermediate
  Community Dock/Panel UUIDs to the unified runtime, preserving unrelated user
  extensions and removing duplicates.
- Migration teardown covers all four retired standalone UUIDs to prevent ghost
  panels or docks on the first upgraded login.
- Validation: focused migration suite `164 passed`; full suite `484 passed`.

### 2026-08-22 — Per-layout indicator ownership checkpoint

- Canonical defaults: BigGnome and Desk UX use Desk UX, Hybrid uses Hybrid,
  G-Unity uses dot, and Classic keeps indicators disabled.
- The unified runtime resolves the active layout override or its default and
  applies it before activating the Dock or Taskbar compatibility module.
- `Apply original` removes only the target layout's runtime overrides, so a
  previous layout cannot contaminate its indicator while other layout
  customizations remain preserved.
- Missing runtime schemas now raise a recoverable Python error instead of
  aborting through `Gio.Settings.new()`.
- Validation: focused suite `133 passed`; full suite `491 passed`; JavaScript
  syntax passed. GNOME 50 deployment hashes match local source for all six
  changed runtime/application files. Live validation requires a session restart.

### 2026-08-22 — Global color-mode ownership

- Layouts never own the user's light/dark choice. Every switch preserves the
  effective live session mode, including changes made outside Layout Switcher.
- The preserved mode also selects the matching `adw-gtk3` and Papient variants;
  target layout files cannot force their saved dark/light variant.
- The global choice applies to applications and icons across all six layouts.
- BigGnome, Desk UX, G-Unity, and Minimal retain their structural dark Shell;
  light mode uses light applications without enabling Light Style over their
  panel/menu CSS.
- Icon-theme and taskbar-label transforms read the transformed target mode,
  not the source layout file.

### 2026-08-22 — Rejected direct Dock lifecycle extraction

- A direct `DockManager` lifecycle inside the unified runtime passed static and
  automated checks but failed the live Classic to BigGnome transition.
- Dock teardown callbacks accessed cleared extension settings and wedged Shell
  D-Bus before `CompleteSwitch`.
- The experiment was fully reverted locally and on GNOME 50. Keep
  `CommunityDockRuntime` as the rollback boundary until teardown ownership is
  isolated and covered by a live transition check.
- The blocked graphical session was terminated cleanly after exact rollback
  hashes were confirmed. Relogin is required once.

### 2026-08-22 — Status icon theme transition refresh

- G-Unity light to Hybrid left JamesDSP's white StatusNotifierItem pixmap on
  the light panel even though the final Papient Light theme was correct.
- Root cause: AppIndicator retained its rendered actor cache across the icon
  theme transition. The existing refresh ran only for live color-mode changes.
- Both layout apply protocols now refresh each live AppIndicator proxy and
  invalidate its icon actor after the target extensions are ready.
- The refresh is in-place. It does not restart applications or reload the
  AppIndicator host, avoiding orphaned tray items.
- Validation: JavaScript syntax passed; focused suite `123 passed`; full suite
  `493 passed`.

## 2026-08-24 — Rejected logical-only G-Unity fullscreen acceptance

- Latest committed checkpoint: `2ca0253`. The accepted live state is the
  uncommitted runtime build 29 working tree.
- GNOME Shell 50 tracks both the native panel and fixed Dock with
  `affectsStruts=true` and `trackFullscreen=true`. Its
  `in-fullscreen-changed` handler hides tracked actors immediately and queues
  region updates before redraw. The nominal work area remains reserved; a real
  fullscreen MetaWindow uses the complete monitor.
- Initial hypothesis: the custom panel policy also reacts to focus, restack,
  and frame changes, so reapplying `always-visible` during the native
  fullscreen transition can show `panelBox` after Shell hid it. Keeping the
  restored `in-fullscreen-changed` observer and fullscreen guard is necessary,
  but later visual evidence proves it is not sufficient.
- The native-only experiment that removed this callback regressed rapid F11
  transitions and remains rejected.
- GNOME 50.4 session started after the restored controller was installed, so
  runtime build 29 contains the on-disk source rather than a cached earlier
  module.
- Logical Brave diagnostics passed one initial cycle, 10 slow non-maximized
  cycles, and 20 rapid maximized cycles. Every sampled fullscreen state reported frame
  `0,0 1280x800`, panel unmapped, and Dock unmapped. Every exit restored panel,
  Dock, and the original normal or maximized frame.
- The GNOME Shell journal contained no entries during the automated test
  window. Final strict runtime audit passed with zero failures and warnings.
- Local and GNOME 50 `dockPanelController.js` SHA-256:
  `f89572cdd24fc46cf4aa81546b5e6b5f6f1ad07f4ff70ff49737d41780bd2b0f`.
- A stale VM-only audit assertion incorrectly required fullscreen actors to set
  `affectsStruts=false`. It was not imported. The reviewed local audit replaced
  it and now matches the VM at SHA-256
  `f980f5fa251134cee26954c1a0ba30c63156781cdd778f19e6c9364b3409c231`.
- Focused Dock/Panel/runtime checks: `76 passed`. JavaScript syntax and diff
  whitespace checks passed.
- BigGnome passed three slow and ten rapid additional F11 frame/panel cycles.
  Its inherited autohide engine keeps the outer Dock container mapped while an
  internal slider retracts, so actor diagnostics alone cannot replace visual
  confirmation that the bottom Dock is absent.
- The complete local suite passed: `528 passed`, with one known PyGI
  deprecation warning.
- G-Unity was restored on GNOME 50 and its strict audit passed. The F11-only
  journal window remained clean. Layout switches exposed existing Copyous and
  AppIndicator teardown errors outside this fullscreen change.
- All seven reviewed files are synchronized by SHA-256 on GNOME 51. Its current
  Shell session still runs cached build 19; logout/login is required before
  build 29 and fullscreen behavior can be validated there.
- This acceptance is rejected. Visual captures later reproduced persistent
  black top/left bands while all recorded logical checks passed.

## 2026-08-24 — Fullscreen compositor-actor race evidence

- GNOME 50 and GNOME 51 both reproduce the defect with runtime build 29 loaded.
- During a visually broken fullscreen state, both report MetaWindow frame
  `0,0 1280x800`, fullscreen window and monitor flags, and unmapped panel and
  Dock. The failure is downstream of strut, work-area, and tracked-chrome state.
- Pixel comparison between broken and correct GNOME 50 captures shows the
  entire Brave surface shifted `+29,+16` and clipped on the right/bottom. This
  is approximately half the G-Unity maximized origin `57,29`.
- GNOME Shell 50 `WindowManager._sizeChangedWindow()` starts size-change
  animation by setting the window actor translation to the source/target
  rectangle difference, then eases translation and scale to their identity
  values. `_sizeChangeWindowDone()` is responsible for removing transitions
  and forcing translation to zero.
- Current evidence identifies an interrupted or incomplete native size-change
  animation: the MetaWindow reaches fullscreen, but its compositor actor keeps
  an intermediate transform. Existing diagnostics cannot observe actor
  translation, scale, or active transitions.
- Next step is diagnostic-only instrumentation of the focused compositor actor.
  Do not change fullscreen policy until a broken visual state captures those
  properties.

## 2026-08-24 — Fullscreen exit configure race isolated

- Runtime build 30 adds diagnostic-only frame, buffer, compositor actor,
  transition, and Shell resize-state telemetry. It does not change behavior.
- A slow exit orders state as follows: `MetaWindow.fullscreen=false`, then
  `monitor.inFullscreen=false` and native chrome returns, then the Wayland
  client commits its normal-size buffer. The final configure trails the
  fullscreen flags by roughly one frame.
- Rapid F11 re-entry inside that interval leaves a maximized window at its
  work-area origin with the monitor-sized `1280x800` frame and buffer. The
  state persists after three seconds with no actor transition, animation,
  `_resizePending`, or `_resizing` entry. The prior incomplete-animation
  hypothesis is rejected.
- G-Unity reproduces as `57,29 1280x800` against work area
  `57,29 1223x771`. BigGnome independently reproduces as
  `0,38 1280x800` against work area `0,38 1280x762`; its Dock does not affect
  struts. Therefore neither the left Dock nor its strut is the root cause.
- A non-maximized Brave window retains its correct frame rectangle while its
  Wayland buffer temporarily remains monitor-sized. A maximized window loses
  the correct frame size until its maximized state is reasserted.
- The actionable fault boundary is the final fullscreen-exit configure, not
  panel/Dock visibility. Keep the restored `in-fullscreen-changed` handler and
  monitor-fullscreen guard. Repair only a maximized post-exit frame that does
  not equal the current work area; never resize arbitrary non-maximized
  windows.

## 2026-08-25 — Fullscreen exit configure repair accepted

- Runtime build 35 preserves the custom `in-fullscreen-changed` observer and
  the fullscreen visibility guard. The rejected native-only experiment remains
  reverted.
- Root cause: rapid re-entry can overtake Brave's final Wayland exit configure.
  Mutter then keeps a monitor-sized frame, buffer, or compositor surface after
  fullscreen flags clear. Panel, Dock, struts, and work area are already
  correct at this point.
- The controller records only the focused window's stable normal frame, buffer,
  and maximized state. After exit settles, it compares frame, buffer, and actor
  geometry with that saved target.
- An inconsistent target receives a bounded native state round trip. Each
  maximize/unmaximize stage waits for a real geometry acknowledgement before
  advancing; this prevents Mutter from coalescing synchronous state calls.
  Non-maximized windows are returned to their exact saved rectangle. The repair
  is cancelled on focus/fullscreen changes and is limited to three attempts.
- GNOME 50 G-Unity passed 10 slow plus 20 rapid cycles from maximized and
  non-maximized states. Fullscreen and restored-normal screenshots have no
  black edge; frame, buffer, and actor targets match. BigGnome passed the same
  rapid path and visual fullscreen check.
- GNOME 51 G-Unity passed 10 slow plus 20 rapid cycles from both states. Every
  slow sample reached `0,0 1280x800` with panel and Dock hidden, then restored
  the exact original geometry. Both post-rapid fullscreen captures have no
  black edge.
- Both VMs finish in G-Unity and pass strict runtime audit with zero failures.
  The SSH-only session-type warning is expected. GNOME 50's current Shell
  journal has no warnings; GNOME 51 has only pre-existing external extension,
  KMS, and cursor warnings.
- Local, GNOME 50, and GNOME 51 SHA-256: `dockPanelController.js`
  `349f9d9094d40287b43d7b161a45aaa7ef851f1cb69256aab26f5476fd9154e5`;
  `runtimeController.js`
  `a5b7759346388af7cefecb09dcec7c957a439cec86cfaf9ff755457055a1e02f`.
