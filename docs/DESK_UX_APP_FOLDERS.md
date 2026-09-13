# Desk UX app folders

Community Menu v25. Applies to the grid layout used by Desk UX. Classic and
Hybrid retain their existing views.

## Availability

Desktop settings expose Community Menu in all six layouts. Classic, Desk UX,
and Hybrid retain enabled defaults; BigGnome, G-Unity, and Minimal retain
disabled defaults. Applying an original ignores inherited menu enablement and
clears that preference only after success. Manual toggles remain available in
every layout; snapshot restores retain explicit overrides. All three menu styles
remain selectable in every layout.
Strict runtime audits honor the same explicit preference before profile defaults.
The obsolete availability hint was removed from all application catalogs.
Defaults are tested against all six shipped profiles with absent, enabled, and
disabled preferences, including original restoration and failed-apply cleanup.

## Behavior

- Pinned apps use independent menu order. Copy GNOME Shell favorites once on
  first use; subsequent pinning, removal, and reordering never change the dock.
- App context menus expose a Pinned Applications switch, including search results.
- Back stays at the end of every internal header, including folder rename mode.
- Folder header color button and context action expose the ten system accent
  colors. Default restores the existing ID-based tint. Selection persists by ID.
- List rows reserve a fixed icon column and vertically center single-line names
  and descriptions. Action rows follow the same horizontal layout.
- Navigation fades out for 60ms and in for 110ms. Rapid navigation cancels stale
  callbacks; closing, dragging, and destruction restore full opacity. Disabled
  animations and reduced motion skip the transition. No geometry animation.
- Folder cards read native GNOME names, categories, apps, and exclusions.
- Open folders inside the menu. Rename reveals the name field; Enter/button saves.
- Drag an app onto another app to create a folder; onto a folder to move it.
- New Folder offers keyboard-accessible selection. Requires two distinct apps.
- Selection boxes are visible before clicking. A localized numeric counter tracks
  selection against the two-app minimum; a name alone does not enable creation.
- Tiles reserve equal icon/label regions. Folder previews use three 35px icons
  in a row, stable ID-based tints, and localized application counts.
- Favorites have an Add Applications picker. Existing folders support bulk adding.
- Move to Folder opens an internal searchable, scrollable destination picker.
- Creation and selection actions remain outside the scrolling content.
- All Apps supports grid/list and ascending/descending locale-aware ordering.
- Recent Applications records up to 24 IDs in memory while this menu instance is
  alive. Tracks launches and RUNNING transitions; no inferred startup history.
  Clear affects this list only. Honors `org.gnome.desktop.privacy:remember-app-usage`.
- Right-click/Menu key offers move, ungroup, create, and native app actions.
- Drag onto the pinned section to pin; onto a pinned app to insert/reorder.
- Drag onto Other Applications to remove membership; context actions also ungroup.
- Scroll edges while dragging. No nested folders.
- Keep one-app folders. Remove a folder after its last effective app is moved out.
- Dissolving a folder removes organization only, never applications.
- Search retains the existing Shell providers. All Apps includes grouped apps.

## Data and safeguards

`org.gnome.desktop.app-folders:folder-children` and relocatable
`org.gnome.desktop.app-folders.folder` settings are the sole folder store.
No duplicate database, overview actor reparenting, or private AppDisplay mutation.

Menu pins use `org.gnome.shell.extensions.community-menu.pins:apps` at
`/org/communitybig/community-menu/pins/`, outside layout-owned extension resets.
An explicit empty list stays empty across restarts. Hidden/uninstalled IDs remain
stored. Bulk pinning writes one ordered list; locked/rejected saves retain selection.

Folder color overrides use `org.gnome.shell.extensions.community-menu.folders:colors`
at `/org/communitybig/community-menu/folders/`. Only visual metadata is stored;
native folder membership remains unchanged. Invisible folder colors are retained.
The picker reuses the translated theme palette from `big-gnome-center` catalogs.

Moving a category member records an exclusion in its source folder. Moving into
a folder clears that app's exclusion. Explicit moves normalize duplicate
membership; merely opening the menu does not rewrite user organization.

Display filtering respects visibility and parental controls. Empty filtered
folders are hidden, not deleted. Hidden/uninstalled explicit app IDs are retained.
Menu pins remain folder members. GNOME's overview independently filters its own
Shell favorites inside folder views.

Pure operations validate before writes. The adapter preflights all affected keys
and rolls back accepted writes if a setter rejects a change. GSettings does not
provide a cross-schema transaction; external writers and backend failures remain
outside that guarantee. Detached folder settings remain as recovery data, as
only IDs listed in `folder-children` are displayed.

Refreshes are coalesced. Drag actors are retained until drag completion. Timers,
drag monitors, settings signals, and secondary menus are released on destruction.
Search interception is suspended for the inline name editor. Native feature
detection retains compatibility with both supported Shell releases.

Sizing uses the parent menu's explicit logical width, not child allocations.
This prevents theme and allocation feedback from reducing columns in GNOME 51.
Recompute tile widths when the monitor-constrained menu width changes. Never
query preferred geometry while rebuilding children. The menu respects monitor
work area and a 640px natural
height. Internal views use their own filter, hiding the global search field.
Preferred size: 700 × 640px; four folder columns at normal scale. Folder and
pinned cards use equal content width/height, capped at 124px and 94px respectively.
All app grids use the same compact square cards, including New Folder, Add
Applications, Other Applications, and All Apps. List mode retains horizontal rows.
Folder previews use 35px icons; favorites retain 48px icons. The session footer
keeps Log Out, Suspend, Restart, and Power Off; no replacement with Lock.

Refinements: centered grids keep 10px gaps on both axes; no flexible gap columns.
Cards retain square dimensions. Section headings share a 12px horizontal inset.
Pinned apps and folders share aligned, full-width rounded section backgrounds.
Each panel contains its heading, action, and grid; tile dimensions stay unchanged.
Folder cards grow from 138px to 152px overall (10%, pixel-rounded), including
35px icons, 13px padding, and 1.1em text. App cards remain unchanged. Folder rows
reserve 40px for outer insets; app rows retain their conservative 64px budget.
Session padding is 5px vertically (6px less total height). Scroll edges use a
12px native fade and a non-stacking 4px, 240ms feedback translation. Closing,
rebuilding, or dragging resets it. No adjustment values or allocations change.
Animations honor `enable-animations` and GNOME 51's optional `reduced-motion`.
Overlay scrollbars start hidden. Pointer motion anywhere in the menu reveals
them in 120ms; 1000ms idle fades them out smoothly over 2000ms. Pressed buttons,
native drag signals, and hover/focus keep scrollbar interaction available.
Pointer-button state handles releases outside the menu. Closing cancels the
timer and resets interaction state and opacity; layout
and scroll positions remain unchanged.
APIs checked against the installed GNOME 50/51 typelibs and
[St.ScrollView](https://gnome.pages.gitlab.gnome.org/gnome-shell/st/method.ScrollView.update_fade_effect.html).

## List, colors, and navigation validation — 2026-09-13

- Full suite: 969 passed; one existing GLib deprecation warning. Focused: 68 tests.
- Covers fixed list icon columns, horizontal action rows, system palette parity,
  all translated labels, narrow palettes, persistence, and interrupted fades.
- Memory-backed color tests passed on GNOME 50.4 and 51.rc; installed hashes match.
  Fresh-session visual validation of alignment, palette, and fade remains pending.
- Backups: GNOME 50 `/var/tmp/bgc-menu-refinements.a5g7n065`; GNOME 51
  `/var/tmp/bgc-menu-refinements.d49_hhct`.

## Independent pins validation — 2026-09-13

- Full suite: 967 passed; one existing GLib deprecation warning.
- Focused: 66 menu tests; header order, tile/search context toggles, drag order,
  one-time migration, empty state, hidden IDs, and locked/rejected writes.
- Memory-backed GJS persistence tests passed on GNOME 50.4 and 51.rc.
- Installed three JavaScript files and the schema on both VMs; hashes matched.
  Real Shell favorites remained unchanged. Fresh-session visual validation pending.
- Backups: GNOME 50 `/var/tmp/bgc-menu-pins.kwuz7q8g`; GNOME 51
  `/var/tmp/bgc-menu-pins.ps8mh1wa`. `absent.json` records newly introduced files.

## v25 validation

- Refinements: 935 tests passed; three existing GI/theme warnings. Native fade
  API verified on both VMs. Final visual validation after login remains pending.
- Reopen regression: GNOME 50 retained four folder columns and five pinned tiles
  after ten Super-key close/open cycles with the fixed parent-width budget.
  GNOME 51 files match. User confirmed the corrected layout after deployment.
- Sizing regressions cover transient child widths, 1x/2x scale, and narrow monitors.
- Initial suite: 934 passed, three existing GI/theme warnings.
- Focused: responsive columns, same-column resizing, search normalization, stable
  tints, bounded recent history, folder operations, and all 29 compiled catalogs.
- Initial GNOME 50 visual check caught 48px tiles from premature geometry reads.
  Corrected by caching allocated width and deferring rendering until mapped.
- Updated candidates copied to GNOME 50.4 and 51.rc, with backups. Final visual
  checks after new login remain pending; do not treat static tests as UI approval.
- Eight new strings translated in 29 locales; one unused hint removed. Each
  compiled catalog contains 61 translated messages.

## v24 validation — 2026-09-12

- Full suite: 902 passed; three existing GI/theme-test warnings. Focused Ruff,
  JavaScript syntax, gettext catalog checks, and diff whitespace checks passed.
- Node: membership, category exclusions, creation threshold, move, rename,
  single/empty folders, invalid IDs, hidden/uninstalled records, input immutability.
- GJS with memory settings: native schema writes, locks, rejected writes, rollback.
- Node: mapped/search/editor input-interceptor truth table.
- GNOME 51.rc VM: home, folder view, app context menu, native drag-to-create,
  keyboard rename, drag out, single-folder preservation, last-app removal.
- GNOME 50.4 VM: home, search/providers, select-two-and-create UI.
- Both VMs: original folder settings restored and compared byte-for-byte.
- Final editor-interceptor, selection-badge, label-wrap, and edge-scroll revision:
  copied to both VMs; fresh-session visual validation pending.

Earlier UI candidates logged Clutter input-focus assertions when adding/editing
folder entries. They remain reproducible with v24 in the GNOME 50 session; do not
claim them resolved. Calendar search provider timed out
once on GNOME 50; application results still populated.

Follow-up: reproduced the creation report on GNOME 50. Two app selections enabled
the button with the entered name; no folder was saved during that diagnostic.
Alignment, larger previews, and visible selection affordances are revised and
copied to both VMs. Follow-up suite: 903 passed, one GI deprecation warning.
Fresh-session visual validation of these follow-up changes remains pending.

Fourteen new strings translated in all 29 supported locales with the user's
authorized model substitution. Existing translations preserved. Templates and
compiled catalogs refreshed; gettext checks passed. Per-locale tests verify Desk UX
message coverage and packaged catalog consistency. Visual locale checks pending.
Final suite: 932 passed, three existing GI/theme warnings. All 1,160 prior
translations preserved; all 29 catalogs contain 54 translated messages.

## References

- [GNOME folder behavior](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/main/js/ui/appDisplay.js)
- [GNOME drag/drop](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/main/js/ui/dnd.js)
- [GNOME favorites](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/main/js/ui/appFavorites.js)
- [GNOME search input handling](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/main/js/ui/searchController.js)
