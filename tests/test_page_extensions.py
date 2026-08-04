# SPDX-License-Identifier: MIT
"""Tests for installed-extension filtering."""

from ui.page_extensions import _matches_installed_extension


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
