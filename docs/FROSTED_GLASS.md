# Frosted Glass development

## Scope

`frosted-glass@communitybig.org` is the Big Gnome Center blur implementation.
GNOME Shell 50 loads only the project-owned Overview background blur. GNOME
Shell 51 loads the complete surface backend. It has no Blur My Shell runtime
or package dependency. One migration entry remains in `layout_applier.py` only
to clear stale dconf left by older Big Gnome Center releases.

Settings contract targets:

- GTK, Qt, Electron, and XWayland application windows
- GNOME panel and Community Panel
- Community Dock
- Community Menu surfaces used by Classic, Hybrid, and Desk-UX
- Quick Settings
- Calendar and notifications
- GNOME Shell system dialogs
- Workspace and application overview

The GTK Big Gnome Center UI is only the GSettings editor. Rendering belongs to
the GNOME Shell extension.

## Version boundary

GNOME 50 supports only `OverviewController`, implemented with
`Shell.BlurEffect` and a project-owned wallpaper actor. `extension.js` does not
load the GNOME 51 surface or window modules in this mode. The GTK UI exposes
only the Overview switch, strength, and opacity.

The original BigGnome, Desk-UX and G-Unity profiles enable overview blur by
default on GNOME 50. Classic, Hybrid and Minimal keep it disabled. Saved user
snapshots preserve the current global preference instead of applying a default.

The complete material backend requires GNOME 51. Its stable release is
scheduled for 2026-09-16. Development packages are available from Arch's
`gnome-unstable` repository.

Mutter 51 implements `ext-background-effect-v1`. A Wayland client must create
an effect object and submit its surface-local blur region. Therefore the native
protocol improves cooperating applications but cannot force arbitrary GTK,
Qt, Electron, or XWayland windows to request blur. Frosted Glass also attaches
Shell blur actors to `Meta.WindowActor`, giving all toolkits the same fallback.

The compositor's `set_background_blur_params()` tunes native client-requested
blur. `Shell.BlurEffect` renders project-owned surfaces. The toolkit-neutral
`Meta.WindowActor` fallback and native window parameters are currently gated
off because the tested Mutter 51 beta corrupts repaints. Do not enable either
path without testing both cooperating and non-cooperating clients.

Primary references:

- <https://release.gnome.org/calendar/>
- <https://archlinux.org/packages/gnome-unstable/x86_64/gnome-shell/>
- <https://wayland.app/protocols/ext-background-effect-v1>
- <https://gnome.pages.gitlab.gnome.org/mutter/meta/>
- <https://gnome.pages.gitlab.gnome.org/gnome-shell/shell/>

## Architecture

| File | Responsibility |
| --- | --- |
| `extension.js` | Lifecycle, version-gated backend loading, power policy, native compositor parameters |
| `blurSurface.js` | Dynamic/static blur actor, tint, opacity, geometry, cleanup |
| `blurPaintSignal.js` | Throttled repaint workaround for background blur |
| `roundedCorners.js` and `.glsl` | Rounded alpha mask applied after blur |
| `windowController.js` | Window discovery, toolkit-neutral fallback, exclusions, maximized/fullscreen policy |
| `shellSurfaces.js` | Panel, dock, menus, popovers, and system-dialog discovery |
| `shellBlurSurface.js` | Non-layout Shell blur actor and repaint workaround |
| `overviewController.js` | Per-monitor wallpaper blur behind Overview |
| `powerMonitor.js` | Battery and power-saver state |
| `connectionManager.js` | Deterministic signal cleanup |
| `stylesheet.css` | Removes opaque Shell backgrounds only on managed actors |
| `schemas/*.xml` | Stable settings contract shared with the GTK UI |
| `ui/frosted_glass.py` | Big Gnome Center GTK4/libadwaita controls |

`BlurSurface` inserts a non-reactive actor behind application windows.
`ShellBlurSurface` creates an allocated overlay directly in `Main.uiGroup`,
positions it from the target's transformed stage geometry, and stacks it below
the target's top-level Shell actor. It never enters the target's layout. Static
mode paints a blurred wallpaper copy; dynamic mode samples the framebuffer
behind the overlay. The original target is made transparent, and no visible
border is added. The allocated Shell overlay uses the rounded mask safely;
window actors keep it disabled until their repaint behavior is stable.

Quick Settings and date-menu controls use translucent solid-color layers over
the one shared blur. Do not add per-control shadows or nested blur effects:
testing shadows on the calendar grid caused severe frame and pointer latency
because dozens of actors required separate offscreen composition.
Checked controls derive their translucent fill from the Shell
`-st-accent-color`; never hard-code GNOME blue because Big Gnome Center changes
the system accent independently of the glass material.
Managed glass surfaces draw a one-pixel translucent highlight inside the
material overlay. Their controls use the same one-pixel treatment. Borders do
not change target allocation or create another offscreen render pass. Keep
the outer highlight near seven-percent opacity and control edges near five
percent so light wallpapers do not turn them into visible frames.

Dynamic Shell blur uses the bundled GNOME 51 `Blur.BlurEffect` helper. It is
derived from `ShellBlurEffect` and applies the rounded mask inside the same
paint-node pipeline after blurring the real framebuffer. Separate stacked
Clutter effects cannot provide the same result: an inner mask is blurred back
into a rectangle, while an outer offscreen mask prevents background sampling.
The Mutter-derived JavaScript corner shader remains the static-mode mask.

Community Dock writes an opaque background color directly on its
`dash-background` actor, which outranks extension CSS. `ShellBlurSurface`
temporarily replaces that inline paint with a transparent style, preserves the
latest Community Dock style, and restores it when dock blur is disabled. Once the
opaque paint is removed, the dock uses the same material, brightness, and
opacity as the panel.

Community Dock auto-hide does not move the background actor directly. Its
`DashSlideContainer` animates `slide-x`, changes allocation, and clips the dock
child. The Frosted Glass overlay observes the full ancestor geometry chain and
intersects its paint clip with the slider's transformed allocation. This keeps
blur, icons, and the reveal animation in the same visible region.

The rounded shader is derived from Blur My Shell's GPL-3.0 CornerEffect and
`yilozt/rounded-window-corners`, which itself follows Mutter. Attribution is in
both source files. Mutter 51 removed `ShaderEffect.set_shader_source()`; the
implementation uses `vfunc_get_static_snippet()` and `Cogl.Snippet` instead.
The bundled extension is GPL-3.0-or-later.

## Settings contract

| Key | Type | Meaning |
| --- | --- | --- |
| `enabled` | bool | Master switch |
| `windows-enabled` | bool | Application windows |
| `panel-enabled` | bool | GNOME panel and Community Panel |
| `dock-enabled` | bool | Community Dock |
| `layout-menus-enabled` | bool | Community Menu layouts |
| `quick-settings-enabled` | bool | Quick Settings popup |
| `calendar-enabled` | bool | Calendar and notifications popup |
| `system-dialogs-enabled` | bool | Power, restart, and other Shell dialogs |
| `overview-enabled` | bool | Workspace and application overview |
| `blur-strength` | int 0–100 | Blur radius input |
| `glass-opacity` | int 10–100 | Material tint and translucent window content |
| `blur-mode` | enum | `automatic`, `dynamic`, or `static` |
| `application-exclusions` | string array | WM class, instance, or GTK app ID fragments |
| `maximized-behavior` | enum | `keep`, `opaque`, or `disable` |
| `fullscreen-behavior` | enum | `keep`, `opaque`, or `disable` |
| `power-save-behavior` | enum | `keep`, `static`, or `disable` |

Automatic selects dynamic blur so panel, dock, and popup materials sample the
live framebuffer behind them. The power policy can switch Automatic to static
on battery or under the power-saver profile. Explicit Static mode renders a
managed wallpaper copy; it is intentionally not a live-content blur.

## Surface discovery rules

- Panel: `Main.panel` plus `global.dashToPanel.panels`.
- Dock: `dashtodockContainer`, then its `dash-background` descendants.
- Layout menus: `community-menu`, preferring `popup-menu-content` descendants.
- Quick Settings: each panel's `statusArea.quickSettings.menu`, preferring the
  `quick-settings` content actor. Its mask reads the computed corner radius
  from the active Shell theme, with the GNOME 51 default of 36 px as fallback.
  Both the content border and the outer `BoxPointer` drawing layer are hidden
  and restored with the surface lifecycle. The glass overlay supplies the
  complete rounded contour without a separate border or shadow. Toggle
  submenus, including the power menu, live in a sibling overlay; discovery
  marks their `quick-toggle-menu` actors so they use translucent paint and a
  one-pixel edge over the same shared blur instead of creating nested blur.
- Calendar and notifications: each panel's `statusArea.dateMenu.menu.box`.
  This is one independent surface and setting; the original `BoxPointer`
  border is restored when the effect is disabled. Notification cards use
  translucent paint over that shared blur. GNOME 51 notification banners live
  separately in `Main.messageTray._banner`; they receive one independent blur
  while visible and are discovered from `_bannerBin` lifecycle signals.
- System dialogs: `.modal-dialog` descendants of
  `Main.layoutManager.modalDialogGroup`. Dialog buttons receive translucent
  paint and a one-pixel edge over the single dialog blur.
- Panel, Community Panel, dock, Quick Settings, and date-menu masks read their computed
  corner radius from the active actor. Hard-coded values are fallback only, so
  layout and theme changes do not alter the existing surface geometry.
- Rounded masks use the Mutter-derived per-pixel coverage calculation from
  Blur My Shell's `CornerEffect`, including its three-pixel paint-buffer
  compensation. This preserves the actor's native side contour instead of
  approximating it with a generic signed-distance shape.
- Blur and tint are composed before one outer rounded mask is applied. The tint
  has no independent radius, avoiding a bright seam between two antialiased
  contours.
- Overview: one `BackgroundManager` actor per monitor, permanently kept at
  index zero of `Main.layoutManager.overviewGroup`.

Discovery intentionally repeats every two seconds because panel, dock, and
menu extensions replace actors during live layout switching.

## Development and validation

Focused static checks:

```sh
for file in usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/*.js; do
  node --check "$file"
done
glib-compile-schemas --strict --dry-run \
  usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/schemas
python3 -m pytest tests/test_frosted_glass.py tests/test_layout_applier.py -q
msgfmt --check usr/share/locale/pt-BR.po
```

GNOME Shell modules cannot be integration-tested with Node. Copy the whole
extension directory into `/usr/share/gnome-shell/extensions/`, copy its schema
to `/usr/share/glib-2.0/schemas/`, and compile **both** schema locations before
restarting the user Shell session:

```sh
glib-compile-schemas \
  /usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/schemas
glib-compile-schemas /usr/share/glib-2.0/schemas
```

The first compiled file is required by `Extension.getSettings()`; the second
exposes the same schema to the GTK application. A development `rsync --delete`
can remove `schemas/gschemas.compiled`, so always recompile afterwards. A
Wayland Shell extension module reload requires logout/login or a display-manager
restart. GNOME Shell 51 beta advertises `ReloadExtension` over D-Bus but the
tested build does not implement the method.

Useful runtime checks:

```sh
gnome-shell --version
gnome-extensions info frosted-glass@communitybig.org
gsettings list-recursively org.communitybig.frosted-glass
journalctl --user -b -o cat | grep -i 'Frosted Glass'
```

Manual matrix:

1. Toggle every target independently.
2. Move a GTK and a Qt window; resize and maximize both.
3. Test a fullscreen window and an excluded application.
4. Open Quick Settings, Calendar and notifications, the power/restart dialog,
   and Community Menu in each applicable layout.
5. Switch between Community Dock and Community Panel layouts while enabled.
6. Open Overview and the application grid on every monitor.
7. Change dynamic/static/automatic mode live.
8. Change strength and opacity at their minimum and maximum.
9. Enter power-saver mode and disconnect AC power when available.
10. Disable the extension and confirm every style, effect, opacity, and actor is restored.

## GNOME 51 test VM notes

Validated initially against GNOME Shell 51 beta, Mutter 51 beta, and Wayland in
a QEMU/KVM VM. The VM advertises `ext_background_effect_manager_v1`.

Panel, Community Dock, and Quick Settings corner geometry was visually validated
against the same surfaces with blur disabled. The final mask reads the active
theme radius and uses Mutter-compatible pixel coverage; it does not resize or
reposition the target actor.

### Deferred application-grid icons

On the tested GNOME Shell 51.beta VM, opening the application grid for the
first time after login can show empty folder cards for about eight seconds.
Waiting elsewhere in the session does not preload those icons; opening the
grid starts the work. A controlled logout/login test reproduced the delay with
all Frosted Glass targets disabled, so it is not caused by this extension's
blur, tint, or overview controller.

The same delayed icon population was observed in the bundled application-menu
layouts after a fresh login with Frosted Glass globally disabled. Treat this
as a separate Shell/menu loading investigation; do not couple a workaround to
the blur lifecycle.

GNOME Shell intentionally defers invisible app-grid work. Do not call private
`AppDisplay._redisplay()` methods or add arbitrary startup timers here: an
extension-side warmup was tested and did not solve the delay. Retest on the
latest GNOME 51 RC or stable package before investigating further. Keep the
Overview implementation unchanged unless the issue can also be reproduced
with current upstream GNOME 51 and a stock icon theme outside the VM.

The beta GDM switchable-authentication path produced empty PAM conversations
and could crash the greeter. This was isolated from Frosted Glass. The VM-only
workaround is a dconf profile under `/etc/dconf/db/gdm.d/` that disables
switchable, fingerprint, and smart-card authentication while leaving password
authentication enabled. Do not ship that workaround in Big Gnome Center.

Before system package experiments, the VM had a Timeshift snapshot and a
separate system-file backup. Keep equivalent rollback coverage for later beta
or RC upgrades.

## Current status and handoff

Implemented locally:

- GNOME 51-only extension and GTK controls
- Gated native parameters plus toolkit-neutral actor fallback prototype
- Window, panel, Community Panel, dock, menu, Quick Settings, date-menu, system
  dialog, and Overview targets
- Rounded blur mask
- Live strength, material opacity, and rendering mode
- Application, maximized, fullscreen, and power rules
- Multi-monitor Overview backgrounds
- Package and layout migration away from Blur My Shell
- Static tests and pt-BR localization

Window fallback is experimental, defaults off, and is hard-gated in the Shell
extension and GTK controls while Mutter 51 repaint behavior is validated. It
must not be exposed until GTK, Qt, and XWayland hover/resize testing completes
without framebuffer artifacts.

Before release, repeat the manual matrix on the current GNOME 51 RC or stable
build and inspect Shell logs after each actor replacement. Pay special attention
to extension API changes between beta and stable, popup geometry under scaled
displays, multi-monitor Overview ordering, and GPU cost at high blur radii.

For another coding agent, provide this file, repository `AGENTS.md`, the current
`git diff`, and VM access details separately. No credentials belong in the
repository.
