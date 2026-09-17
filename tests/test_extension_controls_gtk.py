# SPDX-License-Identifier: MIT
"""Exercise real GTK switch notifications without changing Shell preferences."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from ui.page_extensions import ExtensionsPage


def _switch_in(widget):
    if isinstance(widget, Gtk.Switch):
        return widget
    child = widget.get_first_child()
    while child:
        found = _switch_in(child)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None


@pytest.mark.parametrize("featured", [False, True])
@pytest.mark.parametrize("outcome", ["accepted", "refused", "exception"])
def test_native_switch_repeated_completion_and_rollback(monkeypatch, featured, outcome):
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        pytest.skip("Requires a GTK display")
    Adw.init()
    main_thread = threading.get_ident()
    notifications = []

    def on_ui(*args):
        assert threading.get_ident() == main_thread
        notifications.append(args)

    with ThreadPoolExecutor(max_workers=1) as pool:
        page = SimpleNamespace(
            _pool=pool, _updates={}, _toast=on_ui,
            rebuild_featured=on_ui, refresh_installed=on_ui,
        )
        page._toggle_feat = MethodType(ExtensionsPage._toggle_feat, page)
        page._toggle_extension = MethodType(ExtensionsPage._toggle_extension, page)
        ext = {"uuid": "test@example.org", "name": "Test", "enabled": False}
        monkeypatch.setattr("ui.page_extensions.ExtMgr.can_remove", lambda uuid: False)
        if featured:
            widget = Gtk.Box()
            ExtensionsPage._build_feat_installed(page, widget, ext, widget, False)
        else:
            widget = ExtensionsPage._make_installed_row(page, ext)
        switch = _switch_in(widget)
        assert switch is not None
        try:
            for trial in range(20):
                entered, release = threading.Event(), threading.Event()

                def operation(uuid, enabled):
                    assert threading.get_ident() != main_thread
                    entered.set()
                    assert release.wait(5)
                    if outcome == "exception":
                        raise RuntimeError("test failure")
                    return outcome == "accepted", "test refusal"

                call = Mock(side_effect=operation)
                monkeypatch.setattr("ui.page_extensions.ShellReloader.apply_extension_state", call)
                before = switch.get_active()
                try:
                    switch.set_active(not before)
                    assert entered.wait(5)
                    assert not switch.get_sensitive()
                    # Duplicate notifications while pending must not enqueue work.
                    switch.notify("active")
                finally:
                    release.set()
                deadline = time.monotonic() + 5
                context = GLib.MainContext.default()
                while not switch.get_sensitive() and time.monotonic() < deadline:
                    context.iteration(False)
                    time.sleep(0.001)
                assert switch.get_sensitive()
                assert switch.get_active() == (not before if outcome == "accepted" else before)
                call.assert_called_once_with(ext["uuid"], not before)
            assert notifications
        finally:
            release.set()


def test_lists_follow_settings_committed_after_operation_completion(monkeypatch):
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        pytest.skip("Requires a GTK display")
    Adw.init()
    # Use a private in-memory backend even when run in a real desktop session.
    backend = Gio.memory_settings_backend_new()
    settings = Gio.Settings.new_with_backend("org.gnome.shell", backend)
    uuid = "test@example.org"
    settings.set_strv("enabled-extensions", [])
    ext = {"uuid": uuid, "name": "Test", "description": "Test", "icon": "folder-symbolic"}
    monkeypatch.setattr(Gio.Settings, "new", lambda schema: settings)
    monkeypatch.setattr("ui.page_extensions.FEATURED_EXTENSIONS", [ext])
    monkeypatch.setattr("ui.page_extensions.ExtMgr.is_installed", lambda value: True)
    monkeypatch.setattr("ui.page_extensions.ExtMgr.is_user_dir", lambda value: False)
    monkeypatch.setattr("ui.page_extensions.ExtMgr.can_remove", lambda value: False)
    monkeypatch.setattr("ui.page_extensions.ExtMgr.is_enabled",
                        lambda value: value in settings.get_strv("enabled-extensions"))
    monkeypatch.setattr("ui.page_extensions.ExtMgr.list_installed", lambda: [
        {**ext, "user": False, "enabled": uuid in settings.get_strv("enabled-extensions")},
    ])
    with ThreadPoolExecutor(max_workers=1) as pool:
        page = ExtensionsPage(pool, lambda message: None)
        window = Adw.Window()
        window.set_content(page)
        page.refresh_installed()
        try:
            assert not _switch_in(page._feat_cards[uuid]).get_active()
            assert not _switch_in(page._inst_container).get_active()
            # The completion refresh has already read the old persisted state.
            page.rebuild_featured()
            page.refresh_installed()
            settings.set_strv("enabled-extensions", [uuid])
            deadline = time.monotonic() + 3
            context = GLib.MainContext.default()
            while time.monotonic() < deadline:
                context.iteration(False)
                if (_switch_in(page._feat_cards[uuid]).get_active()
                        and _switch_in(page._inst_container).get_active()):
                    break
                time.sleep(0.001)
            assert _switch_in(page._feat_cards[uuid]).get_active()
            assert _switch_in(page._inst_container).get_active()
        finally:
            window.set_content(None)
            window.close()
