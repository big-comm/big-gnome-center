# SPDX-License-Identifier: MIT
"""Contracts for the read-only Shell runtime audit."""

from pathlib import Path

from runtime_audit import (
    COMMUNITY_DOCK_UUID,
    COMMUNITY_MENU_UUID,
    COMMUNITY_PANEL_UUID,
    DESKTOP_ICONS_UUID,
    HELPER_UUID,
    RUNTIME_UUID,
    Snapshot,
    _extension_state_from_output,
    audit_snapshot,
)


def _payload(root: Path) -> None:
    extensions = root / "usr/share/gnome-shell/extensions"
    for uuid in (RUNTIME_UUID, COMMUNITY_PANEL_UUID, HELPER_UUID):
        path = extensions / uuid
        path.mkdir(parents=True)
        (path / "extension.js").touch()
        if uuid == COMMUNITY_PANEL_UUID:
            schemas = path / "schemas"
            schemas.mkdir()
            (schemas / "gschemas.compiled").touch()
    dock_schemas = extensions / COMMUNITY_DOCK_UUID / "schemas"
    dock_schemas.mkdir(parents=True)
    (dock_schemas / "gschemas.compiled").touch()


def _snapshot(**changes) -> Snapshot:
    values = {
        "active_layout": "BigGnome",
        "enabled_extensions": (RUNTIME_UUID, HELPER_UUID),
        "runtime_state": 1,
        "helper_state": 1,
        "shell_version": "GNOME Shell 50.4",
        "session_type": "wayland",
        "color_scheme": "prefer-dark",
        "icon_theme": "Papient-Dark",
        "indicator_overrides": {},
    }
    values.update(changes)
    if "runtime_diagnostics" not in changes:
        layout = values["active_layout"]
        surface, edge = {
            "BigGnome": ("dock", "bottom"),
            "G-Unity": ("dock", "left"),
            "Hybrid": ("taskbar", "bottom"),
            "Desk UX": ("taskbar", "bottom"),
            "Classic": ("taskbar", "bottom"),
            "Minimal": ("native", "top"),
        }[layout]
        indicator = {
            "BigGnome": "desk-ux",
            "G-Unity": "dot",
            "Hybrid": "hybrid",
            "Desk UX": "desk-ux",
            "Classic": "none",
            "Minimal": "none",
        }[layout]
        dock_opacity = {"BigGnome": 77, "G-Unity": 70}.get(layout)
        dock_size = 39 if surface == "dock" else None
        dock_actors = ([{
            "monitor": 0,
            "edge": edge,
            "width": 420,
            "height": 48,
            "opacity": dock_opacity,
            "iconSize": dock_size,
        }] if surface == "dock" else [])
        actor_height = {"Hybrid": 38, "Desk UX": 46, "Classic": 38}.get(layout)
        panel_opacity = {"Hybrid": 70, "Desk UX": 65, "Classic": 70}.get(layout)
        taskbar_actors = ([{
            "monitor": 0,
            "edge": edge,
            "width": 1920,
            "height": actor_height,
            "grouped": layout != "Classic",
            "opacity": panel_opacity,
            "intellihideEnabled": False,
            "affectsStruts": True,
        }] if surface == "taskbar" else [])
        values["runtime_diagnostics"] = {
            "monitors": [{"index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080}],
            "primaryMonitor": 0,
            "runtime": {
                "build": 4,
                "layout": layout,
                "expected": {
                    "surface": surface,
                    "edge": edge,
                    "extended": {
                        "BigGnome": False,
                        "G-Unity": True,
                    }.get(layout),
                    "hover": "lift" if layout == "Hybrid" else "default",
                    "indicator": indicator,
                    "visibility": {
                        "BigGnome": "intelligent",
                        "G-Unity": "always-visible",
                    }.get(layout, "always-visible" if surface == "taskbar" else None),
                    "labels": layout == "Classic",
                    "actorHeight": actor_height,
                    "opacity": dock_opacity if surface == "dock" else panel_opacity,
                    "iconSize": dock_size,
                },
                "dock": {
                    "active": surface == "dock",
                    "panel": {
                        "visible": True,
                        "fullscreen": False,
                        "affectsStruts": True,
                        "dockAffectsStruts": [True],
                    },
                    "extended": {
                        "BigGnome": False,
                        "G-Unity": True,
                    }.get(layout),
                    "indicator": indicator if surface == "dock" else "",
                    "hover": "default" if surface == "dock" else "",
                    "opacity": dock_opacity,
                    "iconSize": dock_size,
                    "visibility": {
                        "BigGnome": "intelligent",
                        "G-Unity": "always-visible",
                    }.get(layout),
                    "actors": dock_actors,
                },
                "taskbar": {
                    "active": surface == "taskbar",
                    "indicator": indicator if surface == "taskbar" else "",
                    "hover": "lift" if layout == "Hybrid" else "default",
                    "opacity": panel_opacity,
                    "visibility": "always-visible",
                    "actors": taskbar_actors,
                    "lifecycle": {
                        "managerOwned": surface == "taskbar",
                        "globalOwned": surface == "taskbar",
                        "appActionsOwned": surface == "taskbar",
                        "interactionsOwned": surface == "taskbar",
                        "indicatorRendererOwned": surface == "taskbar",
                        "indicatorRenderer": {
                            "style": indicator if surface == "taskbar" else "none"
                        },
                        "activationPending": False,
                    },
                },
            },
            "runtimeError": "",
            "stage": {
                "dock": [{} for _ in dock_actors],
                "taskbar": [{} for _ in taskbar_actors],
            },
        }
    return Snapshot(**values)


def _failures(checks):
    return {check.name: check.detail for check in checks if check.status == "FAIL"}


def test_audit_accepts_the_unified_biggnome_baseline(tmp_path):
    _payload(tmp_path)

    checks = audit_snapshot(_snapshot(), tmp_path, strict_layout=True)

    assert not _failures(checks)
    assert any(check.name == "active-layout" and "dock-bottom" in check.detail for check in checks)


def test_audit_rejects_parallel_and_inactive_runtimes(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot(
        enabled_extensions=(RUNTIME_UUID, HELPER_UUID, COMMUNITY_DOCK_UUID),
        runtime_state=2,
    )

    failures = _failures(audit_snapshot(snapshot, tmp_path))

    assert "single-runtime" in failures
    assert "runtime-active" in failures


def test_strict_audit_checks_original_hybrid_contract(tmp_path):
    _payload(tmp_path)
    valid = _snapshot(
        active_layout="Hybrid",
        enabled_extensions=(
            RUNTIME_UUID,
            HELPER_UUID,
            COMMUNITY_MENU_UUID,
            DESKTOP_ICONS_UUID,
        ),
    )
    invalid = _snapshot(
        active_layout="Hybrid",
        enabled_extensions=(RUNTIME_UUID, HELPER_UUID),
        indicator_overrides={"Hybrid": "desk-ux"},
    )

    assert not _failures(audit_snapshot(valid, tmp_path, strict_layout=True))
    failures = _failures(audit_snapshot(invalid, tmp_path, strict_layout=True))
    assert {"layout-menu", "layout-desktop-icons", "layout-indicator"} <= failures.keys()


def test_strict_audit_rejects_original_biggnome_with_lift_hover(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot()
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    runtime["expected"] = dict(runtime["expected"], hover="lift")
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(runtime_diagnostics=diagnostics),
            tmp_path,
            strict_layout=True,
        )
    )

    assert "layout-hover" in failures


def test_audit_rejects_dock_visibility_drift(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot()
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    runtime["dock"] = dict(runtime["dock"], visibility="always-visible")
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(runtime_diagnostics=diagnostics),
            tmp_path,
            strict_layout=True,
        )
    )

    assert "dock-visibility" in failures


def test_audit_rejects_owned_dock_setting_drift(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot()
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    dock = dict(
        runtime["dock"],
        indicator="dot",
        hover="lift",
        opacity=20,
        iconSize=64,
    )
    dock["actors"] = [dict(dock["actors"][0], opacity=21, iconSize=63)]
    runtime["dock"] = dock
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(runtime_diagnostics=diagnostics),
            tmp_path,
        )
    )

    assert {
        "dock-indicator",
        "dock-hover",
        "dock-opacity-setting",
        "dock-size-setting",
        "dock-opacity",
        "dock-size",
    } <= failures.keys()


def test_audit_rejects_taskbar_opacity_drift(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot(active_layout="Hybrid")
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    taskbar = dict(runtime["taskbar"], opacity=42)
    actors = [dict(actor) for actor in taskbar["actors"]]
    actors[0]["opacity"] = 43
    taskbar["actors"] = actors
    runtime["taskbar"] = taskbar
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(active_layout="Hybrid", runtime_diagnostics=diagnostics),
            tmp_path,
        )
    )

    assert {"taskbar-opacity-setting", "taskbar-opacity"} <= failures.keys()


def test_audit_rejects_taskbar_indicator_and_hover_drift(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot(active_layout="Hybrid")
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    taskbar = dict(runtime["taskbar"], indicator="desk-ux", hover="default")
    lifecycle = dict(taskbar["lifecycle"])
    lifecycle["indicatorRenderer"] = {"style": "desk-ux"}
    taskbar["lifecycle"] = lifecycle
    runtime["taskbar"] = taskbar
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(active_layout="Hybrid", runtime_diagnostics=diagnostics),
            tmp_path,
        )
    )

    assert {
        "taskbar-indicator-setting",
        "taskbar-indicator",
        "taskbar-hover",
    } <= failures.keys()


def test_audit_rejects_panel_visible_over_fullscreen_window(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot()
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    dock = dict(runtime["dock"])
    dock["panel"] = {"visible": True, "fullscreen": True}
    runtime["dock"] = dock
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(runtime_diagnostics=diagnostics),
            tmp_path,
            strict_layout=True,
        )
    )

    assert "fullscreen-panel" in failures


def test_audit_rejects_visible_dock_over_fullscreen_window(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot()
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    dock = dict(runtime["dock"])
    dock["panel"] = {
        "visible": False,
        "fullscreen": True,
        "affectsStruts": False,
        "dockAffectsStruts": [False],
        "dockVisible": [True],
    }
    runtime["dock"] = dock
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(runtime_diagnostics=diagnostics),
            tmp_path,
            strict_layout=True,
        )
    )

    assert "fullscreen-dock" in failures


def test_audit_rejects_extended_biggnome_dock(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot()
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    runtime["dock"] = dict(runtime["dock"], extended=True)
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(runtime_diagnostics=diagnostics),
            tmp_path,
            strict_layout=True,
        )
    )

    assert "dock-extended" in failures


def test_audit_reports_missing_internal_payload(tmp_path):
    _payload(tmp_path)
    (tmp_path / f"usr/share/gnome-shell/extensions/{COMMUNITY_PANEL_UUID}/extension.js").unlink()

    failures = _failures(audit_snapshot(_snapshot(), tmp_path))

    assert f"payload:{COMMUNITY_PANEL_UUID}" in failures


def test_extension_state_parser_accepts_gnome_50_and_typed_variants():
    assert _extension_state_from_output("({'state': <1.0>},)", RUNTIME_UUID) == 1
    assert _extension_state_from_output("({'state': <uint32 2>},)", RUNTIME_UUID) == 2


def test_actor_audit_rejects_a_ghost_dock(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot()
    diagnostics = dict(snapshot.runtime_diagnostics)
    diagnostics["stage"] = {"dock": [{}, {}], "taskbar": []}
    snapshot = _snapshot(runtime_diagnostics=diagnostics)

    failures = _failures(audit_snapshot(snapshot, tmp_path))

    assert "dock-stage-residue" in failures


def test_actor_audit_requires_one_dock_per_logical_monitor(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot()
    diagnostics = dict(snapshot.runtime_diagnostics)
    diagnostics["monitors"] = [
        {"index": 0, "x": 0, "y": 0, "width": 1920, "height": 1080},
        {"index": 1, "x": 1920, "y": 0, "width": 1280, "height": 1024},
    ]
    snapshot = _snapshot(runtime_diagnostics=diagnostics)

    failures = _failures(audit_snapshot(snapshot, tmp_path))

    assert failures["dock-monitor-coverage"] == "expected monitors=[0, 1], got [0]"


def test_audit_rejects_taskbar_lifecycle_ownership_drift(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot(active_layout="Hybrid")
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    taskbar = dict(runtime["taskbar"])
    taskbar["lifecycle"] = {
        "managerOwned": False,
        "globalOwned": True,
        "appActionsOwned": False,
        "interactionsOwned": False,
        "indicatorRendererOwned": False,
        "activationPending": True,
    }
    runtime["taskbar"] = taskbar
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(active_layout="Hybrid", runtime_diagnostics=diagnostics),
            tmp_path,
            strict_layout=True,
        )
    )

    assert "taskbar-manager-ownership" in failures
    assert "taskbar-app-actions-ownership" in failures
    assert "taskbar-interactions-ownership" in failures
    assert "taskbar-indicator-renderer-ownership" in failures
    assert "taskbar-activation-settled" in failures


def test_audit_rejects_null_and_duplicate_shell_stylesheets(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot()
    diagnostics = dict(snapshot.runtime_diagnostics)
    diagnostics["shellTheme"] = {
        "customStylesheets": ["file:///panel.css", "file:///panel.css", "<null>"],
    }

    failures = _failures(
        audit_snapshot(_snapshot(runtime_diagnostics=diagnostics), tmp_path)
    )

    assert "shell-theme-stylesheets" in failures
    assert "shell-theme-stylesheet-uniqueness" in failures
