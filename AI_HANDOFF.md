# AI handoff — Layout Switcher

> Active continuation document. Read this file before changing the repository.
> Update the checklist and decision log after every verified task.
> Last updated: 2026-08-27.

## Current objective

Finish the unified Shell runtime migration with GNOME 50 and GNOME 51 parity.
Validate each bounded slice on GNOME 50 before GNOME 51 unless the user changes
the order explicitly.

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
- Preserve GNOME 50 behavior while adding GNOME 51 compatibility.

## Test environments

| Target | SSH | Priority | State |
|---|---|---:|---|
| GNOME 50 | `tales@192.168.128.230` | Active | Current validation target |
| GNOME 50 clean migration | `tales@192.168.128.206` | Verified | Stable Hybrid upgraded in place; automatic migration accepted |
| GNOME 51 | `tales@192.168.128.114` | Active | Compatibility validation target |

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

## 2026-08-25 — Fullscreen paint-state race reopened

- Runtime build 40 reproduces a persistent visual offset after rapid F11
  cycles on GNOME 50. Logical-only acceptance remains invalid.
- In the broken state, MetaWindow frame/buffer, Meta.WindowActor,
  MetaSurfaceContainerActorWayland, and MetaSurfaceActorWayland all report
  `0,0 1280x800`. Panel and fixed Dock are unmapped.
- The rendered Brave content is nevertheless shifted and clipped. From a
  G-Unity maximized origin of `57,29`, the black edges are about `29,15`,
  matching a stale scaled paint origin rather than any strut or actor geometry.
- A coherent fresh BigGnome session passes the same test. A direct test apply
  that skipped the UI's `settings.json` persistence created a hybrid session;
  that harness artifact is rejected and the VM state was repaired.
- Next fix boundary: refresh the focused WindowActor shaped-texture size after
  the fullscreen buffer commit. Do not change fullscreen visibility policy or
  broaden the existing exit geometry repair.
- Build 41's single 80 ms refresh fixes G-Unity on both Shell versions, but
  GNOME 51 BigGnome still reproduces a 19 px top edge after 20 rapid cycles.
  Its normal origin is `y=38`, confirming that BigGnome's final client commit
  can arrive after the first refresh. The refresh must be bounded and retried.
- Build 42 retries size invalidation three times. BigGnome still keeps the
  19 px edge. Mutter documents `invalidate_size()` as preferred-size/relayout
  invalidation; it does not invalidate already-painted content. The next
  candidate must invalidate `Clutter.Content` itself.

## 2026-08-25 — Dock runtime migration and fullscreen paint repair accepted

- Runtime build 43 owns Dock actor construction and lifecycle directly.
  `DockSurfaceManager` replaces the inherited `DockManager` boundary. Teardown
  is exact reverse order: panel controller, indicator controller, surface.
- Executable Community Dock modules moved under the unified runtime `dock/`
  tree. The old Community Dock directory now contains only schemas, stylesheet,
  media, license, and provenance. It has no metadata, entry point, or JavaScript.
- The controller preserves its `in-fullscreen-changed` observer and fullscreen
  visibility guard. The rejected native-only callback removal was not repeated.
- Root cause of the remaining black edge was stale shaped-texture content after
  a late Wayland fullscreen buffer commit. Window, buffer, compositor actor,
  surface container, struts, and work area were already correct.
- The accepted bounded refresh invalidates shaped-texture size and content,
  then queues actor and stage relayout/redraw at 80, 240, and 400 ms. It is
  cancelled on exit, focus loss, or controller teardown.
- GNOME 50 G-Unity passed 10 slow plus 20 rapid F11 cycles from a non-maximized
  window on build 43. Earlier build 41 coverage passed the same matrix from
  maximized and non-maximized windows. Captures have no black edge.
- GNOME 51 BigGnome passed 10 slow plus 20 rapid F11 cycles from a maximized
  window on build 43. G-Unity passed the full maximized and non-maximized matrix
  during build 41 validation. Captures have no black edge.
- GNOME 51 Classic -> BigGnome -> G-Unity and GNOME 50 six-layout Dock/Taskbar
  transition stress passed without duplicate or residual actors. A direct test
  apply that omitted `settings.json` persistence caused one hybrid relogin; this
  was a harness error, not product behavior, and both VMs were restored.
- Final focused suite: `78 passed`. Full suite: `530 passed`, one known PyGI
  deprecation warning. All runtime JavaScript syntax and diff checks passed.
- Both VMs finish in a fresh G-Unity session on runtime build 43. Strict audits
  report zero failures and zero warnings; current Shell warning journals are
  empty.
- Local and both VM payload hashes: runtime
  `f405709a3d7c5d374acff26ca598443ea5d6beeed8a83088feb1691370c836a9`;
  Dock resource host
  `2bfa2cd685fba7e97c1780e49fc1a4876b0f3aaa4d3adb94b5cf498617606822`;
  Panel host
  `5dc54d2cf64fc0a441305566adefc39344b4852d53192a85cfebbee4f7f7c6d7`;
  helper
  `fcbf2de6c3fcea98192347cd79bb81bf027a660b29255ecb2da5bd74cd3e5744`.
- Audit source SHA-256 is
  `6d12dedc89d5bc680ab75ab3033e7d00d0d383980fb87616a48cdf604ae6bb35`;
  audit payload-tree hash is
  `b5f632038d92f802057a6a67edb2fafaaa21823d7fe7838f151dcdfddbd11f3a`.

## 2026-08-25 — Original Dock-layout panel defaults repaired

- Reproduced on GNOME 50 after applying original BigGnome: the owned
  `panel-opacity-overrides` map no longer contained BigGnome, but the live
  compatibility key remained `uint32 0`.
- Root cause: original layout data is loaded additively. BigGnome does not
  contain `/org/communitybig/panel-and-dock`, while `PanelController` still
  reads that compatibility schema. Removing only the owned override therefore
  left the old live opacity unchanged. The Restore button worked because it
  explicitly wrote the compatibility key.
- Original BigGnome and G-Unity applies now write their accepted panel opacity
  and visibility defaults into the compatibility section while removing only
  the target layout's owned overrides. Other layout overrides remain intact.
- GNOME 50 passed `0 -> original BigGnome -> 65`; GNOME 51 passed
  `0 -> original G-Unity -> 70`. Both strict audits report zero failures and
  zero warnings. `layout_applier.py` SHA-256 is
  `073deb9f167f9f034c6241027983b1ff426f46c1fb86cf9f517de851d92dace4`
  locally and on both VMs.
- Focused suite: `140 passed`. Full suite: `530 passed`, one known PyGI
  deprecation warning. Ruff and diff checks pass; PKGBUILD is unchanged.
- Separate live debt: same-layout G-Unity reapply on GNOME 51 logged one helper
  access to a disposed old Dock actor while clearing its style class. Final
  actors and audit are correct. Investigate in a dedicated GJS lifecycle slice.
- GNOME 51 GSConnect 72 remains in its pre-existing incompatible state
  (`Cannot inherit from a final type`); its metadata supports Shell only
  through GNOME 50.

## 2026-08-25 — Dock monitor, overview, and workspace matrix accepted

- The live audit now requires the runtime Dock monitor set to match the logical
  monitor set. A focused regression proves that one actor across two monitors
  fails `dock-monitor-coverage`.
- GNOME 50.4 and GNOME 51.beta passed BigGnome and G-Unity with two displays,
  monitor 0 and monitor 1 as primary, and removal of the active primary. Every
  converged state had one Dock actor per monitor and no stage residue.
- Each Dock layout passed 10 slow and 25 rapid overview transitions on both
  Shell versions. Rapid Super input can be coalesced and finish open; one
  explicit final toggle closes it without actor drift.
- Each Dock layout passed 10 slow and 25 rapid transitions between a Brave
  workspace and an empty workspace on both Shell versions. Final strict audits
  reported zero failures and warnings.
- Focused suite: `58 passed`. Full suite: `531 passed`, with one known PyGI
  deprecation warning. PKGBUILD and package versions are unchanged.
- Current original layouts intentionally request Dock actors on every logical
  monitor. A future primary/all-monitors product control should be implemented
  per component after Panel migration, not inferred from GNOME display state.

## 2026-08-25 — Wayland F11 regression repaired at the surface boundary

- The build 43 fullscreen acceptance above was incomplete. Frame, buffer, and
  `MetaWindowActor` telemetry did not prove rendered-surface placement. Manual
  coverage missed the first entry after moving a non-maximized window.
- Broken captures had frame, buffer, and window actor at `0,0 1280x800`, while
  `MetaSurfaceContainerActorWayland` retained the normal-window offset. The
  offset exactly matched the visible black top/side margins.
- Mutter's `meta-window-actor-wayland.c` intentionally creates a black
  fullscreen background and centers the surface container while the mapped
  client surface is not an opaque monitor-sized allocation. A late Wayland
  allocation can become monitor-sized without another geometry sync, leaving
  the container centered.
- Build 43 invalidated `MetaShapedTexture` at 80/240/400 ms. It could not repair
  the container offset or a late container replacement. Builds 44/45 added
  container tracking and the missing `notify::fullscreen` trigger, but retained
  fullscreen-exit geometry repair. Build 46 still reproduced rapid-exit drift.
- Official Dash to Dock and Dash to Panel source confirms the ownership
  boundary: extensions control chrome visibility, fullscreen tracking,
  intellihide, and struts; they do not maximize, unmaximize, move, or resize
  application windows and do not replace Mutter's fullscreen engine.
- A runtime-disabled GNOME 50 control passed 10 slow and 20 rapid cycles with
  exact native exit restoration. This proved the runtime exit repair caused the
  drift. Build 47 removed all window-state and frame-geometry manipulation plus
  blind fullscreen timers.
- Final runtime build 49 keeps the native `in-fullscreen-changed` path. A
  Wayland-only compatibility guard watches actor/container replacement and
  mapped child allocation. It coalesces signals through one idle, then sets the
  container to `0,0` only when window and monitor fullscreen flags agree and
  frame, buffer, actor, and a mapped child allocation exactly cover the monitor.
  No Dock, panel, strut, maximize, unmaximize, or `move_resize_frame` operation
  occurs in this path.
- GNOME 51.beta BigGnome final results: moved non-maximized first entry passed;
  non-maximized `10 slow + 20 rapid` passed; maximized `10 slow + 20 rapid`
  passed. Every exit restored the exact original frame and buffer. The shim was
  exercised during the maximized matrix.
- GNOME 50.4 G-Unity final results: moved non-maximized first entry passed;
  contained non-maximized `10 slow + 20 rapid` passed; maximized
  `10 slow + 20 rapid` passed. Every exit restored the exact original frame and
  buffer. The shim was exercised during the maximized matrix.
- All accepted fullscreen samples required frame, buffer, window actor, and
  surface container `0,0 1280x800`, a mapped monitor-sized child surface,
  hidden panel/Dock, and a screenshot without black margins.
- Final strict audits: zero failures and zero warnings on both VMs. Current
  build 49 Shell PIDs have no JavaScript, surface-allocation, or compatibility
  guard warnings. Both VMs end with exactly one `1280x800` monitor.
- Regression gate: always test the first F11 entry after moving a non-maximized
  window, then 10 slow and 20 rapid cycles from both maximized states on GNOME
  50 and 51. Require surface-container telemetry and screenshots. Source-text
  contracts alone are not behavioral or visual acceptance evidence.
- Focused suite: `79 passed`. Full suite: `531 passed`; one known PyGI
  deprecation warning. JavaScript syntax and `git diff --check` pass.
- Local and both VM SHA-256: `dockPanelController.js`
  `09b098b9249f36f816e36e14d03a6030605adcd29d2576572c42fc3b40a42900`;
  `runtimeController.js`
  `8ccb7fa1a884e5ed45a5d361c02c3076e5bda922991de4db3ddb838e27082dff`;
  `runtime_audit.py`
  `80d489697055e64e4e59e617c39364727906bba9bed9960b7a3ceb90c158d9e2`.
  Runtime payload-tree hash:
  `822281b9fa51a0b92b5ee20f93dbba1379677f28f286807288c7e4e6e1d71114`.

## 2026-08-26 — Taskbar/Panel lifecycle ownership accepted

- Runtime build 50 moves Taskbar lifecycle ownership into the unified runtime.
  `TaskbarSurfaceManager` owns context initialization, `global.dashToPanel`,
  settings initialization, overview state, global styles, Ubuntu Dock settling,
  `PanelManager` construction, cancellation, and reverse-order teardown.
- The inherited visual modules no longer import live globals from their old
  extension entry point. `runtimeContext.js` provides the compatibility context;
  `community-panel/extension.js` is now only a thin rollback adapter.
- The strict runtime audit now requires Taskbar manager ownership, global
  ownership, settled activation, exact actor count, and no stage residue.
- GNOME 50.4 passed fresh-session Hybrid; `Hybrid -> BigGnome -> Hybrid`,
  `Classic -> Minimal -> Classic`, and `Desk UX -> G-Unity -> Desk UX`; plus
  direct disable/enable. Hybrid and Classic had one `1280x38` Taskbar; Desk UX
  had one `1280x46` Taskbar. Managed-surface exits left no Taskbar actor,
  manager, or global.
- GNOME 51.beta passed fresh-session Hybrid, `Hybrid -> BigGnome -> Hybrid`,
  and direct disable/enable. Hybrid had one `1280x38` Taskbar. The corrected
  runner subsequently passed all eight surface directions on both GNOME 50 and
  51. Final strict audits had zero failures on both VMs; their session-type
  probe reports the known SSH `tty` warning. Both VMs retained exactly one
  `1280x800` monitor.
- One monolithic transition run stalled in helper `CompleteSwitch` after it
  redundantly reapplied Hybrid as the next source. Hybrid reapply then passed
  in isolation on build 50/GNOME 50 and build 49/GNOME 51. The baseline runner
  now reuses a previous verified target when it is the next source, preserving
  all eight transition directions without redundant full dconf loads.
- Separate Copyous debt: during `BeginSwitch`, late callbacks in
  `lib/ui/components/clipboardItemMenu.js:58` and
  `lib/ui/items/statusItem.js:110` access `this.ext.settings` after disable.
  Fix Copyous signal/idle cleanup in its own repository. These stacks do not
  originate in the unified runtime or Taskbar modules.
- Separate AppIndicator debt on GNOME 50: asynchronous
  `_waitForFullyReady()` resumes after its `AppIndicatorsIconActor` is disposed
  and reads null `_indicator` (`appIndicator.js:1049/1058`,
  `promiseUtils.js`). The inherited panel teardown appears below the failing
  frames because it restores status items. Fix cancellation in AppIndicator;
  do not add a blind Taskbar teardown delay.
- Local tests: focused `56 passed`; full `535 passed`. The final run reported
  the known PyGI deprecation plus two headless Adw/GTK warnings from
  `test_theme_manager`; no test failed. JavaScript syntax, focused Ruff, and
  `git diff --check` pass. Full Ruff still reports eight pre-existing findings
  outside this slice. PKGBUILD and package versions are unchanged.
- Final 17-file aggregate SHA-256 on local staging and both VMs:
  `cccc0d91fa3d319aff705c12a261a4a45edcbd1f852dc05ef1eb9f4828e119c6`.
  `runtime_baseline.py` source SHA-256:
  `79bb891ec5c84a3bee84b5b3a108a8cd97af176ea05673fc1935445d76f715d0`.
- Local and both VM payload-tree hashes: unified runtime
  `24814a606c714e8d2b5825bf6146ca9102b470b94cff4fe77ab923aad4e0e6de`;
  Panel host `8781ff9afea0d4844d4a67d4e07092bfcc1520ce9f6c24373941fd47bb03992d`;
  audit tool `b67a401dc7e8d164d769500528cd349038db1a746534c4af8326656588b1ad05`;
  baseline tool `53aa658b72b0df01a25465bf90254d26ca18df61226b4e3a2476a3e042e9f65e`.
- Next implementation slice: port Taskbar application-button behavior while
  preserving the inherited status area, clock, menus, indicators, and exact
  layout geometry.

## 2026-08-26 — Shell stylesheet lifecycle regression repaired

- Reproduction: Classic light -> Desk UX -> dark scheme -> G-Unity left dark
  top-panel icons on the dark G-Unity panel. The helper also returned
  `loadTheme ERR Error: Argument file may not be null`.
- G-Unity now explicitly owns a `#fafafb` panel-button foreground. This prevents
  inherited light-layout foreground colors from leaking into its fixed dark
  panel.
- Root cause of the theme error was runtime `ComponentHost` retaining the
  original `St.Theme` object with each component stylesheet. `Main.loadTheme()`
  replaces that object and copies custom stylesheets. Later teardown unloaded
  from the stale theme, leaving a duplicated and eventually null stylesheet in
  the current theme.
- Runtime build 51 follows GNOME Shell 50's `ExtensionManager`: retain the
  `Gio.File`, then unload it from the current `St.Theme`. Helper build 68 exposes
  session-theme diagnostics. Strict audit rejects null and duplicate custom
  stylesheets.
- Helper fixed-dark targets use the Shell's documented `force-dark` session
  mode before the clean-room `loadTheme()`. This is a deterministic theme
  resolution guard, not a timer or a replacement theme engine.
- GNOME 50.4 and GNOME 51.beta both passed the exact reproduction twice. Every
  G-Unity completion reported `loadTheme` without `ERR`; screenshots show white
  top-panel icons. Strict audits report zero failures and stylesheet lists stay
  unique. GNOME 50 ends in G-Unity; GNOME 51 ends in BigGnome. Both retain one
  `1280x800` monitor.
- GNOME 50 journal contains only the separately documented Copyous late
  callbacks. GNOME 51 journal is clean for this run. No theme/runtime error is
  present after the accepted transitions.
- Focused tests: `112 passed`. Full suite: `538 passed`, with one known PyGI
  deprecation warning. JavaScript syntax and `git diff --check` pass.
- Local and both VM payload-tree hashes: runtime
  `3c3b0c95f62992e6d7be66790aaf066bfec37f26eda2e3daf0d65c1cb61701e9`;
  helper
  `a93a4dbb67d8e727092b8f5875ed56f4265fb52875e7ee4b66ebb2a6876d6558`;
  Panel host
  `8781ff9afea0d4844d4a67d4e07092bfcc1520ce9f6c24373941fd47bb03992d`;
  audit tool
  `2004d517a1dcb1cbec1772f48dddd254239089cec6879ec7409381fe79c1a35f`.
- Regression gate: apply a Taskbar layout, change the application color scheme,
  then leave for a Dock/native layout. Require successful `loadTheme`, readable
  panel foreground, no null stylesheet, no duplicate stylesheet, screenshot,
  strict audit, and journal inspection on GNOME 50 and 51. Source-text tests are
  not visual acceptance evidence.

## 2026-08-26 — Taskbar behavior, rendering, and visibility ownership

- Runtime builds 52-57 move application actions, preview/context-menu
  coordination, Hybrid/Desk UX indicators, and Panel visibility modes behind
  Layout Switcher-owned controllers. The inherited Panel remains the rollback
  renderer; its status area and native menu implementations are unchanged.
- Application action telemetry covered launch, focus, minimize, active-app
  cycling, grouped multi-window previews, and context menus. Menu ownership
  holds intelligent hiding with a dedicated `Hold.MENU` bit until the popup
  closes.
- Hybrid uses the owned segmented indicator, Desk UX uses focused Metro and
  unfocused dashes, and Classic remains ungrouped with labels and no indicator.
  Strict geometry is Hybrid/Classic `1280x38` and Desk UX `1280x46`.
- Always visible owns a strut. Always hidden and intelligent modes are overlays
  and release the full work area. Intelligent mode uses the inherited official
  Dash-to-Panel `FOCUSED_WINDOWS` and pointer-reveal paths.
- Official Dash-to-Panel master `1c0c1f1` was compared directly. Its
  `intellihide.js` matches the bundled Community Panel implementation except
  for runtime-context import and `Hold.MENU`; it changes `affectsStruts` and
  queues Shell regions, but never moves or resizes application windows.
- GNOME 50 exposed `1280x838` after intelligent -> always-visible when the
  runtime destroyed the Taskbar, temporarily restored the stock top panel,
  then waited 200 ms before rebuilding the bottom panel. The intermediate
  top/bottom strut transition corrupted Mutter's maximized allocation.
- Build 57 fixes the lifecycle cause: Taskbar profiles reuse the same
  `PanelManager`; only Taskbar <-> Dock transitions destroy the surface. No
  maximize, unmaximize, `move_resize_frame`, blind timer, or work-area repair
  shim is used.
- GNOME 50 and 51 both passed intelligent `1280x800` -> always-visible
  `1280x762`, then two minimize/reactivate cycles at `1280x762`. GNOME 50 also
  restored the exact saved normal frame `60,116 1160x530`. Action telemetry
  survived profile changes, proving that the Taskbar manager remained alive.
- Desk UX and Classic strict audits passed on both Shell versions before the
  final lifecycle change. Hybrid build 57 strict audits passed with zero
  failures on both versions; the only warning is the known SSH `tty` session
  probe. Both VMs finish on Hybrid with one `1280x800` monitor and empty Panel
  visibility overrides.
- GNOME 50 journal is clean for runtime/Panel errors. GNOME 51 contains the
  separate known GSConnect `wl_clipboard.js:56` final-type error; no runtime or
  Panel frame appears in that stack.
- All six layout snapshots set Nautilus grid captions to
  `['size', 'none', 'none']`. Legacy standalone Panel/Dock test contracts now
  assert migration to the unified runtime rather than standalone restart.
- Focused suite: `88 passed`. Layout-applier suite: `102 passed`. Full suite:
  `544 passed`, with one known PyGI deprecation warning. JavaScript syntax and
  `git diff --check` pass. PKGBUILD and package versions are unchanged.
- Local and VM payload hashes: runtime
  `223230c6be0b8fde7355746923ca1bd2d0a23d23f5111012cd125fb40aead8cb`;
  Panel host
  `26684b222aa2e59dec86b3e7a74ba6e8d36c2ec74d47ecca1e819613723b596d`;
  audit tool
  `4f67c0a922c7087f813fb95ed453fdbfed3bbf61976572d5aa680e0072a17a6d`.
- Remaining acceptance is user visual coverage of native status menus and the
  complete manual application-button/layout matrix. Do not remove inherited
  Panel branches before that approval.

## 2026-08-26 — Manual Taskbar follow-up, build 59

- Hybrid plus the Desk UX indicator exposed Dash-to-Panel's legacy
  `highlight_stacked_bg.svg` edge when a grouped application had two windows.
  The owned renderer now suppresses only that legacy edge. Grouping, previews,
  focus highlighting, and the horizontal runtime indicator remain unchanged.
- The two-second visibility lag was the inherited
  `intellihide-enable-start-delay=2000`. Runtime activation and the live Python
  settings path now set it to zero, configure behavior first, and enable
  intellihide last. GNOME 50 and 51 reached the hidden translation within the
  350 ms observation window.
- Community Menu now follows the allocated Panel size through native
  `St.Icon.set_icon_size()`. It passed live 38 -> 56 -> 38 scaling on GNOME 51
  and a 56 px confirmation on GNOME 50.
- Runtime build 59 reports `panel-height-overrides` in expected actor geometry.
  Desk UX includes its six external margin pixels. Strict audit therefore
  accepts supported custom heights instead of comparing them with fixed layout
  defaults.
- GNOME 51 reproduced Hybrid + Desk UX indicator + two Nautilus windows without
  the vertical edge. GNOME 50 and 51 passed always-visible -> always-hidden in
  350 ms. Final strict audits: zero failures and the known SSH `tty` warning.
  GNOME 51 ends Hybrid at `1280x38`; GNOME 50 ends Classic at its preserved
  `1280x56` override. Both have one `1280x800` monitor.
- Journal review found no Layout Switcher, Community Panel, or Community Menu
  exception. GNOME 51 retains the external GSConnect final-type failure. Both
  versions log the known retired Community Dock metadata lookup during Shell
  startup; runtime ownership and stage-residue checks pass.
- Focused suite: `111 passed`. Full suite: `547 passed`, with one known PyGI
  deprecation warning. PKGBUILD and package versions are unchanged.

## 2026-08-26 — Taskbar visibility setting ownership, build 61

- Taskbar Panel visibility is the first exclusive owned-setting slice. With the
  unified runtime active, the GTK backend reads/writes only
  `panel-visibility-overrides`; it does not mirror live changes to Community
  Panel. One-time legacy import remains. The standalone compatibility path
  still mirrors until upgrade coverage permits adapter removal.
- Runtime build 61 listens to `changed::panel-visibility-overrides` and applies
  the active layout live without rebuilding its `PanelManager`.
- Live testing found a Dash-to-Panel ordering defect in `Intellihide.disable()`:
  it restored the strut while the Panel actor was still translated off-screen.
  Mutter could retain a maximized `1280x838` allocation after returning to
  always visible. The root fix reveals the actor before enabling its strut.
  There is no blind timer, window resize, or compositor repair shim.
- GNOME 50.4 and 51.beta passed 10 slow and 20 rapid owned-schema cycles while
  maximized. Final frame/work-area geometry was `1280x745` with a 55 px Panel
  on GNOME 50 and `1280x762` with a 38 px Panel on GNOME 51.
- Controlled non-maximized cycles preserved exact frames
  `60,107 1160x530` (GNOME 50) and `38,59 1106x556` (GNOME 51). GNOME 51 also
  passed maximized minimize/restore at `1280x762`. A transient `1280x838`
  reading belonged to the still-minimized window; restoration recomposed it to
  the current work area.
- Strict audits: zero failures on both VMs; only the expected SSH `tty` warning.
  Both finish on Hybrid with one `1280x800` monitor. GNOME 50 preserved
  `{'Desk UX': 'always-hidden', 'Classic': 'always-visible'}`; GNOME 51
  preserved an empty visibility map.
- Journal: no Layout Switcher or Community Panel exception. GNOME 51 retains
  the external GSConnect `wl_clipboard.js:56` final-type error.
- Focused tests: `93 passed`. Full suite: `550 passed`, with the known PyGI
  warning and two headless Adwaita warnings. JavaScript syntax, focused Ruff,
  and `git diff --check` pass. PKGBUILD and package versions are unchanged.
- Local and both VM file hashes: runtime controller
  `1aad43cf7213c1de0ab11f2788698a51bc0f25bee7fdb7e891031a39af4d1619`;
  Panel intellihide
  `aa9de9b7b7274c20de02f224afbd40c7c35e5d88c0622417b1d2ada97b6dbd08`;
  settings backend
  `730a16681a92137974390688da2ad095586be85756b4ccbdf95b3b61af08e04d`;
  Panel/Dock page
  `d9196a2711bc0741a4f796c13d7cb1ed7998abbeb9190e0bc781723f019eefcd`.
- Next implementation slice: move Taskbar Panel height to exclusive owned
  schema control. Keep inherited adapters until the remaining setting slices
  and stable/testing upgrade matrix pass.

## 2026-08-26 — Taskbar height setting ownership, build 62

- Taskbar Panel height now uses the same exclusive owned-setting boundary as
  visibility. With unified runtime active, the GTK backend reads/writes only
  `panel-height-overrides`. One-time import reads inherited `panel-sizes`; the
  standalone compatibility path still mirrors for upgrade rollback.
- Runtime build 62 listens to `changed::panel-height-overrides`, clamps values
  to 32-56 px, and applies them without rebuilding `PanelManager`.
- The adapter uses Dash-to-Panel's official per-monitor
  `PanelSettings.setPanelSize()` API after monitor initialization. It therefore
  preserves real monitor IDs and native `changed::panel-sizes` geometry resets
  instead of reimplementing its JSON storage.
- GNOME 51 passed live 38 -> 56 -> 32 -> 38 with maximized Brave. Exact
  frame/work-area geometry was `1280x744` at 56, `1280x768` at 32, and
  `1280x762` after restoring 38.
- GNOME 50 passed 56 and 32 in intelligent overlay mode. At 56, normal Brave
  remained `60,135 1160x530`, work area remained `1280x800`, and
  `affectsStruts=false`.
- Both Shell versions passed 10 slow and 20 rapid height cycles. Taskbar
  manager/action/menu ownership remained active and stage actor count remained
  exact.
- Final state: both VMs use Hybrid and one `1280x800` monitor. GNOME 51 retains
  empty height/visibility maps. GNOME 50 retains height
  `{'Classic': 36}` and visibility
  `{'Classic': 'always-visible', 'Hybrid': 'intelligent'}`. Internal
  `panel-sizes` uses monitor ID `RHT-0x00000000` at 38 on both.
- Strict audits: zero failures, only the expected SSH `tty` warning. GNOME
  Shell journals contain no Layout Switcher or Community Panel exception.
  GNOME 51 retains the external GSConnect final-type error.
- Focused tests: `95 passed`. Full suite: `552 passed`, with one known PyGI
  warning. JavaScript syntax, focused Ruff, and `git diff --check` pass.
  PKGBUILD and package versions are unchanged.
- Local and both VM hashes: runtime controller
  `a1b41da01a840e02b0ab7abcad710310288f0a50f3d6d6152c30ccd42294c753`;
  Taskbar runtime
  `8f9068c8889c98cee78efb5fb8b378f38964a11af98613ddb0d4816c431cb69a`;
  Taskbar surface
  `386e61b153d174986e79dc35c024e07cee2f1c6db8d8d6092a9edf392c1464d0`;
  settings backend
  `97055a24a14dfb5b32d24215856e0ab268cc967be6e0595a2f3a6184ff6a347c`.
- Next implementation slice: move Taskbar Panel opacity to exclusive owned
  schema control. Keep inherited adapters through the upgrade matrix.

## 2026-08-27 — Taskbar opacity ownership and Mutter 51 signal compatibility, build 64

- Taskbar opacity now reads and writes only `panel-opacity-overrides` while the
  unified runtime is active. Legacy import and standalone mirroring remain.
- Runtime uses Dash-to-Panel's static opacity renderer and reports configured
  and effective actor alpha. GNOME 50.4 and 51.beta passed 20%/90% extremes,
  10 slow transitions, 20 rapid transitions, and maximized 90 -> 20 -> 70.
- Both versions preserved exact `1280x762` maximized geometry, one 1280x38
  Taskbar actor, and one `1280x800` monitor. Original opacity maps were
  restored: empty on GNOME 50 and `{'Hybrid': 70}` on GNOME 51.
- GNOME 51 exposed Dash-to-Panel's two-argument `grab-op-begin` emission against
  Mutter 51's three-argument signal. Runtime now queries `GObject.signal_query`
  and emits the loaded signature. Launch-by-number passes on GNOME 50 and 51
  without a runtime JS error.
- Strict audits: zero failures; only the SSH `tty` warning. Known external
  journal warnings remain for Copyous, GSConnect, retired Community Dock
  metadata, KMS priority, and Brave invalid geometry recovery.
- Focused tests: `98 passed`. Full suite: `557 passed`, with one known PyGI
  warning. JavaScript syntax, strict schemas, and diff checks pass. Ruff still
  reports nine pre-existing findings outside this slice.
- Final local and VM hashes: layout profiles
  `0638c8f91382071fa7aaf08b889ebbacdd6991b1dfcfd26ecfe9e9f19bd84c32`;
  runtime controller
  `64576aee4a6fee6ccbe59d64a5f6083f18b79b373d0cd6e0b28c31205ddac2c2`;
  Taskbar runtime
  `66b386dca89c2b6ac72c586fa2235e4358195fce0ae3572cb2ac01e1431419e7`;
  Taskbar actions
  `3b6e4d51e6c4b69f110a6f1ef08bab6388e5841b4fe9c9839ad37d447f778961`;
  settings backend
  `335c4f6aadc76cdf84b92c27f40a8ca0b45125eb60aab6b0b52149bd41d5f7a2`;
  runtime audit
  `99df26dc744f920e3fbf946e3b14b10e50a896ebe1b7dfa5f23177557c467af1`.
- Next slice: move Taskbar indicator style to exclusive owned-schema control.
  Keep inherited adapters through the upgrade matrix.

## 2026-08-27 — Remaining supported-setting ownership, build 65

- Indicator style and hover now persist only in owned per-layout overrides
  while the unified runtime owns Dock or Taskbar. Legacy custom schemas are
  read only for one-time import and standalone rollback.
- Dock opacity, icon size, and visibility now use the same exclusive UI
  boundary. Their inherited Dash-to-Dock settings remain private renderer
  adapters, not user-facing persistence.
- Classic rejects stale indicator overrides and remains label-only. Taskbar
  lift applies the complete accepted SIMPLE animation profile internally.
- Active Dock setting changes update indicator, hover, opacity, size, and
  visibility without rebuilding the Dock manager. Telemetry exposes manager
  generation and configured/effective opacity and icon size.
- GNOME 50.4 and 51.beta each passed Taskbar 10 slow plus 20 rapid
  indicator/hover cycles, Classic no-indicator, and Dock 10 slow plus 20 rapid
  combined cycles. Dock covered 20%/90% opacity, 28/64 px icons, and always
  visible/hidden/intelligent modes. Manager generation stayed `1`.
- Original override maps were restored exactly. Legacy custom indicator/hover
  values were unchanged. Both VMs finish Hybrid with one `1280x800` monitor.
- Strict audits: zero failures and the expected SSH `tty` warning. Current
  Shell journals contain no runtime, Dock, or Panel exception.
- Focused tests: `106 passed`. Full suite: `565 passed`, with the known PyGI
  and two headless Adwaita warnings. JavaScript syntax, strict schemas, focused
  Ruff, and diff checks pass. PKGBUILD and package versions are unchanged.
- Final local and both-VM hashes: runtime tree
  `5675f1c607206569d9ecd060a522935ddab196c08f4e173aee0cd30a741169d7`;
  runtime controller
  `036bef314b23fb17646a4646feac5d2f7d24c3a52e2e9f8145b8a0e632db5c25`;
  Dock runtime
  `d0684de8766306a7f0f03fe54da04261dbd1ca9dab194449def7438202145065`;
  Taskbar runtime
  `a6b96e8e49dfbb1b384e7d769d9c7181165b9305374e69a7108f907066f5f4e2`;
  settings backend
  `0d643b27939331b290d485ca23d3d3492e66b32ac97bb043ef721c747439856c`;
  runtime audit
  `3cba44badea074f415a6956bda5b9c9225182d0053d275958c7399eab70302f9`.
- Next gate: user visual acceptance of the five live controls. Then run clean,
  stable, testing, intermediate-UUID, and rollback upgrade matrices before
  deleting inherited schema or renderer adapters.

## 2026-08-27 — Physical Taskbar and native status host, build 68

- Added `docs/COMMUNITY_PANEL_RUNTIME_MAP.md` from the live import graph and
  compared GNOME Shell 50.4/current Panel contracts with official
  Dash-to-Panel master. The accepted boundary reuses `Main.panel`,
  `Main.panel.statusArea`, native status actors, and the native menu manager.
- `TaskbarPanelHost` now owns physical detach/create/chrome/release and partial
  construction rollback. `TaskbarStatusAreaHost` owns exact status actor
  parent/index restoration and the intellihide menu bridge. Shell actors no
  longer receive `_dtpOriginalParent` state.
- Diagnostics cover host generation/count, adopted/external/orphan roles,
  clock, Quick Settings, open menus, menu mapping, and transformed geometry.
  Audit distinguishes normal windows from the DING desktop and retries only a
  transient extension-service `NoReply`.
- GNOME 50.4 preserved `Classic`: 12 status roles, zero orphans, maximized
  Brave/work area `1280x768`, Quick Settings open and pointer-leave hold, 10
  slow plus 20 rapid `Classic <-> BigGnome` cycles, strict audit zero failures.
- GNOME 51.beta preserved `Hybrid`: 10 status roles, zero orphans, maximized
  Brave/work area `1280x762`, Quick Settings open and pointer-leave hold, 10
  slow plus 20 rapid `Hybrid <-> BigGnome` cycles, strict audit zero failures.
  Both VMs end with one `1280x800` monitor.
- Filtered `gnome-shell` journals contain no build 68 exception. GNOME 50
  emitted two transient Clutter allocation warnings during rapid Dock churn,
  with zero final residue. GNOME 51 retains the unrelated GSConnect
  `wl_clipboard.js:56` final-type service restart loop.
- Final focused tests: `74 passed`. Full suite: `570 passed`, with the known
  PyGI and two headless Adwaita warnings. All runtime/inherited JavaScript
  syntax and `git diff --check` pass. PKGBUILD/pkgver/pkgrel are unchanged.
- Final local/GNOME 50/GNOME 51 SHA-256: runtime controller
  `27b7411b0558adfa7c0dc74b790e415f3ea88408419743feab1fce0c9a27fe27`;
  Taskbar runtime
  `f13adc8bfe8e9217b9dad0de6beac9950fb4e8f3af78c043f490888b8b54c283`;
  Taskbar surface
  `0308f10e05869cc48f0c1e74b8b26dc2c66182324aa7b36e24de28c0408799a9`;
  physical host
  `62b1746b2c1308f96b4c4d32d2ce5516376153649dc7826be96d012111a3edf9`;
  status host
  `2db448de623a9a1748e1818a4557cb56a0754d53947ad6bd77ebbab3fdea34b2`;
  inherited Panel
  `608ad91c1fcf4187f134f4c686cdec113a67cdcd36a63869f9c6936acb4f2ff2`;
  inherited PanelManager
  `6dd90d1eff9015c502b5e6f7d65782b7d3350d4a64559b68af4474a874c8fb37`;
  audit
  `0c3535990ac5035b174677a3f7debe6d4f94c0abd394179c23ce5610d9360dd8`.
- Manual gate: click Date Menu; exercise AppIndicator, Copyous, removable-drive,
  and other status menus. `Super+V` opens Copyous; use `Super+S` only for Quick
  Settings. Then continue inherited PanelManager injections/monitor lifecycle
  extraction and the clean/stable/testing/rollback matrix.

## 2026-08-27 — Taskbar topology and Shell hook ownership, build 69

- `TaskbarMonitorHost` owns primary-monitor selection, physical panel creation,
  topology settings, `monitors-changed`, serialized reset, stale refresh
  rejection, and monitor diagnostics. `PanelManager` no longer owns topology.
- `TaskbarShellHooks` owns 15 AppDisplay/layout/overview/BoxPointer/workspace/
  Looking Glass/message-tray/native-panel/shutdown hooks. Exact descriptors are
  restored only while still owned; external replacement becomes telemetry,
  never a clobbered property.
- Official Dash-to-Panel master still uses the same private Shell integrations
  and explicit teardown. Build 69 preserves its behavior callbacks and moves
  only installation/restoration ownership.
- The first live `Hybrid -> Minimal` check exposed a missing native-surface
  branch: expected telemetry changed while Taskbar stayed active. The controller
  now deactivates Dock and Taskbar explicitly for `Minimal` and rejects unknown
  surfaces.
- GNOME 50.4 passed a topology-setting reset, 10 slow and 20 rapid
  `Hybrid <-> Minimal` cycles, and finished in its original `Minimal` state.
  GNOME 51.beta passed the same matrix and finished in its original `Hybrid`
  state. Both retain one `1280x800` monitor.
- Every endpoint had exact actor coverage, zero stage residue, zero monitor
  reset failures, and zero hook restoration conflicts. GNOME 51 maximized
  Brave remained `1280x762` with a `1280x38` Panel. Strict audits report zero
  failures and only the SSH `tty` warning.
- GNOME 51 journal has no build 69 exception. Separate startup debt remains:
  Copyous rejects `heavyDepsReady` at `extension.js:5` and then fails at
  `clipboardItem.js:283`; GSConnect still hits a final type; retired Community
  Dock metadata is absent. Do not add Taskbar timing workarounds for them.
- Focused tests: `133 passed`. Full suite: `573 passed`, with one known PyGI
  warning. Runtime/inherited JavaScript syntax and diff checks pass. PKGBUILD
  and package versions are unchanged.
- Final local/GNOME 50/GNOME 51 SHA-256: runtime controller
  `f45321369b3d696b2b80975eccc005287620de931a5672cbcf53031f8d493a31`;
  Taskbar surface
  `02dd68de36c24cd6e66e8f55f3a6260b2fd94bcac3abfa0045e94c63953a9dde`;
  monitor host
  `fb1acb42dae183f4a2e06a8f8f06a769d952b34daf1b8ff6564da2746491f932`;
  Shell hook host
  `a70b54574623f38c19224cd328478aa12aad59e1756a6a70209c5072b80b106e`;
  inherited PanelManager
  `5d0ea06fe3740b1fd0219850d3dff0a65fb8b35738977826bb099c83c3f0b4aa`;
  audit
  `ab808accf2ef5d9437b827c4dcd8da28a0184d41d2e52f8fc80311f5d89740e4`.
- Next slice: extract remaining manager-owned notification, desktop-icon,
  overview, and keybinding services behind focused runtime hosts. Keep behavior
  callbacks inherited until their live restoration matrices pass.

## 2026-08-27 — Taskbar manager-service ownership, build 70

- `TaskbarServiceHost` now owns the remaining service lifecycle formerly in
  inherited `PanelManager`: Overview, notification monitor, DING usable area,
  seven manager signal groups, and the intellihide toggle keybinding.
- Activation preserves upstream ordering: Overview starts after primary-panel
  creation; long-lived services survive monitor-only resets; panel references
  are released before physical actors. Full teardown unbinds and destroys in
  reverse order.
- Pending DING margin idles are cancelled. Partial activation failures clean up
  transactionally. Compatibility manager properties are cleared only if still
  owned by the host.
- This slice ports lifecycle ownership only. Official Dash-to-Panel master
  still owns the same private integrations directly and exposes no newer public
  Shell API. Inherited Overview, notification, and DING behavior modules remain
  loaded until separately replaced and accepted.
- Telemetry and strict audit now require service ownership/activation, Overview,
  notifications, LauncherAPI and Unity D-Bus, DING ownership and settled exact
  margins, seven signal groups, keybinding ownership, and zero activation
  failures.
- GNOME 50.4 retained Classic. GNOME 51.beta retained Hybrid. Each passed 10
  slow and 20 rapid Taskbar-to-Minimal lifecycle cycles plus 10 slow and 20
  rapid native Overview cycles. Both finish with one `1280x800` monitor.
- Both VMs passed a real notification, 38 -> 56 -> 38 px DING margin update,
  and intelligent-hide `Super+I`: hidden at `translationY=38`, retained visible
  at `translationY=0` with `holdStatus=2`, then released. Original empty height,
  visibility, and Overview-keybinding maps were restored.
- Final strict audits: zero failures and only the SSH `tty` warning. GNOME 50
  and GNOME 51 journals contain no build 70 JavaScript exception.
- Final validation: focused `78 passed`; full suite `574 passed`, with one
  known PyGI warning and two headless Adwaita warnings. JavaScript syntax and
  diff checks pass. PKGBUILD and package versions are unchanged.
- Final local/GNOME 50/GNOME 51 SHA-256: runtime controller
  `6282781a48fe0f859cbfd2156d7125ef0ec749f5cc5030a994b8140cf98f178c`;
  Taskbar surface
  `2daa153ffde844a3f80376b8717fbb1f00c8a4a86ec52a9a5fe16211d1a5e3a2`;
  monitor host
  `e1820ef3f9827c9eacd16045334d78e53827a94885da70d6ea629ff5c6b4217d`;
  service host
  `4fa9f070c8a7c27f0b9d03c8bf1d32807d8ad15106e900218ac9c62a76945e28`;
  inherited PanelManager
  `fb25771f6ce5964489047071c6f2d6b232c3125f332a660def545c63142045b8`;
  audit
  `64c8346bdf418c73714e09fa05f4c701e34ddd0ddd480c681632d7ecf1cc7f0e`.
- Next slice: inventory the behavior callbacks and inherited service
  implementations still loaded from Community Panel. Replace and accept one
  boundary at a time before deleting any compatibility module.

## 2026-08-27 — Shared DING usable-area implementation, build 71

- One runtime-owned `DesktopIconsUsableAreaClass` now serves Dock and Taskbar.
  It preserves the official DING sentinel, 100 ms coalescing,
  `extension-state-changed` reconnection, and `setMarginsForExtension()`
  protocol. The upstream 1-clause BSD notice remains in the owned source.
- Dock uses `community-dock@communitybig.org`; Taskbar uses the explicit stable
  `community-panel@communitybig.org` owner. The first GNOME 50 activation caught
  that `TaskbarSurfaceManager` has no UUID. Transactional cleanup left zero
  actors; the stable owner fixed the root cause without a timer workaround.
- Telemetry and strict audit require runtime ownership, connection, settled
  dispatch, exact enabled-DING recipients, and exact physical/margin geometry.
  Both dormant inherited DING implementations were removed after acceptance.
- GNOME 50 passed exact 38/56 px margins, dynamic DING activation, 10 slow and
  20 rapid Dock/Taskbar transitions, then returned to BigGnome with DING off,
  empty overrides, and one monitor. GNOME 51 passed the equivalent matrix and
  returned to Hybrid with DING active, empty overrides, and one monitor.
- One GNOME 51 rapid block was discarded after GSConnect 72 repeatedly failed
  `Cannot inherit from a final type`. GDB captured a GJS/GObject toggle-ref
  deadlock between the Shell main thread and dconf worker. After session restart,
  five individually audited replacement cycles passed with GSConnect disabled;
  its original enabled/error state was restored. No build 71 JS error occurred.
- Focused tests: `79 passed`. Full suite: `575 passed`, one known PyGI warning.
  Runtime/inherited JavaScript syntax and diff checks pass. PKGBUILD and package
  versions are unchanged. Strict audits report zero failures on both VMs.
- Final local/GNOME 50/GNOME 51 SHA-256: runtime controller
  `79c78c2e234d5a227e4a061fd93e43437a2c80de750254abc28c282e902b7eed`;
  service host
  `f1eb7afa540c3cca2ee52e141668308ce7df124614f0eaeec81cc85baf28ba15`;
  shared DING bridge
  `7e78f4953c79898c95d145fa69cfb13984cebfc81294256bca0f722cbd03f538`;
  Dock imports
  `88a8d26e2ac62fe2747371f266b36cc05aec1579d8ed1c349fba5a7c705b3d62`;
  Dock runtime
  `9672f688e01e7094b11dab3c1cddcce51e66a3c3ba512226da69f4bbdd4eba03`;
  audit
  `efb56a7f4981f0964df79de2a32e13dc993436fadf3c18a7eb045316388adc8e`.
- Two migration boundaries remain: Overview behavior, then final inherited
  status/fullscreen behavior plus exact teardown. The Dock menu-side selector
  and macOS-like magnification remain post-migration work.

## 2026-08-28 — Owned Taskbar notification monitor, build 72

- `TaskbarNotificationMonitor` now owns Shell focus/message-tray signals, Unity
  launcher updates, and the `com.canonical.Unity` bus name. It aggregates every
  source per app, merges tray/Unity counts, and clears count/urgency on focus.
- GNOME Shell 50.4/main and current Dash-to-Panel sources were reviewed. No
  newer public API exists; the port follows the current private Shell contract
  and fixes multi-source aggregation and stale Unity urgency without timers.
- Telemetry and strict audit cover implementation, connection and bus
  ownership, sources, application states, totals, urgent IDs, updates, and last
  app. The inherited `notificationsMonitor.js` was removed after live acceptance.
- GNOME 50 passed real notification, visible badge, focus clearing, 10 slow and
  20 rapid cycles, teardown/re-entry, and final BigGnome strict audit. GNOME 51
  passed the equivalent real/focus tests, 10 slow and 20 rapid cycles, and final
  Hybrid strict audit. Both finish with one `1280x800` monitor and zero audit
  failures.
- Direct `active-layout` writes and a low-level apply without updating the app
  state created mixed visuals during an early test. CLI transitions must apply
  the full snapshot, then persist the same successful label through
  `Settings().set("active_layout", ...)`. Strict audit rejects divergence.
  Both layouts were fully restored before final acceptance.
- One discarded GNOME 50 repeated full-layout stress sequence reached the
  existing GJS/dconf futex deadlock after many extension reloads. No runtime JS
  error was logged; the restarted session passed. GNOME 51 journal noise is the
  known GSConnect `wl_clipboard.js` final-type failure, external to this build.
- Focused tests: `80 passed`. Full suite: `576 passed`, one known PyGI warning.
  Changed JavaScript syntax and diff checks pass. PKGBUILD/package versions are
  unchanged. Final local/GNOME 50/GNOME 51 SHA-256: runtime controller
  `eebb4822151d9cd3d585ca530f00f678c365f8e3696ec09494dc9c15cc7a57cd`;
  service host
  `69ecf8b1e59257d5f715ef3ebcb96bc10413a62f3916ae65d0c134e26aef6c66`;
  notification monitor
  `e2521f86fe4612cc48b4a13c822785fe9441bc9a37fcf794bced7e00bdcb3559`;
  audit
  `74335c366544efb2c393eea4febdb9e16816c5468f809a6500ec58b9126ccf4e`;
  runtime payload
  `01e436ca5c25a9fbf47eb6397f5693041a6fb0854f7cbacd5fc0c390e3a5c69b`;
  Community Panel payload
  `6ec10936aca90596ded0a07d82a5b49725533d32cab652169126e875586280d6`.
- Next slice: owned Overview behavior. Final slice: remaining inherited
  status/fullscreen behavior and exact teardown.

## 2026-08-28 — Owned Taskbar Overview integration, build 73

- Checkout started clean at `cfe61da`; build 72 was already committed despite
  the incoming handoff describing it as uncommitted. No build 73 commit exists.
- `TaskbarOverviewIntegration` now owns dash visibility, Overview allocation,
  optional workspace isolation, number hotkeys/previews, and empty-space exit.
  `TaskbarServiceHost` retains the activation point after the primary panel.
- Signals, timeouts, keybindings, suppressed native bindings, and exact method
  descriptors are transactional. Restoration reports conflicts instead of
  overwriting another extension. No actors are created.
- Telemetry and strict audit cover implementation, activation, signals/hooks,
  settings coherence, Overview/search/app-grid state, restoration, counters,
  pending work, conflicts, and orphan actors. Tests require the runtime import
  and absence of the inherited module.
- Sources reviewed on 2026-08-28: GNOME Shell 50.4 target
  `233322b9b675b0385767147c1a6cfc6ff7325160`; Shell main
  `6db7eaf5377e24d85eb9251316a8b2b5ca407cc4`; Dash-to-Panel master
  `1c0c1f1354bfaccbf2539ef516ec527bea498a51`; official GJS Extension,
  `InjectionManager`, and review lifecycle guidance. No public API replaces the
  private Overview contracts. Reviewed hashes are recorded in
  `docs/COMMUNITY_PANEL_RUNTIME_MAP.md`.
- GNOME 50.4 passed in Classic and GNOME 51.beta in Hybrid: normal/maximized
  windows, search, app grid, application activation, workspace changes, menus,
  empty-space exit, 10 slow and 20 rapid cycles in both window states, Minimal
  native restoration, and Taskbar re-entry. The inherited
  `community-panel/.../overview.js` was removed only after both matrices passed.
- Final state: GNOME 50 BigGnome; GNOME 51 Hybrid; application/runtime labels
  equal; one `1280x800` monitor each; strict audit zero failures. Current-shell
  journals contain no build 73 error. GNOME 51 still logs the external GSConnect
  `wl_clipboard.js` final-type failure.
- Focused tests: `80 passed`. Full suite: `576 passed`, one known PyGI warning.
  Changed JavaScript syntax and diff checks pass. PKGBUILD/package versions are
  unchanged. Final local/GNOME 50/GNOME 51 SHA-256: runtime controller
  `9d918d47d5c48e8ab94fbafb662e157ad65489a322f01d392d29538f3fbd36ee`;
  service host
  `a53bc122e5ddacd00f701d272c73692d3f88f1e60f3d92dd098a6d52931fb72d`;
  Overview integration
  `0411e487cce6475141ae75eb88dbe292a7eed5d8116b30a30b8eea6fbd7170dc`;
  audit
  `a96b9abf4c1a75bf023bbf990f49a7a6e264aa72d602390691265b18e4e4d770`;
  runtime payload
  `50236f08080c1fddc1529fe9fe19d358887717eea4f07ac320c6ba78e865c60a`;
  Community Panel payload
  `ee34534c3b866291f5e13a0122bc5f69421177601ec54b3080714e6192bb6bb1`.
- Next and final migration slice: inherited status/fullscreen behavior and the
  exact-teardown gate. Do not mix it into build 73.
