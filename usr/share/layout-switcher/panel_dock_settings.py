# SPDX-License-Identifier: MIT
"""Live Community Dock and Community Panel settings."""

from constants import EXT_SYS_DIR, EXT_USER_DIR

COMMUNITY_DOCK_UUID = "community-dock@communitybig.org"
COMMUNITY_PANEL_UUID = "community-panel@communitybig.org"
DOCK_SCHEMA = "org.gnome.shell.extensions.dash-to-dock"
PANEL_SCHEMA = "org.communitybig.panel-and-dock"
COMMUNITY_PANEL_SCHEMA = "org.gnome.shell.extensions.dash-to-panel"
VISIBILITY_MODES = ("always-visible", "always-hidden", "intelligent")
INDICATOR_STYLES = ("dot", "hybrid", "desk-ux")


def _extension_settings(schema_id: str, extension_uuid: str):
    from gi.repository import Gio

    for extension_root in (EXT_USER_DIR, EXT_SYS_DIR):
        schema_dir = extension_root / extension_uuid / "schemas"
        if not (schema_dir / "gschemas.compiled").is_file():
            continue
        source = Gio.SettingsSchemaSource.new_from_directory(
            str(schema_dir),
            Gio.SettingsSchemaSource.get_default(),
            False,
        )
        schema = source.lookup(schema_id, True)
        if schema:
            return Gio.Settings.new_full(schema, None, None)
    return Gio.Settings.new(schema_id)


class PanelDockSettings:
    """Map the compact UI onto the active Community components."""

    def __init__(
        self,
        *,
        dock_active: bool = True,
        community_panel_active: bool = False,
    ) -> None:
        self.dock_active = dock_active
        self.community_panel_active = community_panel_active
        self.dock = _extension_settings(DOCK_SCHEMA, COMMUNITY_DOCK_UUID)
        self.panel = _extension_settings(PANEL_SCHEMA, COMMUNITY_DOCK_UUID)
        self.community_panel = _extension_settings(
            COMMUNITY_PANEL_SCHEMA,
            COMMUNITY_PANEL_UUID,
        )

    def dock_opacity(self) -> int:
        return round(self.dock.get_double("background-opacity") * 100)

    def set_dock_opacity(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        self.dock.set_boolean("custom-background-color", True)
        self.dock.set_enum("transparency-mode", 1)  # FIXED
        self.dock.set_double("background-opacity", percent / 100)

    def dock_visibility(self) -> str:
        if self.dock.get_boolean("dock-fixed"):
            return "always-visible"
        if self.dock.get_boolean("manualhide") or not self.dock.get_boolean("intellihide"):
            return "always-hidden"
        return "intelligent"

    def set_dock_visibility(self, mode: str) -> None:
        if mode not in VISIBILITY_MODES:
            raise ValueError(f"invalid dock visibility: {mode}")
        self.dock.set_boolean("manualhide", False)
        self.dock.set_boolean("dock-fixed", mode == "always-visible")
        self.dock.set_boolean("intellihide", mode == "intelligent")
        self.dock.set_boolean("autohide", mode != "always-visible")

    def indicator_style(self) -> str:
        if self.community_panel_active:
            focused = self.community_panel.get_string("dot-style-focused")
            unfocused = self.community_panel.get_string("dot-style-unfocused")
            if focused == "METRO" and unfocused == "DASHES":
                return "desk-ux"
            if focused == "SEGMENTED" and unfocused == "SEGMENTED":
                return "hybrid"
            return "dot"
        style = self.panel.get_string("indicator-style")
        return style if style in INDICATOR_STYLES else "dot"

    def set_indicator_style(self, style: str) -> None:
        if style not in INDICATOR_STYLES:
            raise ValueError(f"invalid indicator style: {style}")
        if self.community_panel_active:
            focused, unfocused, size = {
                "dot": ("DOTS", "DOTS", 6),
                "hybrid": ("SEGMENTED", "SEGMENTED", 3),
                "desk-ux": ("METRO", "DASHES", 3),
            }[style]
            self.community_panel.set_string("dot-style-focused", focused)
            self.community_panel.set_string("dot-style-unfocused", unfocused)
            self.community_panel.set_int("dot-size", size)
            return
        self.dock.set_enum("running-indicator-style", 0)  # DEFAULT
        self.panel.set_string("indicator-style", style)

    def panel_opacity(self) -> int:
        if self.community_panel_active:
            return round(self.community_panel.get_double("trans-panel-opacity") * 100)
        return self.panel.get_uint("panel-opacity")

    def set_panel_opacity(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        if self.community_panel_active:
            self.community_panel.set_boolean("trans-use-custom-opacity", True)
            self.community_panel.set_boolean("trans-use-dynamic-opacity", False)
            self.community_panel.set_double("trans-panel-opacity", percent / 100)
            return
        self.panel.set_uint("panel-opacity", percent)

    def panel_visibility(self) -> str:
        if self.community_panel_active:
            if not self.community_panel.get_boolean("intellihide"):
                return "always-visible"
            if self.community_panel.get_boolean(
                "intellihide-hide-from-windows"
            ) or self.community_panel.get_boolean("intellihide-hide-from-monitor-windows"):
                return "intelligent"
            return "always-hidden"
        mode = self.panel.get_string("panel-visibility")
        return mode if mode in VISIBILITY_MODES else "always-visible"

    def set_panel_visibility(self, mode: str) -> None:
        if mode not in VISIBILITY_MODES:
            raise ValueError(f"invalid panel visibility: {mode}")
        if self.community_panel_active:
            intelligent = mode == "intelligent"
            self.community_panel.set_boolean("intellihide", mode != "always-visible")
            self.community_panel.set_boolean("intellihide-hide-from-windows", intelligent)
            self.community_panel.set_boolean("intellihide-hide-from-monitor-windows", False)
            self.community_panel.set_string("intellihide-behaviour", "FOCUSED_WINDOWS")
            self.community_panel.set_boolean("intellihide-use-pointer", True)
            return
        self.panel.set_string("panel-visibility", mode)
