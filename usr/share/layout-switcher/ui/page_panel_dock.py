# SPDX-License-Identifier: MIT
"""Community panel and dock controls."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from constants import tr
from extension_manager import ExtMgr
from panel_dock_settings import (
    COMMUNITY_DOCK_UUID,
    COMMUNITY_PANEL_UUID,
    DOCK_SIZE_RANGE,
    PANEL_HEIGHT_RANGE,
    PanelDockSettings,
)
from settings_store import Settings

VISIBILITY_VALUES = ("always-visible", "always-hidden", "intelligent")
VISIBILITY_LABELS = (
    tr("Always visible"),
    tr("Always hidden (show at edge)"),
    tr("Intelligent hiding"),
)
INDICATOR_STYLES = (
    ("dot", tr("Dot")),
    ("hybrid", tr("Hybrid line")),
    ("desk-ux", tr("Desk UX line")),
)
DOCK_HOVER_EFFECTS = (
    ("default", tr("Standard")),
    ("lift", tr("Gentle lift")),
)
RUNTIME_UUID = "layout-switcher-runtime@communitybig.org"
RUNTIME_DOCK_LAYOUTS = frozenset(("BigGnome", "G-Unity"))
RUNTIME_TASKBAR_LAYOUTS = frozenset(("Hybrid", "Desk UX", "Classic"))


class PanelDockPage(Gtk.Box):
    """Configure the active Community Dock and native panel."""

    def __init__(self, pool, toast_cb) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._toast = toast_cb
        self._syncing = False
        self._settings = None
        self._indicator_buttons = {}
        self._hover_buttons = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        content.set_margin_start(22)
        content.set_margin_end(22)
        content.set_margin_top(8)
        content.set_margin_bottom(22)

        self._dock_group = Adw.PreferencesGroup(
            title=tr("Dock"),
            description=tr("Configure the Community Dock appearance and visibility."),
        )
        (
            self._dock_opacity,
            self._dock_opacity_scale,
            self._dock_opacity_label,
        ) = self._opacity_row(tr("Dock transparency"), self._on_dock_opacity_changed)
        self._dock_group.add(self._dock_opacity)
        (
            self._dock_size,
            self._dock_size_scale,
            self._dock_size_label,
        ) = self._size_row(
            tr("Dock size"),
            DOCK_SIZE_RANGE,
            self._on_dock_size_changed,
        )
        self._dock_group.add(self._dock_size)
        self._hover_row = self._build_hover_effect_row()
        self._dock_group.add(self._hover_row)
        self._dock_visibility = self._visibility_row(
            tr("Dock visibility"),
            self._on_dock_visibility_changed,
        )
        self._dock_group.add(self._dock_visibility)
        self._indicator_row = self._build_indicator_style_row()
        self._dock_group.add(self._indicator_row)
        content.append(self._dock_group)

        self._panel_group = Adw.PreferencesGroup(
            title=tr("Panel"),
            description=tr("Configure the system panel appearance and visibility."),
        )
        (
            self._panel_opacity,
            self._panel_opacity_scale,
            self._panel_opacity_label,
        ) = self._opacity_row(tr("Panel transparency"), self._on_panel_opacity_changed)
        self._panel_group.add(self._panel_opacity)
        (
            self._panel_height,
            self._panel_height_scale,
            self._panel_height_label,
        ) = self._size_row(
            tr("Panel height"),
            PANEL_HEIGHT_RANGE,
            self._on_panel_height_changed,
        )
        self._panel_group.add(self._panel_height)
        self._panel_visibility = self._visibility_row(
            tr("Panel visibility"),
            self._on_panel_visibility_changed,
        )
        self._panel_group.add(self._panel_visibility)
        content.append(self._panel_group)

        self._restore_group = Adw.PreferencesGroup()
        restore_row = Adw.ActionRow(
            title=tr("Restore layout defaults"),
            subtitle=tr("Reset Panel and Dock options for the active layout."),
        )
        restore_button = Gtk.Button(label=tr("Restore"))
        restore_button.set_valign(Gtk.Align.CENTER)
        restore_button.add_css_class("destructive-action")
        restore_button.connect("clicked", self._on_restore_defaults_clicked)
        restore_row.add_suffix(restore_button)
        restore_row.set_activatable_widget(restore_button)
        self._restore_group.add(restore_row)
        content.append(self._restore_group)

        scroll.set_child(content)
        self.append(scroll)

    def _build_hover_effect_row(self) -> Adw.PreferencesRow:
        row = Adw.PreferencesRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        title = Gtk.Label(label=tr("Icon hover effect"), xalign=0)
        title.add_css_class("heading")
        box.append(title)
        hint = Gtk.Label(
            label=tr("Choose how dock icons react to the pointer."),
            wrap=True,
            xalign=0,
        )
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        box.append(hint)
        flow = Gtk.FlowBox()
        flow.add_css_class("dock-hover-grid")
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_min_children_per_line(2)
        flow.set_max_children_per_line(2)
        flow.set_column_spacing(10)
        flow.set_homogeneous(True)
        first_button = None
        for value, label in DOCK_HOVER_EFFECTS:
            button = self._build_hover_effect_button(value, label)
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)
            flow.append(button)
            self._hover_buttons[value] = button
        box.append(flow)
        row.set_child(box)
        return row

    def _build_hover_effect_button(self, value: str, label: str) -> Gtk.ToggleButton:
        button = Gtk.ToggleButton()
        button.add_css_class("dock-hover-card")
        button.set_tooltip_text(tr("Use the {effect} hover effect").format(effect=label))
        button.update_property([Gtk.AccessibleProperty.LABEL], [label])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_margin_top(10)
        box.set_margin_bottom(9)
        box.set_margin_start(8)
        box.set_margin_end(8)
        preview = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        preview.add_css_class("dock-hover-preview")
        preview.set_halign(Gtk.Align.CENTER)
        preview.set_size_request(-1, 58)
        for index in range(3):
            icon = Gtk.Box()
            icon.add_css_class("dock-hover-preview-icon")
            icon.set_size_request(30, 30)
            icon.set_valign(Gtk.Align.END)
            if value == "lift" and index == 1:
                icon.add_css_class("dock-hover-preview-raised")
                icon.set_margin_bottom(8)
            preview.append(icon)
        box.append(preview)
        effect_label = Gtk.Label(label=label)
        effect_label.add_css_class("heading")
        box.append(effect_label)
        button.set_child(box)
        button.connect("toggled", self._on_hover_effect_toggled, value)
        return button

    def _build_indicator_style_row(self) -> Adw.PreferencesRow:
        row = Adw.PreferencesRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        title = Gtk.Label(label=tr("Running app indicator"), xalign=0)
        title.add_css_class("heading")
        box.append(title)
        hint = Gtk.Label(
            label=tr("Choose the mark shown below running applications."),
            wrap=True,
            xalign=0,
        )
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        box.append(hint)

        flow = Gtk.FlowBox()
        flow.add_css_class("indicator-style-grid")
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_min_children_per_line(3)
        flow.set_max_children_per_line(3)
        flow.set_column_spacing(10)
        flow.set_row_spacing(10)
        flow.set_homogeneous(True)

        first_button = None
        for value, label in INDICATOR_STYLES:
            button = self._build_indicator_style_button(value, label)
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)
            flow.append(button)
            self._indicator_buttons[value] = button
        box.append(flow)
        row.set_child(box)
        return row

    def _build_indicator_style_button(
        self,
        value: str,
        label: str,
    ) -> Gtk.ToggleButton:
        button = Gtk.ToggleButton()
        button.add_css_class("indicator-style-card")
        button.set_tooltip_text(tr("Use the {style} indicator").format(style=label))
        button.update_property([Gtk.AccessibleProperty.LABEL], [label])

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        box.set_margin_top(10)
        box.set_margin_bottom(9)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.append(self._build_indicator_preview(value))
        style_label = Gtk.Label(label=label)
        style_label.add_css_class("heading")
        box.append(style_label)
        button.set_child(box)
        button.connect("toggled", self._on_indicator_style_toggled, value)
        return button

    @staticmethod
    def _build_indicator_preview(value: str) -> Gtk.Widget:
        sizes = {
            "dot": ((6, 6), (6, 6)),
            "hybrid": ((20, 4), (20, 4)),
            "desk-ux": ((8, 3), (18, 3)),
        }
        stage = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        stage.add_css_class("indicator-style-preview")
        stage.set_halign(Gtk.Align.FILL)
        stage.set_homogeneous(True)
        stage.set_size_request(-1, 72)
        for index in range(3):
            app = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
            app.set_halign(Gtk.Align.CENTER)
            app.set_valign(Gtk.Align.CENTER)
            icon = Gtk.Box()
            icon.add_css_class("indicator-preview-icon")
            icon.set_size_request(28, 28)
            app.append(icon)
            indicator = Gtk.Box()
            indicator.add_css_class("indicator-preview-mark")
            indicator.add_css_class(f"indicator-preview-{value}")
            indicator.add_css_class(
                "indicator-preview-active" if index == 1 else "indicator-preview-inactive"
            )
            indicator.set_halign(Gtk.Align.CENTER)
            inactive_size, active_size = sizes[value]
            width, height = active_size if index == 1 else inactive_size
            indicator.set_size_request(width, height)
            app.append(indicator)
            stage.append(app)
        return stage

    @staticmethod
    def _opacity_row(
        title: str,
        callback,
    ) -> tuple[Adw.ActionRow, Gtk.Scale, Gtk.Label]:
        row = Adw.ActionRow(title=title)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        transparent = Gtk.Label(label=tr("Transparent"))
        transparent.add_css_class("caption")
        box.append(transparent)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_draw_value(False)
        scale.set_size_request(250, -1)
        scale.connect("value-changed", callback)
        box.append(scale)

        value = Gtk.Label(label="0%")
        value.set_width_chars(4)
        box.append(value)
        opaque = Gtk.Label(label=tr("Opaque"))
        opaque.add_css_class("caption")
        box.append(opaque)
        row.add_suffix(box)
        return row, scale, value

    @staticmethod
    def _visibility_row(title: str, callback) -> Adw.ComboRow:
        row = Adw.ComboRow(
            title=title,
            subtitle=tr("Choose how this component behaves on the desktop."),
            model=Gtk.StringList.new(list(VISIBILITY_LABELS)),
        )
        row.connect("notify::selected", callback)
        return row

    @staticmethod
    def _size_row(
        title: str,
        value_range: tuple[int, int],
        callback,
    ) -> tuple[Adw.ActionRow, Gtk.Scale, Gtk.Label]:
        row = Adw.ActionRow(title=title)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        smaller = Gtk.Label(label=tr("Smaller"))
        smaller.add_css_class("caption")
        box.append(smaller)
        scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            value_range[0],
            value_range[1],
            1,
        )
        scale.set_draw_value(False)
        scale.set_size_request(250, -1)
        scale.connect("value-changed", callback)
        box.append(scale)
        value = Gtk.Label(label="0 px")
        value.set_width_chars(5)
        box.append(value)
        larger = Gtk.Label(label=tr("Larger"))
        larger.add_css_class("caption")
        box.append(larger)
        row.add_suffix(box)
        return row, scale, value

    def refresh(self) -> None:
        active_layout = Settings().get("active_layout", "")
        runtime_active = ExtMgr.is_enabled(RUNTIME_UUID)
        dock_active = ExtMgr.is_enabled(COMMUNITY_DOCK_UUID) or (
            runtime_active and active_layout in RUNTIME_DOCK_LAYOUTS
        )
        community_panel_active = ExtMgr.is_enabled(COMMUNITY_PANEL_UUID) or (
            runtime_active and active_layout in RUNTIME_TASKBAR_LAYOUTS
        )
        try:
            self._settings = (
                PanelDockSettings(
                    active_layout=active_layout,
                    dock_active=dock_active,
                    community_panel_active=community_panel_active,
                    runtime_active=runtime_active,
                )
                if dock_active or community_panel_active
                else None
            )
        except Exception:
            self._settings = None
        dock_available = self._settings is not None and dock_active
        panel_available = self._settings is not None and (dock_active or community_panel_active)
        indicator_available = self._settings is not None and (dock_active or community_panel_active)
        hover_available = self._settings is not None and (
            dock_active or community_panel_active
        )
        self._dock_group.set_visible(active_layout != "Classic")
        self._dock_group.set_sensitive(dock_available or indicator_available)
        self._panel_group.set_sensitive(panel_available)
        self._dock_opacity.set_visible(not community_panel_active)
        self._dock_size.set_visible(dock_available and not community_panel_active)
        self._hover_row.set_visible(hover_available and active_layout != "Classic")
        self._dock_visibility.set_visible(not community_panel_active)
        self._panel_height.set_visible(community_panel_active)
        self._indicator_row.set_sensitive(indicator_available)
        if community_panel_active:
            self._dock_group.set_title(tr("Taskbar"))
            self._dock_group.set_description(tr("Configure running application indicators."))
        elif not dock_available:
            self._dock_group.set_title(tr("Dock"))
            self._dock_group.set_description(tr("Available when Community Dock is active."))
        else:
            self._dock_group.set_title(tr("Dock"))
            self._dock_group.set_description(
                tr("Configure the Community Dock appearance and visibility.")
            )
        if not panel_available:
            self._panel_group.set_description(
                tr("Available when Community Dock or Community Panel is active.")
            )
        elif community_panel_active:
            self._panel_group.set_description(
                tr("Configure the Community Panel appearance and visibility.")
            )
        else:
            self._panel_group.set_description(
                tr("Configure the system panel appearance and visibility.")
            )
        if not self._settings:
            return

        self._syncing = True
        if dock_available:
            self._set_opacity(
                self._dock_opacity_scale,
                self._dock_opacity_label,
                self._settings.dock_opacity(),
            )
            self._dock_visibility.set_selected(
                VISIBILITY_VALUES.index(self._settings.dock_visibility())
            )
            self._set_size(
                self._dock_size_scale,
                self._dock_size_label,
                self._settings.dock_size(),
            )
        if hover_available:
            self._hover_buttons[self._settings.dock_hover_effect()].set_active(True)
        if indicator_available:
            self._indicator_buttons[self._settings.indicator_style()].set_active(True)
        if panel_available:
            self._set_opacity(
                self._panel_opacity_scale,
                self._panel_opacity_label,
                self._settings.panel_opacity(),
            )
            self._panel_visibility.set_selected(
                VISIBILITY_VALUES.index(self._settings.panel_visibility())
            )
            if community_panel_active:
                self._set_size(
                    self._panel_height_scale,
                    self._panel_height_label,
                    self._settings.panel_height(),
                )
        self._syncing = False

    @staticmethod
    def _set_opacity(scale: Gtk.Scale, label: Gtk.Label, value: int) -> None:
        scale.set_value(value)
        label.set_label(f"{value}%")

    @staticmethod
    def _set_size(scale: Gtk.Scale, label: Gtk.Label, value: int) -> None:
        scale.set_value(value)
        label.set_label(f"{value} px")

    def _on_dock_opacity_changed(self, scale: Gtk.Scale) -> None:
        value = round(scale.get_value())
        self._dock_opacity_label.set_label(f"{value}%")
        if not self._syncing and self._settings:
            self._settings.set_dock_opacity(value)

    def _on_panel_opacity_changed(self, scale: Gtk.Scale) -> None:
        value = round(scale.get_value())
        self._panel_opacity_label.set_label(f"{value}%")
        if not self._syncing and self._settings:
            self._settings.set_panel_opacity(value)

    def _on_dock_size_changed(self, scale: Gtk.Scale) -> None:
        value = round(scale.get_value())
        self._dock_size_label.set_label(f"{value} px")
        if not self._syncing and self._settings:
            self._settings.set_dock_size(value)

    def _on_panel_height_changed(self, scale: Gtk.Scale) -> None:
        value = round(scale.get_value())
        self._panel_height_label.set_label(f"{value} px")
        if not self._syncing and self._settings:
            self._settings.set_panel_height(value)

    def _on_dock_visibility_changed(self, row: Adw.ComboRow, param) -> None:
        if self._syncing or not self._settings:
            return
        mode = VISIBILITY_VALUES[min(row.get_selected(), len(VISIBILITY_VALUES) - 1)]
        self._settings.set_dock_visibility(mode)
        self._toast(tr("Dock visibility updated"))

    def _on_panel_visibility_changed(self, row: Adw.ComboRow, param) -> None:
        if self._syncing or not self._settings:
            return
        mode = VISIBILITY_VALUES[min(row.get_selected(), len(VISIBILITY_VALUES) - 1)]
        self._settings.set_panel_visibility(mode)
        self._toast(tr("Panel visibility updated"))

    def _on_indicator_style_toggled(
        self,
        button: Gtk.ToggleButton,
        style: str,
    ) -> None:
        if self._syncing or not self._settings or not button.get_active():
            return
        self._settings.set_indicator_style(style)
        self._toast(tr("Indicator style updated"))

    def _on_hover_effect_toggled(
        self,
        button: Gtk.ToggleButton,
        effect: str,
    ) -> None:
        if self._syncing or not self._settings or not button.get_active():
            return
        self._settings.set_dock_hover_effect(effect)
        self._toast(tr("Icon hover effect updated"))

    def _on_restore_defaults_clicked(self, button: Gtk.Button) -> None:
        if not self._settings:
            return
        self._settings.restore_layout_defaults()
        self.refresh()
        self._toast(tr("Layout Panel and Dock defaults restored"))
