# SPDX-License-Identifier: MIT
"""Layout Switcher controls for the bundled Frosted Glass extension."""

from typing import List

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from constants import tr
from extension_manager import ExtMgr
from shell_reloader import ShellReloader
from utils import gnome_shell_version

FROSTED_GLASS_UUID = "frosted-glass@communitybig.org"
FROSTED_GLASS_SCHEMA = "org.communitybig.frosted-glass"
MINIMUM_SHELL_MAJOR = 50
FULL_BACKEND_MINIMUM_SHELL_MAJOR = 51
# WindowActor background blur corrupts repaints on the tested Mutter 51 beta.
# Keep the setting contract visible, but do not expose an unsafe switch yet.
WINDOW_BLUR_AVAILABLE = False


def is_frosted_glass_supported() -> bool:
    """Return true when at least the overview backend is available."""
    shell_version = gnome_shell_version()
    return shell_version[0] >= MINIMUM_SHELL_MAJOR


def _schema_available() -> bool:
    source = Gio.SettingsSchemaSource.get_default()
    return bool(source and source.lookup(FROSTED_GLASS_SCHEMA, True))


def _schema_has_key(key: str) -> bool:
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup(FROSTED_GLASS_SCHEMA, True) if source else None
    return bool(schema and schema.has_key(key))


class FrostedGlassControls(Gtk.Box):
    """Live GSettings editor. The Shell extension owns rendering."""

    def __init__(self, pool, toast_cb) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._pool = pool
        self._toast = toast_cb
        self._settings = None
        self._dependent_rows: List[Gtk.Widget] = []
        self._unavailable_rows: List[Gtk.Widget] = []
        self._build()

    def _build(self) -> None:
        shell_major = gnome_shell_version()[0]
        overview_only = MINIMUM_SHELL_MAJOR <= shell_major < FULL_BACKEND_MINIMUM_SHELL_MAJOR
        title = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name("weather-fog-symbolic")
        icon.set_pixel_size(24)
        title.append(icon)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        heading = Gtk.Label(label=tr("Overview blur") if overview_only else tr("Frosted glass"))
        heading.add_css_class("title-3")
        heading.set_halign(Gtk.Align.START)
        labels.append(heading)
        description = Gtk.Label(
            label=(
                tr("Blur for the workspace and application overview")
                if overview_only
                else tr("Unified blur for windows and GNOME Shell surfaces")
            ),
        )
        description.add_css_class("dim-label")
        description.set_halign(Gtk.Align.START)
        labels.append(description)
        title.append(labels)
        self.append(title)

        if shell_major < MINIMUM_SHELL_MAJOR:
            version = str(shell_major) if shell_major else tr("unknown")
            self.append(
                self._unavailable(
                    tr(
                        "Overview blur requires GNOME 50 or newer. This desktop is GNOME {version}."
                    ).format(version=version)
                )
            )
            return
        if not _schema_available():
            self.append(
                self._unavailable(
                    tr(
                        "Install or update Layout Switcher to make Frosted Glass "
                        "settings available."
                    )
                )
            )
            return

        self._settings = Gio.Settings.new(FROSTED_GLASS_SCHEMA)
        self._normalize_runtime_state()
        if overview_only:
            self._settings.set_boolean("overview-enabled", True)
            self.append(self._build_overview_main_group())
            self.append(self._build_overview_material_group())
            self._sync_sensitivity()
            return
        self.append(self._build_main_group())
        self.append(self._build_targets_group())
        self.append(self._build_material_group())
        self.append(self._build_rules_group())
        self._sync_sensitivity()

    def _build_overview_main_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        master = Adw.SwitchRow(
            title=tr("Enable overview blur"),
            subtitle=tr("Workspace and application overview"),
        )
        self._settings.bind("enabled", master, "active", Gio.SettingsBindFlags.DEFAULT)
        master.connect("notify::active", self._on_master_changed)
        group.add(master)
        self._master = master
        return group

    def _build_overview_material_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title=tr("Material"))
        strength = self._scale_row("blur-strength", tr("Blur strength"), tr("Less"), tr("More"))
        opacity = self._scale_row(
            "glass-opacity", tr("Material opacity"), tr("Transparent"), tr("Opaque")
        )
        group.add(strength)
        rows = [strength]
        if _schema_has_key("use-accent-color"):
            accent = self._switch_row("use-accent-color", tr("Accent color"), "")
            group.add(accent)
            rows.append(accent)
        group.add(opacity)
        rows.append(opacity)
        self._dependent_rows.extend(rows)
        return group

    def _unavailable(self, message: str) -> Gtk.Widget:
        status = Adw.StatusPage(
            icon_name="dialog-information-symbolic",
            title=tr("Not available in this session"),
            description=message,
        )
        status.set_vexpand(False)
        status.set_size_request(-1, 180)
        return status

    def _build_main_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        master = Adw.SwitchRow(
            title=tr("Enable frosted glass"),
            subtitle=tr("Apply the material without changing the active desktop layout"),
        )
        self._settings.bind("enabled", master, "active", Gio.SettingsBindFlags.DEFAULT)
        master.connect("notify::active", self._on_master_changed)
        group.add(master)
        self._master = master
        return group

    def _build_targets_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title=tr("Surfaces"),
            description=tr("Choose independently where the material is applied."),
        )
        rows = [
            ("windows-enabled", tr("Windows"), tr("GTK, Qt and other application windows")),
            ("panel-enabled", tr("Panel"), tr("GNOME panel and Community Panel")),
            ("dock-enabled", tr("Dock"), tr("Community Dock surfaces")),
            (
                "layout-menus-enabled",
                tr("Layout menus"),
                tr("Application menus used by Classic, Hybrid and Desk-UX"),
            ),
            (
                "quick-settings-enabled",
                tr("Quick Settings"),
                tr("System settings menu in the panel"),
            ),
            (
                "calendar-enabled",
                tr("Calendar and notifications"),
                tr("Date, calendar and notification menu in the panel"),
            ),
            (
                "system-dialogs-enabled",
                tr("System dialogs"),
                tr("Power, restart and other GNOME Shell dialogs"),
            ),
            (
                "overview-enabled",
                tr("Overview"),
                tr("Workspace and application overview"),
            ),
        ]
        for key, title, subtitle in rows:
            row = self._switch_row(key, title, subtitle)
            if key == "windows-enabled" and not WINDOW_BLUR_AVAILABLE:
                row.set_subtitle(tr("Not available in this session"))
                warning = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
                warning.set_tooltip_text(tr("Not available in this session"))
                row.add_suffix(warning)
                self._unavailable_rows.append(row)
            group.add(row)
            self._dependent_rows.append(row)
        return group

    def _build_material_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title=tr("Material"))
        mode = self._combo_row(
            "blur-mode",
            tr("Rendering mode"),
            tr("Automatic balances visual quality and power usage"),
            ["automatic", "dynamic", "static"],
            [tr("Automatic"), tr("Dynamic"), tr("Static")],
        )
        group.add(mode)
        strength = self._scale_row("blur-strength", tr("Blur strength"), tr("Less"), tr("More"))
        opacity = self._scale_row(
            "glass-opacity", tr("Material opacity"), tr("Transparent"), tr("Opaque")
        )
        group.add(strength)
        rows = [mode, strength]
        if _schema_has_key("use-accent-color"):
            accent = self._switch_row("use-accent-color", tr("Accent color"), "")
            group.add(accent)
            rows.append(accent)
        group.add(opacity)
        rows.append(opacity)
        self._dependent_rows.extend(rows)
        return group

    def _build_rules_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title=tr("Behavior"),
            description=tr("Application identifiers can be separated by commas."),
        )
        exclusions = Adw.EntryRow(title=tr("Application exceptions"))
        exclusions.set_text(", ".join(self._settings.get_strv("application-exclusions")))
        exclusions.connect("changed", self._on_exclusions_changed)
        group.add(exclusions)

        choices = ["keep", "opaque", "disable"]
        labels = [tr("Keep blur"), tr("Make opaque"), tr("Disable blur")]
        maximized = self._combo_row(
            "maximized-behavior", tr("Maximized windows"), "", choices, labels
        )
        fullscreen = self._combo_row(
            "fullscreen-behavior", tr("Fullscreen windows"), "", choices, labels
        )
        power = self._combo_row(
            "power-save-behavior",
            tr("Power saving"),
            tr("Used on battery and with the power-saver profile"),
            ["keep", "static", "disable"],
            [tr("Keep selected mode"), tr("Use static blur"), tr("Disable blur")],
        )
        for row in [maximized, fullscreen, power]:
            group.add(row)
        self._dependent_rows.extend([exclusions, maximized, fullscreen, power])
        if not WINDOW_BLUR_AVAILABLE:
            self._unavailable_rows.extend([exclusions, maximized, fullscreen])
        return group

    def _normalize_runtime_state(self) -> None:
        """Remove settings that cannot have a safe runtime effect."""
        if not WINDOW_BLUR_AVAILABLE and self._settings.get_boolean("windows-enabled"):
            self._settings.set_boolean("windows-enabled", False)
        if self._settings.get_boolean("enabled") and not ExtMgr.is_enabled(FROSTED_GLASS_UUID):
            self._settings.set_boolean("enabled", False)

    def _switch_row(self, key: str, title: str, subtitle: str) -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title, subtitle=subtitle)
        self._settings.bind(key, row, "active", Gio.SettingsBindFlags.DEFAULT)
        return row

    def _combo_row(
        self,
        key: str,
        title: str,
        subtitle: str,
        values: List[str],
        labels: List[str],
    ) -> Adw.ComboRow:
        row = Adw.ComboRow(title=title, model=Gtk.StringList.new(labels))
        if subtitle:
            row.set_subtitle(subtitle)
        current = self._settings.get_string(key)
        row.set_selected(values.index(current) if current in values else 0)
        row.connect(
            "notify::selected",
            lambda widget, prop, setting=key, options=values: self._settings.set_string(
                setting, options[min(widget.get_selected(), len(options) - 1)]
            ),
        )
        return row

    def _scale_row(self, key: str, title: str, low: str, high: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        low_label = Gtk.Label(label=low)
        low_label.add_css_class("caption")
        box.append(low_label)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_value(self._settings.get_int(key))
        scale.set_draw_value(False)
        scale.set_size_request(220, -1)
        scale.connect(
            "value-changed",
            lambda widget, setting=key: self._settings.set_int(setting, round(widget.get_value())),
        )
        box.append(scale)
        value = Gtk.Label(label=f"{self._settings.get_int(key)}%")
        value.set_width_chars(4)
        scale.connect(
            "value-changed",
            lambda widget, label=value: label.set_label(f"{round(widget.get_value())}%"),
        )
        box.append(value)
        high_label = Gtk.Label(label=high)
        high_label.add_css_class("caption")
        box.append(high_label)
        row.add_suffix(box)
        return row

    def _on_master_changed(self, row: Adw.SwitchRow, prop) -> None:
        enabled = row.get_active()
        self._settings.set_boolean("enabled", enabled)
        self._sync_sensitivity()
        if not enabled or ExtMgr.is_enabled(FROSTED_GLASS_UUID):
            return

        def task() -> None:
            ok, message = ShellReloader.apply_extension_state(FROSTED_GLASS_UUID, True)
            if ok:
                GLib.idle_add(self._toast, tr("Frosted glass enabled"))
                return
            GLib.idle_add(self._disable_setting)
            GLib.idle_add(
                self._toast,
                tr("Could not enable Frosted Glass: {message}").format(message=message),
            )

        self._pool.submit(task)

    def _disable_setting(self) -> bool:
        self._settings.set_boolean("enabled", False)
        return GLib.SOURCE_REMOVE

    def _on_exclusions_changed(self, row: Adw.EntryRow) -> None:
        entries = [part.strip() for part in row.get_text().split(",") if part.strip()]
        self._settings.set_strv("application-exclusions", entries)

    def _sync_sensitivity(self) -> None:
        active = self._master.get_active()
        for row in self._dependent_rows:
            row.set_sensitive(active and row not in self._unavailable_rows)
