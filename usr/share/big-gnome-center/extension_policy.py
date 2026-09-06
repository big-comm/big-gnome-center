# SPDX-License-Identifier: MIT
"""Removal policy shared by the UI and privileged helper."""

BUNDLED_EXTENSION_UUIDS = frozenset({
    "community-dock@communitybig.org",
    "community-menu@bigcommunity.org",
    "community-menu@communitybig.org",
    "community-panel@communitybig.org",
    "frosted-glass@communitybig.org",
    "layout-switcher-helper@bigcommunity.org",
    "layout-switcher-helper@communitybig.org",
    "layout-switcher-runtime@communitybig.org",
})

BUNDLED_REMOVAL_ERROR = "Extensions bundled with Big Gnome Center cannot be removed"
