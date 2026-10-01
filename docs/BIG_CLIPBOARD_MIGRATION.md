# Big Clipboard integration

2026-09-28. Dependency: `gnome-shell-extension-big-clipboard`.

The renamed package provides/replaces `gnome-shell-extension-copyous`. All six layouts use `big-clipboard@communitybig.org`. Saved layouts and pre-session activation lists migrate from `copyous@boerdereinar.dev` only when the replacement is installed. Explicit clipboard disablement is preserved. Legacy storage, settings and D-Bus identifiers remain compatible; both UUIDs protect the same clipboard settings subtree.

VM testing exposed a retention regression: applying an original layout wrote `history-length=70`, reducing a 120-entry fixture to 70 ordinary entries plus 24 pins. Layout application now reads the live clipboard subtree before mutation and preserves it in both the applied settings and persisted snapshot. A failed read aborts application before writes. Original layouts and older saved snapshots cannot override personal retention, database location, shortcuts or language selection.

Validation:

- 341 focused layout/settings tests passed; six GTK tests skipped without their display environment.
- GNOME 50.4 and 51.0: original BigGnome → Desk UX → Hybrid → G-Unity → Classic → Minimal. Big Clipboard opened with 12 cards and 120 stored entries in every layout.
- Exact SQL dump and hashes of 40 PNGs preserved; 24 pins retained. Clipboard settings retained except the extension's existing deprecated paste-option migration when opening preferences.
- Old package replaced through a local pacman repository; its dependency remained satisfied by the new package. Fresh login, Unicode text/image copying, search and optional highlighting passed on both VMs.

Scope: clipboard integration. VM 51 has an incompatible Big Shot user override (`St.BoxLayout.vertical`) and unavailable GTK4 desktop icons. VM 50 logged a framebuffer-size assertion during a transition. These external findings were recorded, not changed in this migration.

A final fresh login retained all 120 entries and preferences on both VMs; Super+V opened 12 cards. Original user preferences/history were restored after testing. VM viewers left open.

UUID migration follow-up:

- GNOME 50.4 and 51.0 package upgrades and fresh logins passed with the new UUID. Enabled/disabled state, global disablement and repeated migration were checked.
- Repeated all six layouts per VM with 120 entries, 24 pins and 40 images. Exact SQL, image/JSON/action hashes and clipboard settings remained unchanged; default and custom SQLite paths passed.
- Old saved layout UUIDs migrated to the replacement in live and persisted settings. JSON history, preferences, copying, search, pinning and Super+V passed.
- Original VM histories/preferences restored and verified. Full BGC package check: 1,735 passed.
