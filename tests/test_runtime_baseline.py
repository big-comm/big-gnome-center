# SPDX-License-Identifier: MIT
"""Contracts for baseline capture and transition coverage."""

from types import SimpleNamespace

import runtime_baseline
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


def test_transition_run_reuses_the_previous_verified_target(monkeypatch, tmp_path):
    applied = []
    monkeypatch.setattr(
        runtime_baseline,
        "_apply",
        lambda layout, _layouts_dir: applied.append(layout) or 0.1,
    )
    monkeypatch.setattr(runtime_baseline, "_set_scheme", lambda _scheme: None)
    monkeypatch.setattr(runtime_baseline.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        runtime_baseline,
        "_record",
        lambda *args, **kwargs: {"passed": True},
    )
    args = SimpleNamespace(
        transition_scheme="dark",
        layouts_dir=tmp_path,
        scheme_settle=0,
        root=tmp_path,
        settle_timeout=1,
        no_screenshots=True,
        external_capture=False,
    )

    runtime_baseline._transition_run(args, tmp_path)

    assert applied == [
        "BigGnome",
        "G-Unity",
        "Hybrid",
        "BigGnome",
        "Hybrid",
        "Desk UX",
        "Minimal",
        "BigGnome",
        "Minimal",
        "Classic",
        "Minimal",
    ]
