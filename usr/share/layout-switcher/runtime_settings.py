# SPDX-License-Identifier: MIT
"""Layout-owned settings for the focused GNOME Shell runtime."""

RUNTIME_SCHEMA = "org.communitybig.layout-switcher.runtime"

LAYOUT_DEFAULTS = {
    "BigGnome": {
        "dock-opacity": 77,
        "dock-visibility": "intelligent",
        "panel-opacity": 65,
        "panel-visibility": "always-visible",
        "indicator-style": "desk-ux",
        "dock-size": 39,
        "dock-hover": "default",
        "dock-magnification": 40,
        "dock-menu-side": "right",
        "skip-startup-overview": False,
    },
    "G-Unity": {
        "dock-opacity": 70,
        "dock-visibility": "always-visible",
        "panel-opacity": 70,
        "panel-visibility": "always-visible",
        "indicator-style": "dot",
        "dock-size": 39,
        "dock-hover": "default",
        "dock-magnification": 40,
        "skip-startup-overview": False,
    },
    "Hybrid": {
        "panel-opacity": 70,
        "panel-visibility": "always-visible",
        "indicator-style": "hybrid",
        "panel-height": 38,
        "dock-hover": "lift",
        "skip-startup-overview": True,
    },
    "Desk UX": {
        "panel-opacity": 65,
        "panel-visibility": "always-visible",
        "indicator-style": "desk-ux",
        "panel-height": 40,
        "dock-hover": "default",
        "skip-startup-overview": True,
    },
    "Classic": {
        "panel-opacity": 70,
        "panel-visibility": "always-visible",
        "indicator-style": "dot",
        "panel-height": 38,
        "dock-hover": "default",
        "skip-startup-overview": True,
    },
    "Minimal": {
        "panel-opacity": 65,
        "skip-startup-overview": False,
    },
}

_OVERRIDE_KEYS = {
    "dock-opacity": ("dock-opacity-overrides", "a{su}"),
    "dock-visibility": ("dock-visibility-overrides", "a{ss}"),
    "panel-opacity": ("panel-opacity-overrides", "a{su}"),
    "panel-visibility": ("panel-visibility-overrides", "a{ss}"),
    "indicator-style": ("indicator-style-overrides", "a{ss}"),
    "dock-size": ("dock-size-overrides", "a{su}"),
    "panel-height": ("panel-height-overrides", "a{su}"),
    "dock-hover": ("dock-hover-overrides", "a{ss}"),
    "dock-magnification": ("dock-magnification-overrides", "a{su}"),
    "dock-menu-side": ("dock-menu-side-overrides", "a{ss}"),
    "skip-startup-overview": ("skip-startup-overview-overrides", "a{sb}"),
}


class RuntimeSettings:
    """Store defaults and per-layout overrides in a stable schema."""

    def __init__(self, backend=None) -> None:
        self._sync_writes = backend is None
        if backend is None:
            from gi.repository import Gio

            schema = Gio.SettingsSchemaSource.get_default().lookup(RUNTIME_SCHEMA, True)
            if schema is None:
                raise RuntimeError(f"missing settings schema: {RUNTIME_SCHEMA}")
            backend = Gio.Settings.new_full(schema, None, None)
        self._settings = backend

    @staticmethod
    def supports_layout(layout: str) -> bool:
        return layout in LAYOUT_DEFAULTS

    def default(self, layout: str, setting: str, fallback=None):
        return LAYOUT_DEFAULTS.get(layout, {}).get(setting, fallback)

    def get(self, layout: str, setting: str, fallback=None):
        key, _variant_type = _OVERRIDE_KEYS[setting]
        overrides = self._settings.get_value(key).unpack()
        if layout in overrides:
            return overrides[layout]
        return self.default(layout, setting, fallback)

    def has_override(self, layout: str, setting: str) -> bool:
        key, _variant_type = _OVERRIDE_KEYS[setting]
        return layout in self._settings.get_value(key).unpack()

    def set(self, layout: str, setting: str, value) -> None:
        if not self.supports_layout(layout):
            return
        key, variant_type = _OVERRIDE_KEYS[setting]
        overrides = dict(self._settings.get_value(key).unpack())
        overrides[layout] = value
        self._set_value(key, variant_type, overrides)

    def reset_layout(self, layout: str, settings=None) -> None:
        selected = set(settings) if settings is not None else set(_OVERRIDE_KEYS)
        for setting in selected:
            key, variant_type = _OVERRIDE_KEYS[setting]
            overrides = dict(self._settings.get_value(key).unpack())
            if layout not in overrides:
                continue
            del overrides[layout]
            self._set_value(key, variant_type, overrides)
        self._sync()

    def serialized_overrides_without_layout(self, layout: str):
        """Return every override map with one layout removed."""
        from gi.repository import GLib

        serialized = {}
        for key, variant_type in _OVERRIDE_KEYS.values():
            overrides = dict(self._settings.get_value(key).unpack())
            overrides.pop(layout, None)
            serialized[key] = GLib.Variant(variant_type, overrides).print_(True)
        return serialized

    def is_imported(self, layout: str) -> bool:
        return layout in self._settings.get_strv("imported-layouts")

    def mark_imported(self, layout: str) -> None:
        imported = list(self._settings.get_strv("imported-layouts"))
        if layout not in imported:
            imported.append(layout)
            self._settings.set_strv("imported-layouts", imported)
            self._sync()

    def set_active_layout(self, layout: str) -> None:
        if self.supports_layout(layout):
            self._settings.set_string("active-layout", layout)

    def _set_value(self, key: str, variant_type: str, value) -> None:
        from gi.repository import GLib

        self._settings.set_value(key, GLib.Variant(variant_type, value))

    def _sync(self) -> None:
        if not self._sync_writes:
            return
        from gi.repository import Gio

        Gio.Settings.sync()
