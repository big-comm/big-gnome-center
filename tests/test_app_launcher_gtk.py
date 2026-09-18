# SPDX-License-Identifier: MIT
"""Native GTK launch lifetime and isolated GIO URI activation."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

import app_launcher as launcher
from ui.ext_detail_view import ExtDetailView
from ui.page_extensions import ExtensionsPage


def require_display():
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        pytest.skip("Requires a GTK display")


def test_native_button_launch_keeps_child_window_alive(tmp_path, monkeypatch):
    require_display()
    completed = tmp_path / "completed"
    executable = tmp_path / "gnome-extensions-app"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import gi\ngi.require_version('Gtk', '4.0')\n"
        "from gi.repository import Gtk, GLib\nfrom pathlib import Path\n"
        "Gtk.init()\nwindow = Gtk.Window(title='BGC A13 isolated launch test')\n"
        "window.set_default_size(240, 100)\nwindow.present()\n"
        "loop = GLib.MainLoop()\nGLib.timeout_add(6200, loop.quit)\nloop.run()\n"
        f"window.destroy()\nPath({str(completed)!r}).write_text('closed normally')\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    fallback = Mock()
    monkeypatch.setattr(launcher, "launch_uri", fallback)
    errors, ticks = [], []
    page = SimpleNamespace(_launch_error=errors.append)
    button = Gtk.Button(label="Launch test")
    button.connect("clicked", lambda widget: ExtensionsPage._open_gnome_extensions(page, widget))
    timer = GLib.timeout_add(20, lambda: ticks.append(True) or GLib.SOURCE_CONTINUE)
    start = time.monotonic()
    try:
        button.emit("clicked")
        assert time.monotonic() - start < 1
        context = GLib.MainContext.default()
        deadline = start + 12
        while not completed.exists() and time.monotonic() < deadline:
            while context.pending():
                context.iteration(False)
            time.sleep(0.005)
        assert completed.read_text() == "closed normally"
        assert time.monotonic() - start > 6
        assert len(ticks) > 50
        assert not errors
        fallback.assert_not_called()
    finally:
        GLib.source_remove(timer)


def test_detail_link_click_delivers_uri_and_errors(monkeypatch):
    require_display()
    launch = Mock()
    monkeypatch.setattr("ui.ext_detail_view.launch_uri", launch)
    errors = []
    page = SimpleNamespace(_launch_error=errors.append)
    url = "https://extensions.gnome.org/extension/123/?x=a&y=b"
    button = ExtDetailView._link_button(page, "Test link", url)
    button.emit("clicked")
    assert launch.call_args.args[0] == url
    launch.call_args.args[1]("activation refused")
    assert errors == ["activation refused"]


@pytest.mark.parametrize("registered", [True, False])
def test_native_uri_handler_uses_isolated_associations(tmp_path, registered):
    if not shutil.which("dbus-run-session"):
        pytest.skip("Requires dbus-run-session")
    apps = tmp_path / "data" / "applications"
    apps.mkdir(parents=True)
    output = tmp_path / "opened-uri"
    handler = tmp_path / "handler"
    handler.write_text(
        f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
        f"Path({str(output)!r}).write_text(sys.argv[1])\n"
    )
    handler.chmod(0o755)
    desktop = apps / "bgc-a13-test.desktop"
    desktop.write_text(
        "[Desktop Entry]\nType=Application\nName=BGC URI test\n"
        f"Exec={handler} %u\nMimeType=x-scheme-handler/bgc-a13-test;\n"
    )
    source = str(Path(launcher.__file__).parent)
    script = tmp_path / "probe.py"
    script.write_text(
        "import sys,time\nfrom pathlib import Path\nfrom gi.repository import Gio,GLib\n"
        f"sys.path.insert(0, {source!r})\nfrom app_launcher import launch_uri\n"
        f"registered = {registered!r}\n"
        f"desktop = Gio.DesktopAppInfo.new_from_filename({str(desktop)!r})\n"
        "if registered:\n"
        "    assert desktop.set_as_default_for_type('x-scheme-handler/bgc-a13-test')\n"
        f"output = Path({str(output)!r})\n"
        "uri = 'bgc-a13-test://folder/a%20b?x=1&y=two'\nerrors=[]\n"
        "launch_uri(uri, errors.append)\ncontext=GLib.MainContext.default()\n"
        "deadline=time.monotonic()+5\n"
        "while not errors and not output.exists() and time.monotonic()<deadline:\n"
        "    while context.pending(): context.iteration(False)\n"
        "    time.sleep(0.005)\n"
        "if registered:\n"
        "    assert not errors, errors\n    assert output.read_text() == uri\n"
        "else:\n    assert len(errors)==1, errors\n    assert not output.exists()\n"
        "print('native URI activation passed')\n"
    )
    env = os.environ.copy()
    env.update({
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_CONFIG_DIRS": str(tmp_path / "empty-config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_DATA_DIRS": str(tmp_path / "empty-data"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_CURRENT_DESKTOP": "BGC_TEST",
        "GIO_USE_PORTALS": "0",
    })
    result = subprocess.run(
        ["dbus-run-session", "--", sys.executable, str(script)],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
