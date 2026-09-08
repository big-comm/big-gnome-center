"""Pre-Shell identity migration must preserve desktop preferences."""
from pathlib import Path

from session_migration import IDENTITIES, HelperClient, migrate_dump, migrate_lists
import pytest


def test_enabled_disabled_and_duplicate_identities():
    installed = set(IDENTITIES.values())
    old = list(IDENTITIES)
    new = list(IDENTITIES.values())
    assert migrate_lists(old + [new[1], "custom"], [old[1], "disabled"], installed) == (
        new + ["custom"], ["disabled"])
    assert migrate_lists([], old, installed) == ([], new)


def test_missing_replacement_and_idempotence():
    old = list(IDENTITIES)
    assert migrate_lists(old, [], set()) == (old, [])
    current = migrate_lists(old, [], set(IDENTITIES.values()))
    assert migrate_lists(*current, set(IDENTITIES.values())) == current


def test_preserves_layout_engines_and_disabled_bigshot():
    enabled = ["dash-to-dock@micxgx.gmail.com", "blur-my-shell@aunetx", "custom"]
    disabled = ["big-shot@bigcommunity.org"]
    assert migrate_lists(enabled, disabled, set(IDENTITIES.values())) == (
        enabled, ["big-shot@communitybig.org"])


def test_saved_preferences_migrate_without_applying_original():
    text = """[org/gnome/shell]
enabled-extensions=['layout-switcher-helper@bigcommunity.org', 'big-shot@bigcommunity.org', 'dash-to-dock@micxgx.gmail.com']

[org/gnome/shell/extensions/dash-to-dock]
dash-max-icon-size=57
autohide=true

[custom]
value='preserve me'
"""
    result = migrate_dump(text, set(IDENTITIES.values()))
    assert result == text.replace("layout-switcher-helper@bigcommunity.org", "layout-switcher-helper@communitybig.org").replace("big-shot@bigcommunity.org", "big-shot@communitybig.org")
    assert migrate_dump(result, set(IDENTITIES.values())) == result


def test_pending_classic_is_untouched():
    text = """[org/gnome/shell]
enabled-extensions=['layout-switcher-helper@communitybig.org', 'layout-switcher-runtime@communitybig.org', 'big-shot@communitybig.org']

[org/communitybig/layout-switcher/runtime]
active-layout='Classic'
"""
    assert migrate_dump(text, set(IDENTITIES.values())) == text


def test_systemd_orders_migration_before_shell_and_fails_open():
    root = Path(__file__).resolve().parents[1]
    unit = (root / "usr/lib/systemd/user/org.gnome.Shell@.service.d/50-big-gnome-center-migration.conf").read_text()
    assert "ExecStartPre=-/usr/bin/timeout 15s" in unit
    assert "session_migration.py %i" in unit


def test_refuses_live_shell_before_writing(monkeypatch):
    from gi.repository import Gio, GLib
    from types import SimpleNamespace
    import session_migration

    monkeypatch.setattr(Gio, "bus_get_sync", lambda *args: SimpleNamespace(
        call_sync=lambda *args: GLib.Variant("(b)", (True,))))
    monkeypatch.setattr(HelperClient, "installed_extension_uuids", lambda: pytest.fail("must not inspect or write settings"))
    with pytest.raises(RuntimeError, match="Shell is running"):
        session_migration.run()


def test_prestart_migrates_saved_and_live_lists_with_backup(monkeypatch, tmp_path):
    from gi.repository import Gio, GLib
    from types import SimpleNamespace
    import layout_applier
    import session_migration

    installed = set(IDENTITIES.values())
    values = {"enabled-extensions": list(IDENTITIES), "disabled-extensions": ["unrelated"]}
    before = "[org/gnome/shell]\nenabled-extensions=" + repr(list(IDENTITIES)) + "\n"
    saved = tmp_path / "settings.gnome"
    saved.write_text(before)
    monkeypatch.setattr(layout_applier, "SETTINGS_GNOME", saved)
    monkeypatch.setattr(layout_applier, "_LAYOUT_HASH_FILE", tmp_path / "layout.sha256")
    monkeypatch.setattr(HelperClient, "installed_extension_uuids", lambda: installed)
    monkeypatch.setattr(Gio, "bus_get_sync", lambda *args: SimpleNamespace(
        call_sync=lambda *args: GLib.Variant("(b)", (False,))))
    def set_values(key, value):
        values[key] = value
        return True
    settings = SimpleNamespace(get_strv=lambda key: values[key], delay=lambda: None,
        set_strv=set_values, apply=lambda: None, revert=lambda: pytest.fail("unexpected revert"))
    monkeypatch.setattr(Gio.Settings, "new", lambda schema: settings)
    monkeypatch.setattr(Gio.Settings, "sync", lambda: None)
    session_migration.run()
    assert values["enabled-extensions"] == list(IDENTITIES.values())
    assert values["disabled-extensions"] == ["unrelated"]
    assert saved.read_text() == migrate_dump(before, installed)
    assert saved.with_suffix(".gnome.bak").read_text() == before
    session_migration.run()
    assert saved.with_suffix(".gnome.bak").read_text() == before
