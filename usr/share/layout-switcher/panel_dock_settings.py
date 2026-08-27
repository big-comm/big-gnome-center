# SPDX-License-Identifier: MIT
"""Live Community Dock and Community Panel settings."""

import json

from constants import EXT_SYS_DIR, EXT_USER_DIR
from runtime_settings import RuntimeSettings

COMMUNITY_DOCK_UUID = "community-dock@communitybig.org"
COMMUNITY_PANEL_UUID = "community-panel@communitybig.org"
DOCK_SCHEMA = "org.gnome.shell.extensions.dash-to-dock"
PANEL_SCHEMA = "org.communitybig.panel-and-dock"
COMMUNITY_PANEL_SCHEMA = "org.gnome.shell.extensions.dash-to-panel"
VISIBILITY_MODES = ("always-visible", "always-hidden", "intelligent")
INDICATOR_STYLES = ("dot", "hybrid", "desk-ux")
DOCK_HOVER_EFFECTS = ("default", "lift")
DOCK_SIZE_RANGE = (28, 64)
PANEL_HEIGHT_RANGE = (32, 56)


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
        active_layout: str = "",
        dock_active: bool = True,
        community_panel_active: bool = False,
        runtime_active: bool = False,
        runtime=None,
    ) -> None:
        self.active_layout = active_layout
        self._restoring = False
        self.dock_active = dock_active
        self.community_panel_active = community_panel_active
        self.runtime_active = runtime_active
        self.runtime = runtime or RuntimeSettings()
        self.dock = _extension_settings(DOCK_SCHEMA, COMMUNITY_DOCK_UUID)
        self.panel = _extension_settings(PANEL_SCHEMA, COMMUNITY_DOCK_UUID)
        self.community_panel = _extension_settings(
            COMMUNITY_PANEL_SCHEMA,
            COMMUNITY_PANEL_UUID,
        )
        self._import_active_layout_once()

    def _remember(self, setting: str, value) -> None:
        if self.active_layout and not getattr(self, "_restoring", False):
            self.runtime.set(self.active_layout, setting, value)

    def restore_layout_defaults(self) -> None:
        if not self.runtime.supports_layout(self.active_layout):
            return
        defaults = {
            setting: self.runtime.default(self.active_layout, setting)
            for setting in (
                "dock-opacity",
                "dock-visibility",
                "panel-opacity",
                "panel-visibility",
                "indicator-style",
                "dock-size",
                "dock-hover",
                "panel-height",
            )
        }
        self.runtime.reset_layout(self.active_layout)
        self._restoring = True
        try:
            if self.dock_active:
                self.set_dock_opacity(defaults["dock-opacity"])
                self.set_dock_visibility(defaults["dock-visibility"])
                self.set_dock_size(defaults["dock-size"])
                self.set_dock_hover_effect(defaults["dock-hover"])
            elif self.community_panel_active:
                self.set_dock_hover_effect(defaults["dock-hover"])
            if self.dock_active or self.community_panel_active:
                self.set_panel_opacity(defaults["panel-opacity"])
                self.set_panel_visibility(defaults["panel-visibility"])
            if self.active_layout != "Classic" and (
                self.dock_active or self.community_panel_active
            ):
                self.set_indicator_style(defaults["indicator-style"])
            if self.community_panel_active:
                self.set_panel_height(defaults["panel-height"])
        finally:
            self._restoring = False

    def _import_active_layout_once(self) -> None:
        layout = self.active_layout
        if not layout or not self.runtime.supports_layout(layout):
            return
        self.runtime.set_active_layout(layout)
        if self.runtime.is_imported(layout):
            return
        if self.dock_active:
            self._remember("dock-opacity", self.dock_opacity())
            self._remember("dock-visibility", self.dock_visibility())
            self._remember("dock-size", self.dock_size())
            self._remember("dock-hover", self.dock_hover_effect())
        elif self.community_panel_active:
            self._remember("dock-hover", self.dock_hover_effect())
        if self.dock_active or self.community_panel_active:
            panel_opacity = (
                self._legacy_panel_opacity()
                if self.community_panel_active
                else self.panel_opacity()
            )
            self._remember("panel-opacity", panel_opacity)
            panel_visibility = (
                self._legacy_panel_visibility()
                if self.community_panel_active
                else self.panel_visibility()
            )
            self._remember("panel-visibility", panel_visibility)
            self._remember("indicator-style", self.indicator_style())
        if self.community_panel_active:
            self._remember("panel-height", self._legacy_panel_height())
        self.runtime.mark_imported(layout)

    def dock_opacity(self) -> int:
        return round(self.dock.get_double("background-opacity") * 100)

    def set_dock_opacity(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        self._remember("dock-opacity", percent)
        self.dock.set_boolean("custom-background-color", True)
        self.dock.set_enum("transparency-mode", 1)  # FIXED
        self.dock.set_double("background-opacity", percent / 100)

    def dock_size(self) -> int:
        return self.dock.get_int("dash-max-icon-size")

    def set_dock_size(self, size: int) -> None:
        size = max(DOCK_SIZE_RANGE[0], min(DOCK_SIZE_RANGE[1], int(size)))
        self._remember("dock-size", size)
        self.dock.set_int("dash-max-icon-size", size)

    def dock_hover_effect(self) -> str:
        if self.community_panel_active:
            return (
                "lift"
                if self.community_panel.get_boolean("animate-appicon-hover")
                else "default"
            )
        effect = self.panel.get_string("dock-hover-effect")
        return effect if effect in DOCK_HOVER_EFFECTS else "default"

    def set_dock_hover_effect(self, effect: str) -> None:
        if effect not in DOCK_HOVER_EFFECTS:
            raise ValueError(f"invalid dock hover effect: {effect}")
        self._remember("dock-hover", effect)
        if self.community_panel_active:
            self.community_panel.set_boolean("animate-appicon-hover", effect == "lift")
            if effect == "lift":
                self._set_community_panel_hover_profile()
            return
        self.panel.set_string("dock-hover-effect", effect)

    def _set_community_panel_hover_profile(self) -> None:
        from gi.repository import GLib

        self.community_panel.set_string("animate-appicon-hover-animation-type", "SIMPLE")
        profile = (
            ("animate-appicon-hover-animation-convexity", "a{sd}", 0.0),
            ("animate-appicon-hover-animation-duration", "a{su}", 220),
            ("animate-appicon-hover-animation-extent", "a{si}", 1),
            ("animate-appicon-hover-animation-rotation", "a{si}", 0),
            ("animate-appicon-hover-animation-travel", "a{sd}", 0.08),
            ("animate-appicon-hover-animation-zoom", "a{sd}", 1.08),
        )
        for key, variant_type, value in profile:
            values = dict(self.community_panel.get_value(key).unpack())
            values["SIMPLE"] = value
            self.community_panel.set_value(key, GLib.Variant(variant_type, values))

    def dock_visibility(self) -> str:
        if self.dock.get_boolean("dock-fixed"):
            return "always-visible"
        if self.dock.get_boolean("manualhide") or not self.dock.get_boolean("intellihide"):
            return "always-hidden"
        return "intelligent"

    def set_dock_visibility(self, mode: str) -> None:
        if mode not in VISIBILITY_MODES:
            raise ValueError(f"invalid dock visibility: {mode}")
        self._remember("dock-visibility", mode)
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
        self._remember("indicator-style", style)
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
        if (
            self.runtime_active
            and self.community_panel_active
            and self.runtime.supports_layout(self.active_layout)
        ):
            opacity = int(self.runtime.get(self.active_layout, "panel-opacity", 70))
            return max(0, min(100, opacity))
        return self._legacy_panel_opacity()

    def _legacy_panel_opacity(self) -> int:
        if self.community_panel_active:
            return round(self.community_panel.get_double("trans-panel-opacity") * 100)
        return self.panel.get_uint("panel-opacity")

    def set_panel_opacity(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        self._remember("panel-opacity", percent)
        if (
            self.runtime_active
            and self.community_panel_active
            and self.runtime.supports_layout(self.active_layout)
        ):
            return
        if self.community_panel_active:
            self.community_panel.set_boolean("trans-use-custom-opacity", True)
            self.community_panel.set_boolean("trans-use-dynamic-opacity", False)
            self.community_panel.set_double("trans-panel-opacity", percent / 100)
            return
        self.panel.set_uint("panel-opacity", percent)

    def panel_height(self) -> int:
        if (
            self.runtime_active
            and self.community_panel_active
            and self.runtime.supports_layout(self.active_layout)
        ):
            height = int(self.runtime.get(self.active_layout, "panel-height", 38))
            return max(PANEL_HEIGHT_RANGE[0], min(PANEL_HEIGHT_RANGE[1], height))
        return self._legacy_panel_height()

    def _legacy_panel_height(self) -> int:
        if not self.community_panel_active:
            default = self.runtime.default(self.active_layout, "panel-height", 38)
            return int(default)
        try:
            sizes = json.loads(self.community_panel.get_string("panel-sizes"))
            return int(next(iter(sizes.values())))
        except (AttributeError, TypeError, ValueError, StopIteration, json.JSONDecodeError):
            return 38

    def set_panel_height(self, height: int) -> None:
        height = max(PANEL_HEIGHT_RANGE[0], min(PANEL_HEIGHT_RANGE[1], int(height)))
        self._remember("panel-height", height)
        if (
            self.runtime_active
            and self.community_panel_active
            and self.runtime.supports_layout(self.active_layout)
        ):
            return
        if not self.community_panel_active:
            return
        try:
            sizes = json.loads(self.community_panel.get_string("panel-sizes"))
        except (TypeError, ValueError, json.JSONDecodeError):
            sizes = {}
        if not isinstance(sizes, dict) or not sizes:
            sizes = {"0": height}
        else:
            sizes = {key: height for key in sizes}
        self.community_panel.set_string(
            "panel-sizes",
            json.dumps(sizes, separators=(",", ":")),
        )

    def panel_visibility(self) -> str:
        if (
            self.runtime_active
            and self.community_panel_active
            and self.runtime.supports_layout(self.active_layout)
        ):
            mode = self.runtime.get(
                self.active_layout, "panel-visibility", "always-visible"
            )
            return mode if mode in VISIBILITY_MODES else "always-visible"
        return self._legacy_panel_visibility()

    def _legacy_panel_visibility(self) -> str:
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
        self._remember("panel-visibility", mode)
        if (
            self.runtime_active
            and self.community_panel_active
            and self.runtime.supports_layout(self.active_layout)
        ):
            return
        if self.community_panel_active:
            intelligent = mode == "intelligent"
            self.community_panel.set_int("intellihide-enable-start-delay", 0)
            self.community_panel.set_boolean("intellihide-hide-from-windows", intelligent)
            self.community_panel.set_boolean("intellihide-hide-from-monitor-windows", False)
            self.community_panel.set_string("intellihide-behaviour", "FOCUSED_WINDOWS")
            self.community_panel.set_boolean("intellihide-use-pointer", True)
            self.community_panel.set_boolean("intellihide", mode != "always-visible")
            return
        self.panel.set_string("panel-visibility", mode)
