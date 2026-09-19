# SPDX-License-Identifier: MIT
"""Real Gio notifications with private schemas, backend and session bus."""

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import settings_store

SCHEMA = "org.bigcommunity.tests.monitor"
SCHEMAS = f"""<schemalist>
  <schema id="{SCHEMA}" path="/org/bigcommunity/tests/monitor/">
    <key name="text" type="s"><default>''</default></key>
    <key name="enabled" type="b"><default>false</default></key>
    <key name="count" type="i"><default>0</default></key>
  </schema>
  <schema id="{SCHEMA}.relocatable">
    <key name="text" type="s"><default>''</default></key>
  </schema>
</schemalist>"""


@pytest.mark.parametrize("backend", ["memory", "dconf"])
def test_native_monitor_contract(tmp_path, backend):
    for command in ("glib-compile-schemas", "dbus-run-session", "gsettings"):
        if not shutil.which(command):
            pytest.skip(f"Requires {command}")
    (tmp_path / "monitor.gschema.xml").write_text(SCHEMAS)
    subprocess.run(["glib-compile-schemas", str(tmp_path)], check=True)
    profile = tmp_path / "dconf-profile"
    profile.write_text("user-db:bgc_monitor_test\n")
    env = os.environ.copy()
    env.update({
        "GSETTINGS_SCHEMA_DIR": str(tmp_path),
        "GSETTINGS_BACKEND": backend,
        "DCONF_PROFILE": str(profile),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "PYTHONPATH": str(Path(settings_store.__file__).parent),
        "G_DEBUG": "fatal-warnings",
    })
    result = subprocess.run(
        ["dbus-run-session", "--", sys.executable, __file__, backend],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "native monitor contract passed" in result.stdout


def native_probe(backend):
    from gi.repository import Gio, GLib

    monitor = settings_store.GSettingsMonitor()
    calls = {"text": [], "duplicate": [], "any": [], "replacement": []}
    main_thread = threading.get_ident()

    def callback(name):
        return lambda: calls[name].append(threading.get_ident())

    for schema in ("org.bigcommunity.tests.missing", SCHEMA + ".relocatable"):
        assert not monitor.watch(schema, "text", callback("text"))
        assert not monitor.watch_any(schema, callback("any"))
    assert not monitor.watch(SCHEMA, "missing", callback("text"))
    assert monitor.watch(SCHEMA, "text", callback("text"))
    assert monitor.watch(SCHEMA, "text", callback("duplicate"))
    assert monitor.watch_any(SCHEMA, callback("any"))
    assert not any(calls.values())
    writer = Gio.Settings.new(SCHEMA)

    def wait_for(predicate):
        if predicate():
            return
        loop = GLib.MainLoop()

        def check():
            if predicate():
                loop.quit()
            return GLib.SOURCE_CONTINUE

        check_id = GLib.timeout_add(5, check)
        timeout_id = GLib.timeout_add_seconds(5, lambda: loop.quit() or GLib.SOURCE_CONTINUE)
        try:
            loop.run()
            assert predicate(), calls
        finally:
            GLib.source_remove(check_id)
            GLib.source_remove(timeout_id)

    def write(key, value):
        if backend == "dconf":
            result = subprocess.run(
                ["gsettings", "set", SCHEMA, key, value.print_(False)],
                capture_output=True, text=True, timeout=5,
            )
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            # A worker writes; notifications must return to the creating context.
            results = []
            thread = threading.Thread(target=lambda: results.append(writer.set_value(key, value)))
            context = GLib.MainContext.default()
            assert context.acquire()
            try:
                thread.start()
                thread.join(timeout=5)
            finally:
                context.release()
            assert not thread.is_alive()
            assert results == [True]

    try:
        text_changes = 0
        for number in range(1, 31):
            key, value = (
                ("text", GLib.Variant("s", f"change-{number}")) if number % 3 == 1 else
                ("enabled", GLib.Variant("b", (number // 3) % 2 == 0)) if number % 3 == 2 else
                ("count", GLib.Variant("i", number))
            )
            text_changes += int(key == "text")
            write(key, value)
            wait_for(lambda: len(calls["any"]) == number)
            assert len(calls["text"]) == text_changes, calls
            assert len(calls["duplicate"]) == text_changes, calls
        monitor.disconnect_all()
        monitor.disconnect_all()
        assert monitor.watch_any(SCHEMA, callback("replacement"))
        for number in range(1, 11):
            write("text", GLib.Variant("s", f"replacement-{number}"))
            wait_for(lambda: len(calls["replacement"]) == number)
        assert len(calls["text"]) == len(calls["duplicate"]) == 10
        assert len(calls["any"]) == 30
        assert all(thread == main_thread for values in calls.values() for thread in values)
    finally:
        monitor.disconnect_all()
    print(f"native monitor contract passed: {backend}, 40 writes, 60 callbacks")


if __name__ == "__main__":
    native_probe(sys.argv[1])
