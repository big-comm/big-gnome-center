# Wallpaper Color Integration

Status: proposed; implementation not started.

## Goal

Add a global Desktop option that derives an accent from the active wallpaper
and tints the desktop consistently. Expose four strengths: Subtle, Default,
Strong, and Stronger. Recompute after wallpaper, color-scheme, or layout
changes.

## Reference audit

Reference: ChromaLeon commit
`97545fc94342321dfbbdd3067a7dfc535ef4a3f1` (2026-08-28).

Relevant behavior:

- Read `picture-uri` or `picture-uri-dark` from
  `org.gnome.desktop.background`.
- Scale the image to 64x64, quantize pixels, rank saturated mid-lightness
  colors, and enforce usable contrast.
- Apply wallpaper-derived accent and tint CSS to GNOME Shell, GTK 4, and
  optional GTK 3.
- Map four strength levels around the default tint mix.
- Watch wallpaper, color-scheme, and feature settings.

Excluded behavior:

- Wallpaper picker.
- Icon-theme copying or SVG recoloring.
- Flatpak permission management.
- Custom user CSS editor.
- GTK hot-reload workarounds.
- Full replacement GNOME Shell themes.

ChromaLeon is GPL-3.0-or-later; Layout Switcher is MIT. Do not copy its source
or templates into this project. Implement the documented behavior independently
and retain the upstream commit only as design provenance.

## Upstream limitations

ChromaLeon does not support Qt 5 or Qt 6. It has no qt5ct, qt6ct, KDE Colors,
Kvantum, `kdeglobals`, or Qt palette integration.

BigLinux provides `sync-gnome-theme-to-qt.path`, but its current service only
selects fixed light/dark Kvantum themes and copies fixed `kdeglobals` palettes.
It does not read the wallpaper color or GNOME arbitrary accent values. It can
overwrite independently generated Qt state after dconf changes.

Qt support therefore requires explicit ownership and coordination, not only a
call to the existing watcher.

## Proposed UI

Add a `Wallpaper colors` group to Desktop:

- `Use wallpaper colors` global switch; disabled by default.
- `Color intensity` combo with Subtle, Default, Strong, and Stronger.
- Optional read-only swatch for the derived color.

The setting is global, not layout-specific. Layout snapshots may change the
wallpaper, but must not silently change the user's feature preference.

## Proposed ownership

Use the existing Layout Switcher settings and helper lifecycle. The feature
must remain active after the GTK application closes.

- Persist enabled state, strength, and derived color in the project schema.
- Let the always-enabled Shell helper watch wallpaper and color-scheme changes.
- Load a small project-owned Shell overlay; never replace the base Shell
  stylesheet with `setThemeStylesheet()`.
- Write GTK 3/4 overrides atomically with unique ownership markers.
- Remove only owned blocks/files when disabled.
- Detect modified or conflicting owned files before restoration.
- Preserve layout classes, Frosted Glass, and runtime styles.

## Qt design boundary

Qt 5/6 support is a separate implementation phase:

- Generate matching light/dark KDE palette values.
- Generate or derive user-owned Kvantum variants for both Qt generations.
- Coordinate with `sync-gnome-theme-to-qt.path` so it cannot restore fixed
  palettes over the derived state.
- Restore the previous Kvantum theme and `kdeglobals` state exactly.
- Do not claim coverage for applications that ignore the configured Qt style.

Changing the external `comm-gnome-config` package is outside this repository.
Prefer a documented coordination contract over competing file watchers.

## Failure handling

- Reject unsupported or unreadable wallpaper URIs without losing the last
  valid state.
- Support packaged AVIF wallpapers used by all six layouts.
- Serialize updates and cancel stale extraction jobs.
- Use atomic writes and bounded retries.
- Keep a last-known-good derived color.
- Restore owned Shell, GTK, and Qt state transactionally.
- Never overwrite unrelated user CSS or theme configuration.

## Delivery phases

1. Independent color extraction with deterministic unit fixtures.
2. Settings, Desktop UI, persistence, and accessibility.
3. Shell overlay lifecycle on GNOME 50 and 51.
4. GTK 4 and GTK 3 owned CSS lifecycle.
5. Layout transition and wallpaper-change integration.
6. Qt 5/6 palette and Kvantum coordination.
7. Strict audit telemetry, rollback checks, documentation, and full validation.

Shell and GTK must pass before Qt ownership is enabled. Qt completion is not a
prerequisite for testing the earlier phases, but the UI must state actual
coverage until it passes.

## Validation gates

- Unit fixtures for extraction, contrast, strength mapping, and invalid input.
- Atomic ownership and exact restoration tests for every generated file.
- Light/dark wallpaper and color-scheme changes.
- Every layout, including transitions while the feature is enabled.
- Native Shell styling and Frosted Glass coexistence.
- GTK 3 and GTK 4 native and Flatpak applications.
- Qt 5 and Qt 6 applications using the supported Kvantum path.
- Ten slow and twenty rapid update cycles.
- Helper teardown/re-entry with no stale stylesheet or watcher.
- Strict runtime audit and clean journal on GNOME 50 and 51.
- Matching local/VM SHA-256 after every deployment.
- Final state: GNOME 50 BigGnome, GNOME 51 Hybrid, one monitor each, and
  application/runtime layout state aligned.

## Complexity

Overall complexity: high.

- Color extraction and UI: medium.
- Shell overlay: medium-high because six layouts and two Shell versions share
  stylesheet ownership.
- GTK ownership and restoration: high because user files are shared state.
- Qt 5/6: high because the external watcher currently owns fixed Kvantum and
  KDE palette files.

The main risk is lifecycle and restoration, not color calculation. Deliver in
separate checkpoints; do not combine this work with unrelated corrections.
