# SPDX-License-Identifier: MIT
"""Dock position choices follow the active layout without writing on refresh."""

import unittest
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from tests.test_panel_dock import FakeRuntime, settings_fixture
from ui import page_panel_dock


def test_position_choices_and_restore_follow_active_layout(monkeypatch):
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        raise unittest.SkipTest("Requires a GTK display")
    Adw.init()
    layout = ["BigGnome"]
    runtime = FakeRuntime()
    preferences = Mock()
    preferences.get.side_effect = lambda _key, _default="": layout[0]
    monkeypatch.setattr(page_panel_dock, "Settings", lambda: preferences)
    monkeypatch.setattr(page_panel_dock.ExtMgr, "is_enabled",
                        lambda uuid: uuid == page_panel_dock.RUNTIME_UUID)

    def backend(**kwargs):
        settings = settings_fixture()
        settings.active_layout = kwargs["active_layout"]
        settings.runtime_active = True
        settings.runtime = runtime
        return settings

    monkeypatch.setattr(page_panel_dock, "PanelDockSettings", backend)
    page = page_panel_dock.PanelDockPage(None, lambda _message: None)
    assert page._dock_positions == ("bottom", "left", "right")
    assert page._dock_position.get_selected() == 0
    assert not runtime.values
    page._dock_position.set_selected(2)
    assert runtime.values[("BigGnome", "dock-position")] == "right"
    assert not page._menu_side_row.get_visible()
    layout[0] = "G-Unity"
    page.refresh()
    assert page._dock_positions == ("left", "right")
    assert page._dock_position.get_selected() == 0
    assert ("G-Unity", "dock-position") not in runtime.values
    page._dock_position.set_selected(1)
    layout[0] = "BigGnome"
    page.refresh()
    assert page._dock_position.get_selected() == 2
    page._on_restore_defaults_clicked(None)
    assert page._dock_position.get_selected() == 0
    assert page._menu_side_row.get_visible()
    assert runtime.values[("G-Unity", "dock-position")] == "right"
