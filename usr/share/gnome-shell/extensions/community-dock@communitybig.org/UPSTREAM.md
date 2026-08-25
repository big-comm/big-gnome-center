# Community Dock upstream provenance

Community Dock starts from Dash to Dock 106 as packaged for BigLinux on
2026-07-25. The GNOME 50 and GNOME 51 beta installations contained identical
core JavaScript files at the time of import.

Upstream project: https://github.com/micheleg/dash-to-dock

Original author: Michele G.

License: GPL-2.0-or-later. `COPYING` is preserved unmodified.

Local changes:

- JavaScript runtime moved under the unified Layout Switcher runtime.
- Standalone Community Dock entry point and UUID metadata removed.
- Original resource directory retained for schemas, stylesheet, and media.
- Layout Switcher owns lifecycle, layout defaults, indicators, and panel policy.

Do not remove upstream copyright or license notices. Keep functional parity
through upgrade and rollback testing.
