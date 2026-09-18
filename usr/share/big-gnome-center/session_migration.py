# SPDX-License-Identifier: MIT
"""Migrate extension identities before Shell imports either helper module."""

import logging
import sys

from helper_client import (
    BIG_SHOT_UUID, COMMUNITY_MENU_UUID, HELPER_UUID,
    LEGACY_BIG_SHOT_UUID, LEGACY_COMMUNITY_MENU_UUID, LEGACY_HELPER_UUID,
    HelperClient,
)

IDENTITIES = {
    LEGACY_HELPER_UUID: HELPER_UUID,
    LEGACY_BIG_SHOT_UUID: BIG_SHOT_UUID,
    LEGACY_COMMUNITY_MENU_UUID: COMMUNITY_MENU_UUID,
}


def migrate_lists(enabled, disabled, installed):
    """Rename installed identities; do not activate a different layout engine."""
    def convert(values):
        result = []
        for value in values:
            target = IDENTITIES.get(value, value)
            target = target if target in installed else value
            if target not in result:
                result.append(target)
        return result

    enabled_out = convert(enabled)
    disabled_out = [value for value in convert(disabled) if value not in enabled_out]
    return enabled_out, disabled_out


def migrate_dump(text, installed):
    """Preserve pending layouts and every setting outside the two UUID lists."""
    from layout_applier import LayoutApplier

    section = "/org/gnome/shell"
    values = LayoutApplier._section_key_values(text, section)
    keys = ("enabled-extensions", "disabled-extensions")
    before = [LayoutApplier._string_list(values.get(key)) for key in keys]
    after = migrate_lists(*before, installed)
    for key, old, new in zip(keys, before, after):
        if key in values and old != new:
            text = LayoutApplier._replace_or_add_dconf_key(
                text, section, key, LayoutApplier._quote_string_list(new))
    return text


def run():
    from gi.repository import Gio, GLib
    from layout_applier import SETTINGS_GNOME
    from layout_persistence import open_store

    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    reply = bus.call_sync(
        "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "NameHasOwner", GLib.Variant("(s)", ("org.gnome.Shell",)),
        GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, 2000, None)
    if reply.unpack()[0]:
        raise RuntimeError("Refusing helper migration while Shell is running")

    installed = HelperClient.installed_extension_uuids()
    settings = Gio.Settings.new("org.gnome.shell")
    keys = ("enabled-extensions", "disabled-extensions")
    before = [list(settings.get_strv(key)) for key in keys]
    after = migrate_lists(*before, installed)

    # The distribution restores this file before each login. Migrate it too,
    # without replacing a layout explicitly staged by the user.
    if SETTINGS_GNOME.is_symlink():
        raise RuntimeError("Refusing symlinked settings.gnome")
    store = open_store(SETTINGS_GNOME)
    with store.lock():
        state = store.read()
        original = next(store.candidates(state), None)
        if original is not None:
            migrated = migrate_dump(original, installed)
            if original != migrated:
                if state.get('transaction'):
                    raise RuntimeError('Pending persistence recovery; defer identity migration')
                store.publish(migrated, managed=True, staged=state.get('staged', False))

    settings.delay()
    for key, old, new in zip(keys, before, after):
        if old != new and not settings.set_strv(key, new):
            settings.revert()
            raise RuntimeError(f"Cannot migrate {key}")
    settings.apply()
    Gio.Settings.sync()
    if tuple(before) != after:
        logging.info("Migrated legacy extension identities before Shell startup")


def main():
    # Never customize the display manager's separate Shell session.
    if len(sys.argv) > 1 and sys.argv[1] == "gdm":
        return 0
    logging.basicConfig(level=logging.INFO)
    try:
        run()
    except Exception:
        logging.exception("Session migration failed; leaving Shell startup available")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
