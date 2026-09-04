# SPDX-License-Identifier: MIT
"""Tests for installed-extension filtering."""

from pathlib import Path

from constants import tr
from ui.page_extensions import (
    _installed_extension_description,
    _matches_installed_extension,
    _visible_installed_extensions,
)


SOURCE = Path(__file__).parents[1] / "usr/share/layout-switcher/ui/page_extensions.py"


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
