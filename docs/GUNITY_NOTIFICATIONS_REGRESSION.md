# G-Unity notification expansion

## Cause

QuickSettingsLayout allocates rows at natural height. Expanded notification
groups exceeded the work area, placing the open popup above the screen.
GNOME 50 reproduced a 923px popup at y=-923 on an 800px display.
Calendar capture handlers also remained attached to the original date menu.

## Fix

- Bound the notification row by available monitor space minus controls and chrome.
- Retain native notification scrolling.
- Route native capture events on GNOME 50; transfer the capture container on 51.
- Collapse groups on close. Disconnect owned handlers and restore the calendar
  capture container when leaving G-Unity.
- Helper build: 112.

## Validation — 2026-09-27

- Focused pytest after card styling: 238 passed; one existing deprecation warning.
- Logged-in GNOME 50.4 and 51.0 VMs: 28 distinct interaction checkpoints passed.
  Group expansion/collapse, repeated close/reopen, light/dark changes, and
  G-Unity → Minimal → G-Unity followed by expansion and reopening.
- Real pointer/keyboard input; popup bounds and group state collected by temporary
  read-only probes. No date-menu click needed to recover Quick Settings.
- Evidence: `/tmp/bgc-notification-regression/interaction-results.json`, screenshots
  and guest diagnostics. Temporary probes restored and disabled after testing.
- Installed in both VMs only. Host package unchanged.

## Opaque notification cards

Light Quick Settings with Frosted Glass set notification card alpha to 0.34
in the runtime stylesheet. Stacked cards exposed underlying text. Card backgrounds
are now opaque in Quick Settings and the calendar, including hover/focus styles.
Menu material settings remain unchanged. Light/dark grouped and expanded cards
were visually inspected in both VMs; reopening also passed after CSS reload.
Evidence: `*-opaque-*.png` in the directory above.
GNOME 51's existing light-theme group heading has low contrast over the dark
glass tint; outer menu styling remains outside this card-background fix.
This fix does not address the earlier Shell crash documented in
`LAYOUT_SWITCH_REGRESSION.md`.
