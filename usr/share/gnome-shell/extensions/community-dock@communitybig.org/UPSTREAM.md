# Community Dock upstream provenance

Community Dock starts from Dash to Dock 106 as packaged for BigLinux on
2026-07-25. The GNOME 50 and GNOME 51 beta installations contained identical
core JavaScript files at the time of import.

Upstream project: https://github.com/micheleg/dash-to-dock

Original author: Michele G.

License: GPL-2.0-or-later. `COPYING` is preserved unmodified.

Local changes:

- Distinct `community-dock@communitybig.org` UUID and Community Dock identity.
- Bundled schema source for independence from the external package.
- Layout Switcher lifecycle integration and BigCommunity layout defaults.
- Selectable BigCommunity running-indicator styling and controller owned by
  Community Dock.
- BigCommunity panel opacity and visibility controller with an independent schema.

Do not remove upstream copyright or license notices. Keep functional parity
until BigGnome and G-Unity have passed live comparison and rollback testing.
