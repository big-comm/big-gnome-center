# SPDX-License-Identifier: MIT
"""Desktop controls and layout-aware application menu options."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from constants import tr
from extension_manager import ExtMgr
from helper_client import HelperClient
from settings_store import Settings
from ui.desktop_icons import DesktopIconsControls
from utils import dconf_read, dconf_write

COMMUNITY_MENU_UUID = "community-menu@communitybig.org"
SUPER_KEY_PATH = "/org/gnome/shell/extensions/community-menu/super-key-opens-menu"
MENU_LAYOUT_PATH = "/org/gnome/shell/extensions/community-menu/layout"
MENU_LAYOUT_DEFAULTS = {
    "Classic": "APPS_ONLY",
    "Desk UX": "APP_GRID",
    "Hybrid": "MINT",
}
MENU_STYLES = (
    ("Classic", "APPS_ONLY"),
    ("Desk-UX", "APP_GRID"),
    ("Hybrid", "MINT"),
)
NOTIFICATION_POSITION_DEFAULTS = {
    "Classic": "bottom-right",
    "Hybrid": "bottom-right",
    "Desk UX": "bottom-right",
    "Minimal": "top-center",
    "BigGnome": "top-center",
    "G-Unity": "top-right",
}
NOTIFICATION_POSITIONS = (
    ("top-center", tr("Top center")),
    ("bottom-center", tr("Bottom center")),
    ("top-right", tr("Top right")),
    ("top-left", tr("Top left")),
    ("bottom-left", tr("Bottom left")),
    ("bottom-right", tr("Bottom right")),
)
NOTIFICATION_POSITION_VALUES = {value for value, _label in NOTIFICATION_POSITIONS}


class DesktopPage(Gtk.Box):
    """Configure desktop components and layout-aware defaults."""

    def __init__(self, pool, toast_cb) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._pool = pool
        self._toast = toast_cb
        self._prefs = Settings()
        self._syncing = False
        self._active_layout = ""
        self._menu_style_buttons = {}
        self._menu_style_badges = {}
        self._notification_position_buttons = {}
        self._notification_position_badges = {}
        self._build()

    def _build(self) -> None:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        content.set_margin_start(22)
        content.set_margin_end(22)
        content.set_margin_top(8)
        content.set_margin_bottom(22)

        self._desktop_icons = DesktopIconsControls(self._pool, self._toast)
        content.append(self._desktop_icons)
        self._notification_group = self._build_notification_group()
        content.append(self._notification_group)
        self._shell_group = self._build_shell_group()
        content.append(self._shell_group)

        scroll.set_child(content)
        self.append(scroll)

    def _build_notification_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title=tr("Notification position"),
            description=tr("Choose where notification banners appear."),
        )
        row = Adw.PreferencesRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self._notification_flow = Gtk.FlowBox()
        self._notification_flow.add_css_class("notification-position-grid")
        self._notification_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._notification_flow.set_min_children_per_line(3)
        self._notification_flow.set_max_children_per_line(3)
        self._notification_flow.set_column_spacing(10)
        self._notification_flow.set_row_spacing(10)
        self._notification_flow.set_homogeneous(True)

        first_button = None
        for value, label in NOTIFICATION_POSITIONS:
            button = self._build_notification_position_button(value, label)
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)
            self._notification_flow.append(button)
            self._notification_position_buttons[value] = button

        box.append(self._notification_flow)
        row.set_child(box)
        group.add(row)
        return group

    def _build_notification_position_button(
        self,
        value: str,
        label: str,
    ) -> Gtk.ToggleButton:
        button = Gtk.ToggleButton()
        button.add_css_class("notification-position-card")
        button.set_tooltip_text(tr("Show notifications at {position}").format(position=label))
        button.update_property([Gtk.AccessibleProperty.LABEL], [label])

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_margin_top(10)
        box.set_margin_bottom(9)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.append(self._build_notification_position_preview(value))

        position_label = Gtk.Label(label=label)
        position_label.add_css_class("heading")
        box.append(position_label)

        badge = Gtk.Label(label=tr("Default"))
        badge.add_css_class("menu-style-default")
        badge.set_halign(Gtk.Align.CENTER)
        badge.set_valign(Gtk.Align.START)
        badge.set_margin_top(16)
        badge.set_visible(False)
        self._notification_position_badges[value] = badge

        overlay = Gtk.Overlay()
        overlay.set_child(box)
        overlay.add_overlay(badge)
        button.set_child(overlay)
        button.connect("toggled", self._on_notification_position_toggled, value, label)
        return button

    @staticmethod
    def _build_notification_position_preview(value: str) -> Gtk.Widget:
        preview = Gtk.Overlay()
        preview.add_css_class("notification-position-preview")
        preview.set_size_request(-1, 76)

        desktop = Gtk.Box()
        desktop.add_css_class("notification-position-desktop")
        preview.set_child(desktop)

        panel = Gtk.Box()
        panel.add_css_class("notification-position-panel")
        panel.set_halign(Gtk.Align.FILL)
        panel.set_valign(Gtk.Align.START)
        preview.add_overlay(panel)

        banner = Gtk.Box()
        banner.add_css_class("notification-position-banner")
        banner.set_size_request(48, 12)
        banner.set_halign(
            Gtk.Align.START
            if value.endswith("left")
            else Gtk.Align.END
            if value.endswith("right")
            else Gtk.Align.CENTER
        )
        banner.set_valign(Gtk.Align.START if value.startswith("top") else Gtk.Align.END)
        banner.set_margin_top(10)
        banner.set_margin_bottom(7)
        banner.set_margin_start(7)
        banner.set_margin_end(7)
        preview.add_overlay(banner)
        return preview

    def _build_shell_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title=tr("Application menu"),
            description=tr("Available for Classic, Desk-UX and Hybrid layouts."),
        )

        self._menu_row = Adw.ActionRow(
            title=tr("Application menu"),
            subtitle=tr("Use Community Menu as the application menu"),
        )
        self._menu_switch = Gtk.Switch()
        self._menu_switch.set_valign(Gtk.Align.CENTER)
        self._menu_switch.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [tr("Application menu")],
        )
        self._menu_switch.connect("notify::active", self._on_menu_toggled)
        self._menu_row.add_suffix(self._menu_switch)
        self._menu_row.set_activatable_widget(self._menu_switch)
        group.add(self._menu_row)

        style_row = Adw.PreferencesRow()
        style_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        style_box.set_margin_top(12)
        style_box.set_margin_bottom(12)
        style_box.set_margin_start(12)
        style_box.set_margin_end(12)

        style_title = Gtk.Label(label=tr("Menu style"))
        style_title.add_css_class("heading")
        style_title.set_halign(Gtk.Align.START)
        style_box.append(style_title)

        style_hint = Gtk.Label(
            label=tr("Choose the appearance of Community Menu."),
            wrap=True,
            xalign=0,
        )
        style_hint.add_css_class("dim-label")
        style_hint.add_css_class("caption")
        style_box.append(style_hint)

        self._style_flow = Gtk.FlowBox()
        self._style_flow.add_css_class("menu-style-grid")
        self._style_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._style_flow.set_min_children_per_line(3)
        self._style_flow.set_max_children_per_line(3)
        self._style_flow.set_column_spacing(10)
        self._style_flow.set_row_spacing(10)
        self._style_flow.set_homogeneous(True)

        first_button = None
        for name, value in MENU_STYLES:
            button = self._build_menu_style_button(name, value)
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)
            self._style_flow.append(button)
            self._menu_style_buttons[value] = button

        style_box.append(self._style_flow)
        style_row.set_child(style_box)
        group.add(style_row)

        self._super_row = Adw.ComboRow(
            title=tr("Super key"),
            subtitle=tr("Choose what happens when pressing Super"),
            model=Gtk.StringList.new([tr("Open menu"), tr("Open overview")]),
        )
        self._super_row.connect("notify::selected", self._on_super_changed)
        group.add(self._super_row)
        return group

    def _build_menu_style_button(
        self,
        name: str,
        value: str,
    ) -> Gtk.ToggleButton:
        button = Gtk.ToggleButton()
        button.add_css_class("menu-style-card")
        button.set_tooltip_text(tr("Use the {name} menu style").format(name=name))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_margin_top(12)
        box.set_margin_bottom(10)
        box.set_margin_start(8)
        box.set_margin_end(8)

        box.append(self._build_menu_preview(value))

        label = Gtk.Label(label=name)
        label.add_css_class("heading")
        box.append(label)

        badge = Gtk.Label(label=tr("Default"))
        badge.add_css_class("menu-style-default")
        badge.set_halign(Gtk.Align.CENTER)
        badge.set_valign(Gtk.Align.START)
        badge.set_margin_top(20)
        badge.set_visible(False)
        self._menu_style_badges[value] = badge

        overlay = Gtk.Overlay()
        overlay.set_child(box)
        overlay.add_overlay(badge)
        button.set_child(overlay)

        button.connect("toggled", self._on_menu_style_toggled, value, name)
        return button

    def _build_menu_preview(self, value: str) -> Gtk.Widget:
        stage = Gtk.Box()
        stage.add_css_class("menu-style-preview-stage")
        stage.set_size_request(-1, 120)

        preview = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        preview.add_css_class("menu-style-preview")
        preview.set_halign(Gtk.Align.CENTER)
        preview.set_valign(Gtk.Align.CENTER)
        stage.append(preview)

        if value == "APPS_ONLY":
            preview.add_css_class("menu-style-preview-classic")
            preview.set_size_request(78, 108)
            self._append_classic_preview(preview)
        elif value == "APP_GRID":
            preview.add_css_class("menu-style-preview-desk-ux")
            preview.set_size_request(132, 108)
            self._append_desk_ux_preview(preview)
        else:
            preview.add_css_class("menu-style-preview-hybrid")
            preview.set_size_request(146, 108)
            self._append_hybrid_preview(preview)
        return stage

    def _append_classic_preview(self, preview: Gtk.Box) -> None:
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        body.set_vexpand(True)
        body.append(self._build_preview_rail(5))
        body.append(self._build_preview_categories(7))
        preview.append(body)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        footer.append(self._build_preview_actions(3))
        search = self._preview_block("menu-style-search", -1, 7)
        search.set_hexpand(True)
        footer.append(search)
        preview.append(footer)

    def _append_desk_ux_preview(self, preview: Gtk.Box) -> None:
        search = self._preview_block("menu-style-search", -1, 8)
        preview.append(search)
        apps = self._build_preview_apps(6, 3)
        apps.set_vexpand(True)
        preview.append(apps)
        preview.append(self._build_preview_footer(user=True))

    def _append_hybrid_preview(self, preview: Gtk.Box) -> None:
        rail_width = 27
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header.append(self._preview_block("menu-style-user", rail_width, 7))
        search = self._preview_block("menu-style-search", -1, 7)
        search.set_hexpand(True)
        header.append(search)
        preview.append(header)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        body.set_vexpand(True)
        body.append(self._build_preview_categories(6, width=rail_width))
        apps = self._build_preview_apps(4, 2)
        apps.set_hexpand(True)
        body.append(apps)
        preview.append(body)
        preview.append(self._build_preview_footer(user=False))

    def _build_preview_rail(self, items: int) -> Gtk.Box:
        rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        rail.add_css_class("menu-style-rail")
        rail.set_size_request(13, -1)
        for _index in range(items):
            rail.append(self._preview_block("menu-style-rail-item", 6, 6))
        return rail

    def _build_preview_categories(
        self,
        items: int,
        *,
        width: int = 31,
    ) -> Gtk.Box:
        categories = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        categories.add_css_class("menu-style-categories")
        categories.set_size_request(width, -1)
        for _index in range(items):
            categories.append(self._preview_block("menu-style-category-line", -1, 3))
        return categories

    def _build_preview_apps(self, columns: int, rows: int) -> Gtk.Grid:
        apps = Gtk.Grid(column_spacing=4, row_spacing=4)
        apps.add_css_class("menu-style-app-grid")
        apps.set_halign(Gtk.Align.CENTER)
        apps.set_valign(Gtk.Align.CENTER)
        for app_index in range(columns * rows):
            app = self._preview_block("menu-style-app", 8, 8)
            apps.attach(app, app_index % columns, app_index // columns, 1, 1)
        return apps

    def _build_preview_actions(self, items: int) -> Gtk.Box:
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        actions.add_css_class("menu-style-actions")
        for _index in range(items):
            actions.append(self._preview_block("menu-style-action", 4, 4))
        return actions

    def _build_preview_footer(self, *, user: bool) -> Gtk.Box:
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        footer.add_css_class("menu-style-footer")
        if user:
            footer.append(self._preview_block("menu-style-user", 26, 5))
        actions = self._build_preview_actions(4)
        actions.set_halign(Gtk.Align.END if user else Gtk.Align.START)
        actions.set_hexpand(user)
        footer.append(actions)
        return footer

    @staticmethod
    def _preview_block(css_class: str, width: int, height: int) -> Gtk.Box:
        block = Gtk.Box()
        block.add_css_class(css_class)
        block.set_size_request(width, height)
        return block

    def refresh(self) -> None:
        """Synchronize controls with the live session."""
        self._desktop_icons.refresh()
        self._prefs = Settings()
        self._active_layout = self._prefs.get("active_layout", "")
        notification_position = self._notification_position_for_active_layout()
        notification_default = NOTIFICATION_POSITION_DEFAULTS.get(
            self._active_layout,
            "top-center",
        )

        self._syncing = True
        self._notification_position_buttons[notification_position].set_active(True)
        for value, badge in self._notification_position_badges.items():
            badge.set_visible(value == notification_default)
        self._syncing = False
        self._notification_flow.set_sensitive(True)

        supports_menu = self._active_layout in MENU_LAYOUT_DEFAULTS
        self._shell_group.set_visible(supports_menu)
        if not supports_menu:
            return

        installed = ExtMgr.is_installed(COMMUNITY_MENU_UUID)
        enabled = ExtMgr.is_enabled(COMMUNITY_MENU_UUID) if installed else False
        stored_super = self._prefs.get("super_key_opens_menu")
        if not isinstance(stored_super, bool):
            stored_super = dconf_read(SUPER_KEY_PATH) != "false"
        menu_style = (dconf_read(MENU_LAYOUT_PATH) or "").strip("'\"")
        if menu_style not in self._menu_style_buttons:
            menu_style = MENU_LAYOUT_DEFAULTS[self._active_layout]

        self._syncing = True
        self._menu_switch.set_active(enabled)
        self._super_row.set_selected(0 if stored_super else 1)
        self._menu_style_buttons[menu_style].set_active(True)
        default_style = MENU_LAYOUT_DEFAULTS[self._active_layout]
        for value, badge in self._menu_style_badges.items():
            badge.set_visible(value == default_style)
        self._syncing = False

        self._menu_switch.set_sensitive(installed)
        self._super_row.set_sensitive(installed and enabled)
        self._style_flow.set_sensitive(installed and enabled)
        self._menu_row.set_subtitle(
            tr("Use Community Menu as the application menu")
            if installed
            else tr("Community Menu is not installed")
        )

    def _notification_position_for_active_layout(self) -> str:
        saved = self._prefs.get("notification_positions", {})
        value = saved.get(self._active_layout, "") if isinstance(saved, dict) else ""
        if value in NOTIFICATION_POSITION_VALUES:
            return value
        return NOTIFICATION_POSITION_DEFAULTS.get(self._active_layout, "top-center")

    def _on_notification_position_toggled(
        self,
        button: Gtk.ToggleButton,
        value: str,
        label: str,
    ) -> None:
        if self._syncing or not button.get_active():
            return
        self._notification_flow.set_sensitive(False)

        def task() -> None:
            ok, message = HelperClient.set_notification_position(value)
            GLib.idle_add(
                self._finish_notification_position_change,
                ok,
                message,
                value,
                label,
            )

        self._pool.submit(task)

    def _finish_notification_position_change(
        self,
        ok: bool,
        message: str,
        value: str,
        label: str,
    ) -> bool:
        if ok:
            saved = self._prefs.get("notification_positions", {})
            saved = dict(saved) if isinstance(saved, dict) else {}
            saved[self._active_layout] = value
            if not self._save_preference("notification_positions", saved):
                self.refresh()
                return GLib.SOURCE_REMOVE
            self._toast(
                tr("{position} notification position applied").format(
                    position=label,
                )
            )
            GLib.timeout_add(200, self._send_notification_preview)
        else:
            self._toast(
                tr("Could not change the notification position: {message}").format(
                    message=message,
                )
            )
        self.refresh()
        return GLib.SOURCE_REMOVE

    def _save_preference(self, key: str, value) -> bool:
        if self._prefs.set(key, value):
            return True
        self._toast(f"{tr('Operation failed')}: {self._prefs.last_error}")
        return False

    def _send_notification_preview(self) -> bool:
        root = self.get_root()
        app = root.get_application() if root else None
        if app:
            notification = Gio.Notification.new(tr("Notification preview"))
            notification.set_body(tr("Notifications will appear here."))
            app.send_notification("notification-position-preview", notification)
        return GLib.SOURCE_REMOVE

    def _on_menu_toggled(self, switch: Gtk.Switch, param) -> None:
        if self._syncing:
            return
        enable = switch.get_active()
        switch.set_sensitive(False)

        def task() -> None:
            ok, message = ExtMgr.set_enabled(COMMUNITY_MENU_UUID, enable)
            GLib.idle_add(self._finish_menu_toggle, ok, message, enable)

        self._pool.submit(task)

    def _finish_menu_toggle(self, ok: bool, message: str, enable: bool) -> bool:
        if ok:
            if not self._save_preference("community_menu_enabled", enable):
                self.refresh()
                return GLib.SOURCE_REMOVE
            self._toast(
                tr("Application menu enabled") if enable else tr("Application menu disabled")
            )
        else:
            self._toast(
                tr("Could not change the application menu: {message}").format(
                    message=message,
                )
            )
        self.refresh()
        return GLib.SOURCE_REMOVE

    def _on_menu_style_toggled(
        self,
        button: Gtk.ToggleButton,
        value: str,
        name: str,
    ) -> None:
        if self._syncing or not button.get_active():
            return
        self._style_flow.set_sensitive(False)

        def task() -> None:
            ok, message = dconf_write(MENU_LAYOUT_PATH, f"'{value}'")
            GLib.idle_add(
                self._finish_menu_style_change,
                ok,
                message,
                value,
                name,
            )

        self._pool.submit(task)

    def _finish_menu_style_change(
        self,
        ok: bool,
        message: str,
        value: str,
        name: str,
    ) -> bool:
        if ok:
            if not self._save_preference("community_menu_layout", value):
                self.refresh()
                return GLib.SOURCE_REMOVE
            self._toast(tr("{name} menu style applied").format(name=name))
        else:
            self._toast(
                tr("Could not change the menu style: {message}").format(
                    message=message,
                )
            )
        self.refresh()
        return GLib.SOURCE_REMOVE

    def _on_super_changed(self, row: Adw.ComboRow, param) -> None:
        if self._syncing:
            return
        opens_menu = row.get_selected() == 0
        row.set_sensitive(False)

        def task() -> None:
            ok, message = dconf_write(
                SUPER_KEY_PATH,
                "true" if opens_menu else "false",
            )
            GLib.idle_add(self._finish_super_change, ok, message, opens_menu)

        self._pool.submit(task)

    def _finish_super_change(
        self,
        ok: bool,
        message: str,
        opens_menu: bool,
    ) -> bool:
        if ok:
            if not self._save_preference("super_key_opens_menu", opens_menu):
                self.refresh()
                return GLib.SOURCE_REMOVE
            self._toast(
                tr("Super opens the application menu")
                if opens_menu
                else tr("Super opens the overview")
            )
        else:
            self._toast(
                tr("Could not change the Super key: {message}").format(
                    message=message,
                )
            )
        self.refresh()
        return GLib.SOURCE_REMOVE
