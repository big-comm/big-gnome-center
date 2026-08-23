# SPDX-License-Identifier: MIT
"""Tests for installed-extension filtering."""

from pathlib import Path

from ui.page_extensions import (
    _installed_extension_description,
    _matches_installed_extension,
)


SOURCE = Path(__file__).parents[1] / "usr/share/layout-switcher/ui/page_extensions.py"


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

    assert description == "Captures, annotates and records the screen."
    assert _matches_installed_extension(ext, "records the screen")


def test_external_extension_description_uses_its_first_paragraph():
    ext = {
        "uuid": "example@example.org",
        "description": "Useful desktop feature.\n\nLong support and donation details.",
    }

    assert _installed_extension_description(ext) == "Useful desktop feature."


def test_missing_extension_description_has_a_clear_fallback():
    ext = {"uuid": "example@example.org", "description": ""}

    assert _installed_extension_description(ext) == (
        "Description not provided by the developer."
    )


def test_featured_extensions_keep_the_approved_compact_grid():
    source = SOURCE.read_text()

    assert "self._feat_flow.set_max_children_per_line(2)" in source
    assert "self._feat_flow.set_max_children_per_line(3)" not in source
    assert "self._feat_flow.set_valign(Gtk.Align.START)" in source
