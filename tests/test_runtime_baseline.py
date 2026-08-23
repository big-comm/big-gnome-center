# SPDX-License-Identifier: MIT
"""Contracts for baseline capture and transition coverage."""

from runtime_baseline import LAYOUT_FILES, REFERENCE_ORDER, TRANSITIONS


SURFACE = {
    "BigGnome": "dock",
    "G-Unity": "dock",
    "Hybrid": "taskbar",
    "Desk UX": "taskbar",
    "Classic": "taskbar",
    "Minimal": "native",
}


def test_reference_run_covers_all_supported_layouts():
    assert set(REFERENCE_ORDER) == set(LAYOUT_FILES)
    assert len(REFERENCE_ORDER) == 6


def test_transition_matrix_covers_every_surface_direction():
    covered = {(SURFACE[source], SURFACE[target]) for source, target, _name in TRANSITIONS}

    assert covered == {
        ("dock", "dock"),
        ("dock", "taskbar"),
        ("dock", "native"),
        ("taskbar", "dock"),
        ("taskbar", "taskbar"),
        ("taskbar", "native"),
        ("native", "dock"),
        ("native", "taskbar"),
    }
