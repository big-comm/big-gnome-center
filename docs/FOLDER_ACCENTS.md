# Folder accents

Papient's scalable folder SVGs expose `.ColorScheme-Highlight` with a default
blue value. GNOME does not supply KDE's color-scheme replacement for these
full-color icons. BGC materializes that declared color in a user-local theme.

- Supported bases: bigicons-papient, bigicons-papient-dark, bigicons-papient-light.
- Uses GNOME accent names/palette from `constants.ACCENT_COLORS`.
- Replaces only the SVG's declared highlight color. Geometry, opacity, emblems,
  fixed-color artwork and symbolic icons are retained. No generic SVG recoloring.
- Uses standard `index.theme` inheritance. Applications/devices inherit the base.
- Outputs immutable content-addressed themes beneath `$XDG_DATA_HOME/icons`
  (default `~/.local/share/icons`), with the `bgc-folders--` prefix and Hidden=true.
  Source theme directory metadata is retained. Blue restores the original base.
- No root privileges, source-icon edits, icon-cache invalidation tricks or GTK
  patches. Generated themes remain valid without BGC running.
- A debounced helper follower watches icon-theme and accent-color. Work runs in
  a subprocess with a deadline; stale completions cannot override newer choices.
  Layout transactions defer synchronization. Disable cancels pending work.
- Light/dark switching resolves generated themes back to their Papient base.
  UI lists hide generated variants and identify the user's base selection.
- Missing sources, locked settings and generation failures preserve the current
  selection. Custom themes remain untouched. Previously generated directories
  are retained, never recursively purged from a shared icon directory.
- AuditRuntime exposes `folderAccent`: status, base, accent, theme, icon count,
  pending state or error. The Python auditor flags generation failures.

## Validation

- Unit coverage: palette/bases, aliases, fixed-color assets, source preservation,
  content updates, collisions, unsupported themes, blue restoration, UI and layout.
- GJS test uses the memory settings backend and isolated XDG paths. Covers busy
  transactions, rapid changes, custom themes and cancellation.
- GNOME 51 VM: temporary follower produced 214 purple icons. Direct VM capture
  confirmed Nautilus folders and special folders kept Papient shapes. Restored
  prior icon-theme/accent automatically. Local package 26.09.12-1618 installed;
  helper build 81 awaits login. Source hashes match. Integrated test pending.
- Full local suite: 898 passed. Backup and test package in
  `/var/tmp/bgc-folder-accent.z9Z9Iu`; previous package retained in
  `/var/tmp/bgc-local-refresh.mCZunA`. Mutter 51rc-1.1 unchanged.
- GNOME 50.4 VM: local package 26.09.12-1618 installed without conflicts.
  GTK 4.22.4 / Mutter 50.4 unchanged. Direct VM capture confirmed green folders
  and special folders via the temporary follower (214 icons). Blue restoration
  returned status=original; saved settings restored. User confirmed working after
  the request to test the updated session. Backup and previous package:
  `/var/tmp/bgc-folder-accent-50.6HE4YL`.

References:
- https://specifications.freedesktop.org/icon-theme/latest/
- https://github.com/biglinux/bigicons-papient
