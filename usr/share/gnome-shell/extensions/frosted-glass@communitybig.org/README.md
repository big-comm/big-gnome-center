# Frosted Glass

GNOME Shell 51 extension owned by Big Gnome Center. It applies a controlled
frosted-glass material to application windows and selected Shell surfaces.

Window blur only tunes native client requests through `ext-background-effect-v1`.
Applications must opt in. Window content and opacity are never modified.
Disabling window tuning restores the compositor's previous parameters; it does
not suppress blur requested independently by applications.

License: GPL-3.0-or-later.

Architecture, settings, testing, VM notes, and handoff status are documented in
[`docs/FROSTED_GLASS.md`](../../../../../docs/FROSTED_GLASS.md).
