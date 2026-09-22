# SPDX-License-Identifier: MIT
"""Contracts for baseline capture and transition coverage."""

from types import SimpleNamespace

import pytest

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


def test_apply_records_layout_only_after_success(monkeypatch, tmp_path):
    writes = []
    monkeypatch.setattr(
        runtime_baseline.LayoutApplier,
        "apply",
        lambda _path: (True, "ok"),
    )

    class Store:
        last_error = ""

        def set(self, key, value):
            writes.append((key, value))
            return True

    monkeypatch.setattr(runtime_baseline, "Settings", Store)

    runtime_baseline._apply("BigGnome", tmp_path)

    assert writes == [("active_layout", "BigGnome")]


def test_apply_does_not_record_failed_layout(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runtime_baseline.LayoutApplier,
        "apply",
        lambda _path: (False, "failed"),
    )
    monkeypatch.setattr(
        runtime_baseline,
        "Settings",
        lambda: (_ for _ in ()).throw(AssertionError("store must not open")),
    )

    with pytest.raises(RuntimeError, match="cannot apply BigGnome"):
        runtime_baseline._apply("BigGnome", tmp_path)


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


def test_desktop_entry_overview_check_requires_a_closed_overview():
    def snapshot(visible, visible_target):
        return SimpleNamespace(
            runtime_diagnostics={
                "runtime": {
                    "taskbar": {
                        "lifecycle": {
                            "serviceHost": {
                                "overviewIntegration": {
                                    "overviewVisible": visible,
                                    "overviewVisibleTarget": visible_target,
                                }
                            }
                        }
                    }
                }
            }
        )

    for layout in ("Hybrid", "Desk UX", "Classic"):
        assert runtime_baseline._desktop_entry_overview_check(
            snapshot(False, False), layout
        ).status == "PASS"
        assert runtime_baseline._desktop_entry_overview_check(
            snapshot(True, True), layout
        ).status == "FAIL"
    assert runtime_baseline._desktop_entry_overview_check(
        snapshot(True, True), "BigGnome"
    ) is None


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
