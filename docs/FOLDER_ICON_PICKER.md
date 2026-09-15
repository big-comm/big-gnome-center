# Folder icon picker

Nautilus exposes **Customize Folder Icon…** for a single local directory and for
the current directory's background. BGC opens a separate GTK4/Adwaita window with
search, theme previews, Apply, Cancel, and Restore Default.

## Storage

- Save the theme name in `metadata::custom-icon-name`; remove the higher-priority
  `metadata::custom-icon` file URI only after saving the name.
- Restore Default removes both attributes. Native special-folder icons return.
- No folder content, permissions, emblems, GNOME app folders, or global settings
  are modified. No separate database or privileged helper.
- Opening/canceling never writes. Legacy SVGs within installed Papient themes
  preselect their corresponding design; Apply converts the association.
- Personal image paths are not matched by basename. They remain until an
  explicit Apply or Restore Default action.
- Metadata writes run off the GTK thread. Reject stale dialogs; attempt rollback
  if a later write fails. Report write/rollback failures without closing the UI.
  GVfs has no transaction across attributes; concurrent writers remain possible.

## Theme integration

Reuse the three supported bases and generated overlay names from `folder_accent`.
List scalable `folder*` SVGs with a declared highlight; collapse symlink aliases
and omit open/drag/symbolic variants and fixed-color artwork. Read-only discovery
honors user theme roots before system roots. Installed Papient currently yields
77 designs. Other themes can restore the default but cannot apply these designs.

GTK resolves previews through the current icon theme and updates on theme
changes. The existing BGC accent follower recolors the same names used by Nautilus.
System theme files remain unchanged.

## Packaging

- Dependency: `nautilus-python` (Nautilus 4.1 API).
- Provider: `usr/share/nautilus-python/extensions/big_gnome_center_folder_icons.py`.
- Launcher: `usr/bin/big-gnome-center-folder-icon FOLDER`.
- Separate application ID: `br.com.biglinux.BigGnomeCenter.FolderIcon`.
- Selection/background actions have distinct IDs; Nautilus shares its action
  namespace across both menus. Reusing one ID can target the parent directory.
- Compare icon metadata before/after the picker exits. If it changed, invoke
  `slot.reload` only on tabs showing the folder's parent. Extension-info
  invalidation alone does not reload Nautilus's cached icon metadata. Cancel and
  unchanged choices do not reload views. Unrelated tabs keep their location.
- Launch with an argument vector, never a shell. Application modules and GTK
  application setup stay outside Nautilus's embedded Python interpreter.
- Observe direct context popovers of native file views, including subclasses.
  Use side anchoring and start alignment so GTK can slide menus vertically before
  resizing them. Top/bottom anchoring only allows horizontal sliding and can
  cause needless overflow. Keep native fonts, row sizes, and spacing; no CSS.
  Menus taller than the entire usable display still need GTK's overflow handling.
- Nautilus loads providers on startup. Existing processes need reopening after
  installation; do not restart the user's file manager automatically.
- Strings use the BGC gettext domain. All 62 feature messages are translated and
  compiled in all 29 project catalogs. Existing translations are preserved.

## Validation

Run `pytest -q tests/test_folder_icons.py tests/test_folder_accent.py` first.
Unit coverage includes discovery, aliases, accent overlays, personal images,
metadata conversion/reset/rollback, concurrent changes, and context action targets.

Run `LC_ALL=pt_BR.UTF-8 python tests/folder_icon_picker_vm.py` inside the test
user's graphical session after installing the files. It creates a disposable
directory under the user's home and changes only process-local GTK settings.

Guest GTK/GVfs checks use disposable home directories. Verify conversion through
Apply, orange/green/blue preview lookup, persistent design names, Cancel, personal
SVG preservation, Restore Default, localized search, unsupported themes, and the
Nautilus provider. Test the actual context menu separately in GNOME 50 and 51;
constructing Nautilus FileInfo objects outside Nautilus is not a valid host test.

Both guests passed GTK/GVfs conversion, lookup, cancel, restore, search, and
provider checks. Actual menu activation exposed the shared action-ID bug;
distinct IDs fix selection/background targets.

Guest installation backups:
- GNOME 50.4: `/var/tmp/bgc-folder-picker.f94j71h2`.
- GNOME 51.rc: `/var/tmp/bgc-folder-picker.59hpz332`.

2026-09-15: all 29 catalogs pass `msgfmt --check`; all 62 feature strings exist
in compiled catalogs. Compact-menu styling was rejected and removed.
Final checks: 67 focused tests, 1002 full-suite tests, focused Ruff, and
`git diff --check` passed. One existing GLib deprecation warning.

Run `python tests/context_menu_position_vm.py` in a native Wayland guest session
with at least 524px usable height. In GNOME 50.4 and 51.rc, baseline menus showed
375/377px of 524px. Side anchoring displayed all 16 normal-size rows at the center
and four corners. Real Nautilus menus were also verified in separate D-Bus
instances with disposable config/data/cache: all 442px of content visible,
including Properties, without a scrollbar. Both selection actions opened the
picker for Projetos, the selected directory. Existing Nautilus instances were
not closed or reloaded.

Updated provider and all 29 catalogs installed; backups:
- GNOME 50.4: `/var/tmp/bgc-folder-picker-i18n.4s2wn72e`.
- GNOME 51.rc: `/var/tmp/bgc-folder-picker-i18n.1f6rnluq`.

2026-09-15 refresh follow-up: reproduced persisted `folder-tar` metadata with a
stale plain folder in GNOME 50; F5 revealed the saved design. Fixed provider
refresh and checked Apply/Restore Default in actual Nautilus on both guests,
using disposable folders and separate D-Bus instances. Icons changed immediately
without F5; selection remained. Earlier metadata/lookup tests did not cover this
live-view cache. Provider backup on each guest:
`/var/tmp/bgc-provider-before-refresh.py`.
Validation: 28 focused tests, 1006 full-suite tests, focused Ruff, and
`git diff --check` passed; one existing GLib deprecation warning.
