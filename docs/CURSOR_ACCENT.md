# Cursor accent matching

The cursor gallery offers opt-in system accent matching. The setting defaults
to false in `org.communitybig.big-gnome-center.themes::cursor-follow-accent`.
The cursor package provides palettes and assets; installing it does not change
the selected cursor or enable matching.

`cursor_accent.py` selects installed `Bibata-Material-*` themes using the active
GNOME accent and color scheme. It prefers the corresponding hue family, then
uses the upstream CIEDE2000 matcher to choose within that family. This prevents
neutral gray palettes from winning against blue or purple accents. Light mode
uses `-Light` variants; `default` follows GNOME's default light appearance.

The matcher comes from Sakib Shahariar Shimanto's Material Bibata Cursor,
commit `517f397`. The MIT notice is installed as `LICENSE.material`.

A unique Gio.Application runs only while matching is enabled. The settings
window starts it immediately; XDG autostart restores it after login. It observes
accent, color-scheme, cursor-theme and preference changes. Manual cursor changes
disable matching, including changes made by other settings applications.
Turning matching off keeps the current cursor. Missing themes and locked cursor
settings never force a fallback or overwrite the user's selection.

Runtime validation uses private D-Bus sessions and temporary XDG configuration
directories. This tests the separate watcher process without changing the
visible desktop. Visual review remains separate from these checks.

## Maia on GNOME 51: deferred

Observed on 2026-09-16:

- GNOME 50.4 VM: Manjaro `gsettings-desktop-schemas 50.1-1` accepts `maia`;
  the user confirmed successful application.
- GNOME 51.0 VM: Arch `gsettings-desktop-schemas 51.0-1` accepts only the nine
  upstream accents. Applying `maia` fails with an out-of-range error before
  cursor matching runs.

Maia is a downstream Manjaro addition. The failure is independent of the
cursor-follow setting. User decision: wait for Manjaro's GNOME 51 packages
and recheck Maia support; its availability is not yet confirmed. Keep Maia
visible and retain the existing cursor palette mapping. Do not port the
downstream patches or modify VM packages for this issue now.

The proposed unsupported-color filtering was withdrawn. No changes from that
attempt were installed in either VM. After the Manjaro update, verify the
installed accent range, Maia application, and cursor following again.
