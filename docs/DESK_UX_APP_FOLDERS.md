# Desk UX app folders

Community Menu v25. Applies to the grid layout used by Desk UX. Classic and
Hybrid retain their existing views.

## Behavior

- Pinned apps share GNOME Shell favorites and dock order.
- Folder cards read native GNOME names, categories, apps, and exclusions.
- Open folders inside the menu. Rename reveals the name field; Enter/button saves.
- Drag an app onto another app to create a folder; onto a folder to move it.
- New Folder offers keyboard-accessible selection. Requires two distinct apps.
- Selection boxes are visible before clicking. A localized numeric counter tracks
  selection against the two-app minimum; a name alone does not enable creation.
- Tiles reserve equal icon/label regions. Folder previews use three 32px icons
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

Moving a category member records an exclusion in its source folder. Moving into
a folder clears that app's exclusion. Explicit moves normalize duplicate
membership; merely opening the menu does not rewrite user organization.

Display filtering respects visibility and parental controls. Empty filtered
folders are hidden, not deleted. Hidden/uninstalled explicit app IDs are retained.
Pinned apps remain folder members here; GNOME's overview can hide pinned apps
inside its folder view.

Pure operations validate before writes. The adapter preflights all affected keys
and rolls back accepted writes if a setter rejects a change. GSettings does not
provide a cross-schema transaction; external writers and backend failures remain
outside that guarantee. Detached folder settings remain as recovery data, as
only IDs listed in `folder-children` are displayed.

Refreshes are coalesced. Drag actors are retained until drag completion. Timers,
drag monitors, settings signals, and secondary menus are released on destruction.
Search interception is suspended for the inline name editor. Native feature
detection retains compatibility with both supported Shell releases.

Sizing uses the mapped actor's cached logical width. Recompute tile widths even
when the column count remains unchanged. Never query preferred geometry while
rebuilding children. The menu respects monitor work area and a 640px natural
height. Internal views use their own filter, hiding the global search field.
Preferred size: 700 × 640px; four folder columns at normal scale. Folder and
pinned cards use equal content width/height, capped at 112px and 94px respectively.
All app grids use the same compact square cards, including New Folder, Add
Applications, Other Applications, and All Apps. List mode retains horizontal rows.
Folder previews retain 32px icons; favorites retain 48px icons. The session footer
keeps Log Out, Suspend, Restart, and Power Off; no replacement with Lock.

## v25 validation

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
