# SPDX-License-Identifier: MIT
"""Tests for installed-extension filtering."""

from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

from constants import tr
from ui.page_extensions import (
    ExtensionsPage,
    _installed_extension_description,
    _matches_installed_extension,
    _visible_installed_extensions,
)

SOURCE = Path(__file__).parents[1] / "usr/share/big-gnome-center/ui/page_extensions.py"


def test_installed_list_hides_system_runtime_and_legacy_duplicates():
    hidden_uuids = {
        "community-dock@communitybig.org",
        "community-menu@bigcommunity.org",
        "community-panel@communitybig.org",
        "layout-switcher-helper@bigcommunity.org",
        "pamac-updates@manjaro.org",
    }
    extensions = [
        {"uuid": uuid, "user": False}
        for uuid in sorted(hidden_uuids)
    ] + [
        {"uuid": "community-menu@communitybig.org", "user": False},
        {"uuid": "gtk4-ding@smedius.gitlab.com", "user": False},
    ]

    visible = _visible_installed_extensions(extensions)

    assert [ext["uuid"] for ext in visible] == [
        "community-menu@communitybig.org",
        "gtk4-ding@smedius.gitlab.com",
    ]


def test_installed_list_keeps_user_copy_of_hidden_system_uuid():
    extension = {
        "uuid": "community-menu@bigcommunity.org",
        "user": True,
    }

    assert _visible_installed_extensions([extension]) == [extension]


def test_installed_extension_filter_matches_visible_metadata():
    ext = {
        "name": "Kiwi (is not Apple)",
        "uuid": "kiwi@kemma",
        "description": "macOS-inspired enhancements for GNOME",
    }

    assert _matches_installed_extension(ext, "kiwi")
    assert _matches_installed_extension(ext, "KEMMA")
    assert _matches_installed_extension(ext, "enhancements")
    assert _matches_installed_extension(ext, "  ")
    assert not _matches_installed_extension(ext, "telegram")


def test_bundled_extensions_use_short_curated_descriptions():
    ext = {
        "name": "Big Shot",
        "uuid": "big-shot@communitybig.org",
        "description": "Technical upstream description",
    }

    description = _installed_extension_description(ext)
    expected = tr("Captures, annotates and records the screen.")

    assert description == expected
    assert _matches_installed_extension(ext, expected)


def test_external_extension_description_uses_its_first_paragraph():
    ext = {
        "uuid": "example@example.org",
        "description": "Useful desktop feature.\n\nLong support and donation details.",
    }

    assert _installed_extension_description(ext) == "Useful desktop feature."


def test_missing_extension_description_has_a_clear_fallback():
    ext = {"uuid": "example@example.org", "description": ""}

    assert _installed_extension_description(ext) == tr(
        "Description not provided by the developer."
    )


def test_featured_extensions_keep_the_approved_compact_grid():
    source = SOURCE.read_text()

    assert "self._feat_flow.set_max_children_per_line(2)" in source
    assert "self._feat_flow.set_max_children_per_line(3)" not in source
    assert "self._feat_flow.set_valign(Gtk.Align.START)" in source


@pytest.mark.parametrize("failure", ["refused", "worker", "submit"])
def test_featured_toggle_failure_restores_once_without_new_operation(monkeypatch, failure):
    jobs, deliveries = [], []

    def submit(work):
        if failure == "submit":
            raise RuntimeError("executor stopped")
        jobs.append(work)

    page = SimpleNamespace(
        _pool=SimpleNamespace(submit=submit), _toast=Mock(),
        rebuild_featured=Mock(), refresh_installed=Mock(),
    )
    if hasattr(ExtensionsPage, "_toggle_extension"):
        page._toggle_extension = MethodType(ExtensionsPage._toggle_extension, page)

    class Switch:
        active = True
        sensitive = True

        def set_sensitive(self, value):
            self.sensitive = value

        def set_active(self, value):
            if value != self.active:
                self.active = value
                ExtensionsPage._toggle_feat(page, "test@example.org", value, None, None, self)

    switch = Switch()
    operation = Mock(return_value=(False, "refused"))
    if failure == "worker":
        operation.side_effect = RuntimeError("unexpected error")
    monkeypatch.setattr("ui.page_extensions.ShellReloader.apply_extension_state", operation)
    monkeypatch.setattr(
        "ui.page_extensions.GLib.idle_add",
        lambda callback, *args: deliveries.append((callback, args)),
    )
    ExtensionsPage._toggle_feat(page, "test@example.org", True, None, None, switch)
    if failure != "submit":
        assert not switch.sensitive
        jobs.pop(0)()
        for callback, args in deliveries:
            callback(*args)
    assert switch.active is False
    assert switch.sensitive
    assert not jobs
    assert operation.call_count == (0 if failure == "submit" else 1)
    page._toast.assert_called_once()
    page.rebuild_featured.assert_not_called()
    page.refresh_installed.assert_not_called()


def test_settings_refresh_coalesces_changes_and_preserves_pending_controls(monkeypatch):
    idle_add = Mock(return_value=123)
    monkeypatch.setattr("ui.page_extensions.GLib.idle_add", idle_add)
    page = SimpleNamespace(
        _pending_extension_toggles=0, _shell_refresh_source=0,
        _refresh_shell_settings=Mock(),
    )
    ExtensionsPage._on_shell_settings_changed(page, "favorite-apps")
    idle_add.assert_not_called()
    ExtensionsPage._on_shell_settings_changed(page, "enabled-extensions")
    ExtensionsPage._on_shell_settings_changed(page, "disabled-extensions")
    idle_add.assert_called_once_with(page._refresh_shell_settings)
    assert page._shell_refresh_source == 123

    page._shell_refresh_source = 0
    page._pending_extension_toggles = 1
    ExtensionsPage._on_shell_settings_changed(page, "enabled-extensions")
    assert idle_add.call_count == 1


@pytest.mark.parametrize("pending,attached", [(1, True), (0, False), (0, True)])
def test_settings_refresh_skips_busy_or_detached_pages(pending, attached):
    page = SimpleNamespace(
        _pending_extension_toggles=pending, _shell_refresh_source=123,
        get_root=lambda: object() if attached else None,
        rebuild_featured=Mock(), refresh_installed=Mock(),
    )
    assert ExtensionsPage._refresh_shell_settings(page) is False
    assert page._shell_refresh_source == 0
    expected = 1 if attached and not pending else 0
    assert page.rebuild_featured.call_count == expected
    assert page.refresh_installed.call_count == expected
