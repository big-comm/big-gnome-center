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
