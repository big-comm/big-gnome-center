# Layout switch regression — 2026-09-27

## Cause

`MainWindow._on_ext_changed()` refreshes an already-created Panel and Dock
page while the layout worker is applying a new profile. Its settings adapter
used the previous UI label to write `runtime/active-layout`. This competed
with the layout transaction and could rebuild the previous surface mid-switch.

Reproduced on GNOME 50.4 and 51.0 with saved layouts:
Classic → G-Unity → Classic → BigGnome. Repeating the normal UI refresh every
250 ms during application makes the race reproducible. The final date actor
was a direct child of `Main.panel`, despite the taskbar being inactive. Its
clock text still updated, but the native panel did not allocate it correctly.
Calendar/notifications remained attached to the displaced actor.

Separately, commit `64a8342` removed the Quick Settings shutdown policy for
Classic, Hybrid and Desk UX.

## Changes

- Settings-page refresh no longer selects the runtime profile.
- Original and saved layouts select their target inside the transaction.
  Saved opacity and other overrides remain intact.
- Restore shutdown-action suppression when Community Menu provides session
  actions; disconnect the visibility handler and restore Shell policy on teardown.
- Expose shutdown-action visibility in the existing read-only runtime audit.

## Validation

- Local suite: 1,722 passed.
- Before correction: all 30 directed pairs of original layouts completed in
  both VMs. The concurrent-refresh saved-layout sequence reproduced the missing
  clock in both VMs. Ordinary switching alone did not reliably reproduce it.
- Helper build 111 confirmed in both logged-in VM sessions after installation.
- The same four-step saved-layout reproduction passed after correction in both VMs.
- Final full matrix and visual checks: incomplete. GNOME 50 completed 21
  steps, then Shell crashed during menu interaction before step 22 completed.
  Do not treat this commit as full layout-switch stability validation.

Artifacts: `/tmp/bgc-clock-regression/` (host). Includes before/after audits,
screenshots and test scripts. VM tests exercise the actual GTK application
callbacks and GNOME Shell; they do not use Shell Eval or replace Shell actors.

## Additional observations

- GNOME 51 reports Copyous and GTK4 DING unavailable; these are optional
  extensions. Layout transactions report this instead of claiming activation.
- GNOME 50 logged a separate delayed taskbar hover callback accessing a
  disposed app icon (`taskbar.js:804`, `utils.js:613`).
- GNOME 50 Shell exited with SIGSEGV at 00:50:45 (PID 59862). No core was
  retained. A viewport-size assertion preceded the crash; causality remains
  unconfirmed. This crash is unresolved by the changes recorded here.
- GNOME 51 logged a `g_variant_unref` assertion from `gsd-keyboard` at login.

These observations prevent treating layout coverage as a claim that every
desktop feature or journal entry is error-free.
