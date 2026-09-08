# Frosted Glass development

## Scope

`frosted-glass@communitybig.org` is the Big Gnome Center blur implementation.
GNOME Shell 50 loads only the project-owned Overview background blur. GNOME
Shell 51 loads the complete surface backend. It has no Blur My Shell runtime
or package dependency. One migration entry remains in `layout_applier.py` only
to clear stale dconf left by older Big Gnome Center releases.

Settings contract targets:

- Wayland application windows requesting native background blur
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
Qt, Electron, or XWayland windows to request blur. GTK4 alone is insufficient:
the application must request a blurred background through its rendering tree.
For validated native GTK applications, Big Gnome Center supplies that request
through GTK's user stylesheet: `backdrop-filter` plus translucent background
colors. This requires GTK 4.23.3 or newer and successful CSS capability parsing.
Profiles cover Nautilus, Big Gnome Center, GNOME Text Editor and cooperating
BigLinux/Community applications with explicit window CSS classes.
Calculator has no exclusive window selector in the tested version and remains
unchanged. GTK3, Qt, Electron, and Flatpak runtimes are not supported profiles.

### Validated application profiles

- Files (Nautilus): `window.nautilus-window`.
- Big Gnome Center: `window.big-gnome-center`.
- GNOME Text Editor: `window.org-gnome-TextEditor`; background-only text-view rule.
- Ashyterm: `window.ashyterm-window`; blur only, preserving its palette and alpha.
- Audio/Video Converter: `window.big-audio-converter`, `window.big-video-converter`.
- Hardware/Network Info: `window.big-hardware-info`, `window.big-network-info`.
- BigOCR: `window.bigocrpdf`, `window.bigocrimage`, `window.bigocrpdf-editor`.
- WebApps Manager: `window.biglinux-webapps`; not browser/web content.
- General Adjustments: `window.biglinux-settings`.
- Big Recorder: `window.bigrecorder`.
- System / Distribution Info: `window.community-release`; live client.
- Big Microphone (Python): `window.biglinux-microphone`; live client.
- BigCam: `window.bgc-bigcam`; live blur only, preserving camera opacity.
- Big Driver Manager: `window.big-driver-manager`; live client.

These profiles were tested on the GNOME 51.beta / GTK 4.23.3 VM. This list is
not a claim that every GTK4 application supports the managed style.
Camera/audio discovery and driver detection were disabled in the new UI tests;
recording and package operations were not exercised. The current Rust Microphone
clone shares its profile but has startup-only integration; VM validation pending.

Embedded dialogs restore opaque palette variables at their boundary. Recorder
chrome follows the inherited palette; text, icons and document canvases are
not faded. App integration adds a class without replacing toolkit classes.

Cooperating app packages must include their window class; updating Big Gnome
Center alone does not retrofit older app binaries. The class itself has no
effect without the managed style. GNOME 50 remains unchanged. No app bundles a
global GTK override. Media, PDF pages and drawing widgets receive no overrides.
Reopen running applications after installing either side of the integration.

Big Gnome Center monitors the managed sheet and reloads its GTK provider while
open. Disabling removes its material class, including matches from GTK's cached
startup stylesheet. System / Distribution Info, Python Microphone, BigCam and
Driver Manager use the same client. Other profiles still require reopening after
material changes; a static CSS class is not live integration.

The package exposes optional Python integration:

```python
try:
    from big_gnome_center_material import attach_window_material
except ImportError:
    attach_window_material = None

# After initializing the GTK window; requires a registered app profile.
self.add_css_class("community-release")
if attach_window_material is not None:
    self._window_material = attach_window_material(self, "community-release")
```

The client monitors atomic stylesheet updates, gates unsupported GTK versions,
and releases providers on window destruction. It never changes window opacity.

Native panel material preserves transparency after runtime opacity updates
during overview transitions, then restores the latest underlying style on stop.

### Calculator: deferred

GNOME Calculator 51beta-1 has no exclusive window CSS class or explicit widget
name in its `MathWindow` template. Its GType name is not a CSS ID. Do not use a
generic window selector, inject code, or patch the executable to force support.

User decision (2026-09-07): defer Calculator support; do not create or maintain
a separate fork/package. Revisit when upstream provides a suitable selector or
native application integration. Calculator remains visually unchanged.

The compositor's `set_background_blur_params()` tunes native client-requested
blur. Window tuning is opt-in and restricted to GNOME 51. No fallback modifies
window actors, client opacity, geometry, or input. Opaque clients stay opaque;
text and icons retain their original contrast.
Native parameters are changed only for enabled dynamic window blur and restored
when that path stops. Shell-only blur never overrides native client parameters.
Disabling tuning restores native defaults; it does not suppress independent
client blur requests. Static mode and power-saving fallback restore parameters,
not a static window image. Per-window rules are unavailable through this global
API and are hidden; legacy schema keys remain for settings compatibility.

### Managed GTK styles

`window_material.py` maintains `gtk-4.0/big-gnome-center-windows.css` under the
user's XDG config directory. One marked import is prepended to `gtk.css`.
Existing user bytes, BOM, permissions, and later edits are preserved. Symlinks,
non-regular files, and unowned material files are refused. Disabling empties the
owned stylesheet and removes only the exact managed import. No app is restarted
automatically; existing GTK processes may need reopening after either change.

`windowStyles.js` serializes helper requests across rapid toggles and extension
re-enables. The Shell drives synchronization without an open GTK control app.
GNOME 50, disabled targets, static mode, and zero blur remove the managed styles.
Native parameter tuning still affects independently cooperating applications.

Background tint follows the application's named Adwaita color, including the
Text Editor's recolored schemes. Opacity maps to 60–100% to retain contrast.
Text, icons, selections, and button colors are not overridden. High contrast
skips all managed rules. CSS requests a 30 px blur to reach GTK's native-region
threshold; the compositor's radius can be tuned when its API is available.
The GNOME 51.beta VM exposes the protocol but not the optional compositor
tuning methods. Native styles still work there, using Mutter's blur parameters;
the strength setting tunes native windows only when that API is available.

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
| `windowStyles.js` | Serialized GTK style synchronization and teardown |
| `window_material.py` | Capability check, scoped CSS, reversible user import |
| `blurPaintSignal.js` | Throttled repaint workaround for background blur |
| `roundedCorners.js` and `.glsl` | Rounded alpha mask applied after blur |
| `shellSurfaces.js` | Panel, dock, menus, popovers, and system-dialog discovery |
| `shellBlurSurface.js` | Non-layout Shell blur actor and repaint workaround |
| `overviewController.js` | Per-monitor wallpaper blur behind Overview |
| `powerMonitor.js` | Battery and power-saver state |
| `connectionManager.js` | Deterministic signal cleanup |
| `stylesheet.css` | Removes opaque Shell backgrounds only on managed actors |
| `schemas/*.xml` | Stable settings contract shared with the GTK UI |
| `ui/frosted_glass.py` | Big Gnome Center GTK4/libadwaita controls |

`ShellBlurSurface` creates an allocated overlay directly in `Main.uiGroup`,
positions it from the target's transformed stage geometry, and stacks it below
the target's top-level Shell actor. It never enters the target's layout. Static
mode paints a blurred wallpaper copy; dynamic mode samples the framebuffer
behind the overlay. The original target is made transparent, and no visible
border is added. Application windows have no extension-owned actor or effect;
Mutter handles their native blur regions.

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

Dynamic Shell blur defaults to native `Shell.BlurEffect`. Rounded dynamic
corners require the optional `gnome-rounded-blur` library; it is not bundled
or built by this package. Earlier documentation incorrectly called it bundled.
Its `Blur.BlurEffect` applies the rounded mask in the native paint-node pipeline.
Separate stacked Clutter effects cannot provide the same result: an inner mask
is blurred back into a rectangle, while an outer offscreen mask prevents
background sampling. The JavaScript corner shader remains the static-mode mask.

Before importing the optional library, `roundedBackend.js` resolves its symbols
in an isolated GJS process with `LD_BIND_NOW=1`, matching the Shell GI/library
paths. Failed imports and a three-second timeout fall back to native Shell blur.
This avoids terminating the desktop when a Mutter upgrade invalidates the
library. The fallback has rectangular dynamic blur bounds; it does not promise
rounded clipping. Native GTK window blur is independent of this library.

GNOME 51 RC removed `clutter_get_default_backend()`. The optional library must
obtain the backend from its actor's Clutter context and defer pipeline creation
until that actor is attached. A tested source patch for upstream revision
`f3bfcc796e1214c1e1d4287ee35cb132ad8133f0` is in
`docs/patches/rounded-blur-gnome51.patch`. Build it against Mutter 51, including
Clutter-51 introspection. Do not copy a GNOME 50 binary into a GNOME 51 package.
The patch is a packaging aid, not an automatic system-library installer.

GNOME 51 porting reference:
<https://gjs.guide/extensions/upgrading/gnome-shell-51.html>.

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
| `windows-enabled` | bool | Tune native client-requested blur on GNOME 51 |
| `panel-enabled` | bool | GNOME panel and Community Panel |
| `dock-enabled` | bool | Community Dock |
| `layout-menus-enabled` | bool | Community Menu layouts |
| `quick-settings-enabled` | bool | Quick Settings popup |
| `calendar-enabled` | bool | Calendar and notifications popup |
| `system-dialogs-enabled` | bool | Power, restart, and other Shell dialogs |
| `overview-enabled` | bool | Workspace and application overview |
| `blur-strength` | int 0–100 | Blur radius input |
| `glass-opacity` | int 0–100 | Shell material tint; never client opacity |
| `blur-mode` | enum | `automatic`, `dynamic`, or `static` |
| `application-exclusions` | string array | Legacy; unused by native window tuning |
| `maximized-behavior` | enum | Legacy; unused by native window tuning |
| `fullscreen-behavior` | enum | Legacy; unused by native window tuning |
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
2. Compare a native blur client with opaque GTK/Qt clients; resize and maximize.
3. Confirm ordinary clients retain opacity in fullscreen and Overview.
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

### Mutter 51 RC software-rendering regression

Mutter 51.rc introduced a primary-GPU FBO path that breaks rendering on some
software-rendered systems. On the QEMU/llvmpipe VM, native window and dynamic
Shell blur became transparent without blur; ordinary headless output still
worked. The visible-session A/B test restored blur with
`MUTTER_DEBUG_USE_FBOS=0`, without changing application or extension code.

Upstream fix:
[290f201b2da7](https://gitlab.gnome.org/GNOME/mutter/-/commit/290f201b2da76155e9f20605e6ef670fd4a26042),
“onscreen/native: Disable FBO path by default with software rendering”
([MR !5286](https://gitlab.gnome.org/GNOME/mutter/-/merge_requests/5286)).
It selects the supported path automatically for software rendering, preserving
the accelerated-GPU policy. Use a Mutter package containing that commit or an
explicit downstream backport. Do not ship the diagnostic environment variable,
renderer overrides, or compositor-library replacements in Big Gnome Center.

Internal Shell screenshots are insufficient for native-window blur validation:
their repaint can lack the stage view required by Mutter's native blur path.
Use direct VM display captures or actual stage-view framebuffer captures.

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
- Opt-in GNOME 51 native window tuning and restorable compositor parameters
- Window, panel, Community Panel, dock, menu, Quick Settings, date-menu, system
  dialog, and Overview targets
- Rounded blur mask
- Live strength, material opacity, and rendering mode
- Power rules; legacy per-window settings retained without UI controls
- Multi-monitor Overview backgrounds
- Package and layout migration away from Blur My Shell
- Static tests and pt-BR localization

The forced-opacity window fallback was removed after visual testing showed
washed-out text and icons. Its former VM matrix does not validate native client
support. Native parameter ownership, version gating, restoration, and absence of
window-actor mutation have focused regression coverage. Hardware GPU and
mixed-scale multi-monitor coverage remain release checks.

A temporary GTK 4.23.3 client on the GNOME 51.beta VM used a translucent
background with `backdrop-filter: blur(30px)`. Wayland tracing confirmed a
nonempty `ext_background_effect_surface_v1.set_blur_region` request. Text and
button content stayed opaque. This native-client check ran with Frosted Glass
disabled; loading the updated extension still requires a new Shell session.

Isolated native Nautilus and Text Editor profiles were also tested in the VM.
Both submitted native blur regions. Text Editor retained syntax highlighting.
The full helper/extension path requires post-login validation after deployment.
The GJS helper passed real subprocess tests for enable, disable, rapid re-enable,
and exact restoration of a copy of the VM user's existing stylesheet. A native
request must not be gated on `set_background_blur_params()`: it is absent from
the tested Meta-51 typelib despite working protocol support.

Mutter 51 also removed `Meta.is_wayland_compositor()`. Detect the native context
with `global.context.get_wayland_compositor()` instead. An unguarded call to the
removed function prevented the full Shell backend from starting. GTK setup and
refresh now contain their errors so panel, dock, and Overview remain independent.
The Context method was exercised with the real Meta-51 typelib. Lifecycle tests
cover absent legacy APIs and GTK initialization failure; post-login rendering
must still be verified in the Shell process.

Before release, repeat the manual matrix on the current GNOME 51 RC or stable
build and inspect Shell logs after each actor replacement. Pay special attention
to extension API changes between beta and stable, popup geometry under scaled
displays, multi-monitor Overview ordering, and GPU cost at high blur radii.

For another coding agent, provide this file, repository `AGENTS.md`, the current
`git diff`, and VM access details separately. No credentials belong in the
repository.
