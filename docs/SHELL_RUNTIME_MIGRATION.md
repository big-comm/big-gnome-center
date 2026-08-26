# Shell Runtime Migration Plan

Last update: 2026-08-26
Status: Dock extraction complete; Taskbar/Panel lifecycle extraction accepted

The actionable remaining-work checklist is maintained in
[`SHELL_RUNTIME_REMAINING_WORK.md`](SHELL_RUNTIME_REMAINING_WORK.md).

## Goal

Replace the bundled Dash to Dock and Dash to Panel forks with a focused Shell
runtime owned by Layout Switcher. Preserve the six accepted layouts while
removing unused preferences, menus, schemas, assets, and runtime branches.

User-facing configuration must exist only in Layout Switcher.

## Architecture decision

GNOME Shell actors cannot be implemented by the external GTK/Python process.
Dock, taskbar, and panel code must still run inside GNOME Shell as GJS.

Target architecture:

```text
Layout Switcher GTK app
  -> own GSettings schema
  -> Layout Switcher Helper (switch orchestration only)
  -> Layout Switcher Shell runtime (dock, taskbar, panel)
```

The Shell runtime must:

- have no `prefs.js` or independent preferences window;
- expose no Dash to Dock or Dash to Panel settings action;
- use only Layout Switcher-owned settings;
- activate modules according to the current layout;
- remain modular so one component failure does not break layout switching;
- support GNOME 50 and GNOME 51 without version-specific user configuration.

Do not merge the runtime into the helper. The helper owns D-Bus switching and
must remain available if a visual component fails.

## Baseline

Current inherited runtime:

| Component | Approximate size | JS/CSS lines |
|---|---:|---:|
| Community Dock | 920 KiB | 15,761 |
| Community Panel | 1.6 MiB | 16,955 |
| Combined | 2.5 MiB | 32,716 |

These numbers are measurement baselines, not fixed reduction targets. Record
them again after every cleanup phase.

## Product rules

- Keep a curated, Deepin-like control surface; do not build a general Shell
  editor.
- Preserve current layout defaults exactly until the user accepts a change.
- Add only controls that are useful to the supported layouts.
- Prefer illustrated choices over technical drop-downs and raw values.
- Store user overrides per layout; never let one layout overwrite another.
- Provide `Restore layout defaults` for every configurable component.
- Hide or disable controls that the active layout does not use.
- Apply changes live, with debouncing for sliders.
- Define safe minimum and maximum values after GNOME 50 visual measurement.
- Keep rollback available until the replacement is visually accepted.
- Do not delete inherited runtime code before its replacement passes tests.
- Never change `PKGBUILD` version fields as part of this migration.

## Configuration scope

### Existing controls to preserve

- [x] Dock opacity.
- [x] Dock visibility: always visible, always hidden, intelligent.
- [x] Panel opacity.
- [x] Panel visibility: always visible, always hidden, intelligent.
- [x] Running indicator: dot, Hybrid line, Desk UX line.
- [x] Layout-specific behavior and indicator geometry.

### First new controls

- [x] Dock icon size / thickness through the transition adapter.
- [x] Panel height through the transition adapter.
- [x] Dock icon hover feedback: current behavior or Hybrid-style lift.
- [x] Illustrated hover-effect cards with live preview.
- [x] Safe minimum and maximum per component.
- [x] Per-layout saved value in the owned runtime schema.
- [x] Restore the active layout's default value.
- [x] Live preview without restarting the session.

The height controls should describe the visible result. Internal icon size,
padding, and actor allocation remain implementation details.

### Good follow-up candidates

- [ ] Dock position: left, bottom, right.
- [ ] Dock length: fit content or fill available edge.
- [ ] Multi-monitor target: primary monitor or all monitors.

Add these only after the size controls and runtime foundation are accepted.

### Possible future controls

- Show Applications button visibility.
- Trash visibility.
- Mounted volumes visibility.

Keep their current layout defaults initially. Add them only after a concrete
user need; they must not enlarge the first configuration surface.

### Intended initial page

Dock, when available:

- opacity;
- visibility;
- size;
- running indicator style;
- hover feedback.

Panel, when available:

- opacity;
- visibility;
- height.

No icon spacing, arbitrary alignment, padding, margin, or element-order editor.

### Deferred advanced options

- Mouse-button action remapping.
- Scroll actions.
- Multiple animation engines.
- Advanced window-preview tuning.
- Arbitrary panel-element editors.
- Import/export of dock or panel preferences.

These options reproduce the complexity being removed and are out of the
initial scope.

## Layout contracts

| Layout | Runtime surface | Required default |
|---|---|---|
| BigGnome | bottom dock + native top panel | Desk UX indicator |
| G-Unity | left dock + native top panel | dot indicator |
| Hybrid | bottom taskbar/panel | Hybrid indicator |
| Desk UX | bottom taskbar/panel | Desk UX indicator |
| Classic | bottom labeled taskbar/panel | no running indicator |
| Minimal | native top panel only | dock/taskbar controls unavailable |

Each contract must cover launch, focus, minimize, multiple windows, favorites,
running state, notification badges, context menus, overview, workspace changes,
fullscreen, visibility, and monitor changes.

## Phases and approval gates

### Phase 0 — Inventory and regression baseline

- [x] List inherited modules and map active schema sections by layout.
- [x] Record current installed size and source line count.
- [x] Build a six-layout behavior matrix.
- [x] Add focused baseline and transition-contract tests.
- [x] Capture GNOME 50 reference screenshots and measurements.
- [x] Capture GNOME 51 reference screenshots and measurements.
- [x] Review GNOME 51 runtime behavior before extraction.

Gate: baseline reviewed. No runtime behavior changed.

Evidence: [`baselines/README.md`](baselines/README.md). GNOME 50.4 and GNOME 51
beta passed the same clean-session matrix. Their actor-allocation differences
are recorded and must not be normalized blindly during extraction.

### Phase 1 — Centralize configuration safely

- [x] Remove Dock and Panel preferences entry points.
- [x] Remove settings items from application context menus.
- [ ] Keep runtime behavior unchanged.
- [x] Confirm source exposes supported controls only through Layout Switcher.
- [x] Remove preference UI files after package validation.

Gate: all six layouts visually accepted on GNOME 50.

### Phase 2 — Own settings model

- [x] Create a Layout Switcher-owned runtime schema.
- [x] Define layout defaults separately from user overrides.
- [x] Add per-layout reset behavior.
- [x] Add the per-layout reset backend; expose it after the size controls land.
- [x] Migrate current values once without overwriting unrelated settings.
- [x] Add dock size and panel height controls.
- [x] Keep an adapter to inherited schemas during transition.
- [x] Add the unified Shell runtime extension.
- [x] Encode the six accepted layout surface profiles.
- [x] Persist the active layout during every original-layout apply.
- [x] Stage the runtime before replacing accepted components.

Foundation details:

- Schema: `org.communitybig.layout-switcher.runtime`.
- Accepted defaults live in `runtime_settings.py`; GSettings stores overrides only.
- Existing Dock and Panel values are imported once for each active layout.
- Live writes are mirrored to the owned schema while inherited runtimes remain active.
- Runtime UUID: `layout-switcher-runtime@communitybig.org`.
- The original passive gate was removed only after both surfaces could be
  activated behind the unified controller.

Gate: upgrade and clean-install tests accepted on GNOME 50.

### Phase 3 — Focused dock runtime

- [x] Extract only features used by BigGnome and G-Unity.
- [x] Preserve bottom and left placement.
- [x] Apply the layout-owned indicator profile before Dock activation.
- [x] Preserve favorites, running apps, badges, menus, and hiding.
- [x] Remove unused Dock preferences, UI, and runtime branches.
- [x] Compare both layouts against the accepted baseline.

Gate: BigGnome and G-Unity accepted before inherited Dock removal.

### Phase 4 — Focused taskbar and panel runtime

- [ ] Extract only features used by Classic, Hybrid, and Desk UX.
- [x] Own Taskbar/Panel construction, cancellation, and teardown in the unified
  runtime.
- [ ] Preserve system indicators, clock, taskbar boundaries, and menus.
- [x] Apply the layout-owned indicator profile before Taskbar activation.
- [ ] Preserve each layout's remaining icon and label rules.
- [ ] Preserve overlay-style panel hiding and intelligent hiding.
- [ ] Remove unused Panel preferences, UI, translations, assets, and branches.

Gate: Classic, Hybrid, and Desk UX accepted before inherited Panel removal.

### Phase 5 — Unified runtime transition

- [x] Enable the focused runtime through layout ownership.
- [x] Migrate active Community Dock and Community Panel users once.
- [ ] Keep external Dash to Dock and Dash to Panel packages untouched.
- [ ] Retain rollback for one testing cycle.
- [ ] Remove bundled fork UUIDs only after upgrade validation.

Gate: clean install and upgrade install accepted.

### Phase 6 — Final cleanup and GNOME 51

- [ ] Delete unused inherited schemas and compatibility adapters.
- [ ] Remove orphan assets, translations, and documentation.
- [ ] Record final size and source line reduction.
- [ ] Run package build and full automated suite.
- [ ] Validate every layout live on GNOME 50.
- [ ] Validate every layout live on GNOME 51.

Gate: user approval for testing repository publication.

## Validation checklist per change

- [ ] Focused automated tests pass.
- [ ] Full suite passes.
- [ ] JavaScript syntax passes.
- [ ] Schemas compile strictly.
- [ ] Package staging contains required runtime files.
- [ ] No independent preferences entry appears.
- [ ] Current layout still matches its reference.
- [ ] User approves the live GNOME 50 result.
- [ ] Completion state is updated in this document.

## Accepted decisions

- [x] Centralize all user-facing Dock and Panel configuration in Layout Switcher.
- [x] Keep a Shell-side runtime because GNOME Shell actors require it.
- [x] Remove independent fork preference screens and settings menu entries.
- [x] Migrate incrementally with visual approval between phases.
- [x] Add safe dock size and panel height controls.
- [x] Keep the accepted icon spacing fixed; do not expose a user control.
- [x] Use a curated, Deepin-like configuration surface with strong defaults.
- [x] Use illustrated controls when the visual result is easier to understand.
- [x] Add Hybrid-style icon lift as a focused Dock hover option.
- [x] Do not expose arbitrary start/center/end alignment.
- [x] Defer Applications, Trash, and mounted-volume toggles.

## Current transition checkpoint

- The unified controller owns Dock versus Taskbar activation.
- Indicator defaults are canonical and isolated per layout: BigGnome and
  Desk UX use Desk UX; Hybrid uses Hybrid; G-Unity uses dot; Classic uses none.
- Applying an original layout removes only that layout's runtime overrides.
  Overrides belonging to other layouts remain intact.
- Dock construction, behavior, executable modules, and reverse-order teardown
  are owned by the unified runtime. The retired Dock directory is a resource
  and schema host only.
- The Taskbar compatibility engine remains the only internal rollback module.
- Runtime build 51 owns `PanelManager` construction and teardown through
  `TaskbarSurfaceManager`. Inherited visual modules retain their accepted
  behavior behind a separate runtime context; the old entry point is a thin
  rollback adapter. Component stylesheets follow Shell theme replacement and
  unload from the current `St.Theme`, preventing duplicate/null CSS state.
- GNOME 50.4 passed all three affected surface cycles. GNOME 51.beta passed
  fresh activation, Taskbar-to-Dock-to-Taskbar, and direct disable/enable. The
  corrected runner then passed all eight surface directions on both versions.
  Strict audits require lifecycle ownership and zero actor residue.
- Next extraction slice: preserve and port application-button behavior without
  changing system status-area, clock, menu, indicator, or layout geometry.
