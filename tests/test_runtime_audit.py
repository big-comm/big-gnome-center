# SPDX-License-Identifier: MIT
"""Contracts for the read-only Shell runtime audit."""

from pathlib import Path

import runtime_audit
from runtime_audit import (
    AuditEnvironmentError,
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
        "app_active_layout": "BigGnome",
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
    if "app_active_layout" not in changes:
        values["app_active_layout"] = values["active_layout"]
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
                    "desktopBridge": {
                        "implementation": (
                            "layout-switcher-runtime"
                            if surface == "dock" else ""
                        ),
                        "ownerUuid": (
                            COMMUNITY_DOCK_UUID if surface == "dock" else ""
                        ),
                        "connected": surface == "dock",
                        "pending": False,
                        "recipientUuids": (
                            [DESKTOP_ICONS_UUID]
                            if surface == "dock"
                            and DESKTOP_ICONS_UUID in values["enabled_extensions"]
                            else []
                        ),
                    },
                    "actors": dock_actors,
                },
                "taskbar": {
                    "active": surface == "taskbar",
                    "indicator": indicator if surface == "taskbar" else "",
                    "hover": "lift" if layout == "Hybrid" else "default",
                    "opacity": panel_opacity,
                    "visibility": "always-visible",
                    "actors": taskbar_actors,
                    "window": {"normal": True},
                    "lifecycle": {
                        "managerOwned": surface == "taskbar",
                        "globalOwned": surface == "taskbar",
                        "appActionsOwned": surface == "taskbar",
                        "interactionsOwned": surface == "taskbar",
                        "indicatorRendererOwned": surface == "taskbar",
                        "indicatorRenderer": {
                            "style": indicator if surface == "taskbar" else "none"
                        },
                        "panelHost": {
                            "owned": surface == "taskbar",
                            "activePanels": len(taskbar_actors),
                        },
                        "monitorHost": {
                            "owned": surface == "taskbar",
                            "resetting": False,
                            "signalGroups": 2 if surface == "taskbar" else 0,
                            "monitorCount": 1,
                            "primaryMonitor": 0,
                            "panelMonitors": [0] if surface == "taskbar" else [],
                            "resetFailures": 0,
                        },
                        "serviceHost": {
                            "owned": surface == "taskbar",
                            "active": surface == "taskbar",
                            "overviewOwned": surface == "taskbar",
                            "overviewActive": surface == "taskbar",
                            "overviewIntegration": {
                                "implementation": (
                                    "layout-switcher-runtime"
                                    if surface == "taskbar" else ""
                                ),
                                "connected": surface == "taskbar",
                                "active": surface == "taskbar",
                                "signalsOwned": 14 if surface == "taskbar" else 0,
                                "hooksOwned": 1 if surface == "taskbar" else 0,
                                "hookLabels": (
                                    ["overview-allocation"]
                                    if surface == "taskbar" else []
                                ),
                                "allocationHookOwned": surface == "taskbar",
                                "workspaceIsolationOwned": False,
                                "configuredWorkspaceIsolation": False,
                                "hotkeysEnabled": surface == "taskbar",
                                "configuredHotkeys": surface == "taskbar",
                                "keybindingsOwned": 61 if surface == "taskbar" else 0,
                                "nativeKeybindingsSuppressed": (
                                    18 if surface == "taskbar" else 0
                                ),
                                "clickToExitOwned": surface == "taskbar",
                                "configuredClickToExit": surface == "taskbar",
                                "dashVisible": False,
                                "configuredDashVisible": False,
                                "overviewVisible": False,
                                "overviewVisibleTarget": False,
                                "overviewState": "hidden",
                                "overviewStateValue": 0,
                                "searchActive": False,
                                "appGridActive": False,
                                "hotkeyPreviewActive": False,
                                "pendingTimeouts": 0,
                                "restorationPending": surface == "taskbar",
                                "restoreConflicts": 0,
                                "lastConflict": "",
                                "entryCount": 0,
                                "exitCount": 0,
                                "stateChangeCount": 0,
                                "allocationCount": 1 if surface == "taskbar" else 0,
                                "lastState": "hidden",
                                "actorsCreated": 0,
                                "orphanActors": 0,
                            },
                            "notificationsOwned": surface == "taskbar",
                            "launcherSubscriptionOwned": surface == "taskbar",
                            "unityBusOwned": surface == "taskbar",
                            "notificationApps": 0,
                            "notificationMonitor": {
                                "implementation": (
                                    "layout-switcher-runtime"
                                    if surface == "taskbar" else ""
                                ),
                                "connected": surface == "taskbar",
                                "launcherSubscriptionOwned": surface == "taskbar",
                                "unityBusOwned": surface == "taskbar",
                                "trackedSources": 0,
                                "stateApps": 0,
                                "totalNotifications": 0,
                                "urgentApps": [],
                                "updateCount": 0,
                                "lastUpdateApp": "",
                            },
                            "desktopIconsOwned": surface == "taskbar",
                            "desktopMargins": (
                                {"0": {
                                    "top": 0,
                                    "bottom": actor_height,
                                    "left": 0,
                                    "right": 0,
                                }}
                                if surface == "taskbar" else {}
                            ),
                            "desktopMarginsPending": False,
                            "desktopBridge": {
                                "implementation": (
                                    "layout-switcher-runtime"
                                    if surface == "taskbar" else ""
                                ),
                                "ownerUuid": (
                                    COMMUNITY_PANEL_UUID
                                    if surface == "taskbar" else ""
                                ),
                                "connected": surface == "taskbar",
                                "pending": False,
                                "recipientUuids": (
                                    [DESKTOP_ICONS_UUID]
                                    if surface == "taskbar"
                                    and DESKTOP_ICONS_UUID
                                    in values["enabled_extensions"]
                                    else []
                                ),
                            },
                            "signalsOwned": surface == "taskbar",
                            "signalGroups": 7 if surface == "taskbar" else 0,
                            "keybindingOwned": surface == "taskbar",
                            "activationFailures": 0,
                        },
                        "shellHooks": {
                            "owned": surface == "taskbar",
                            "active": surface == "taskbar",
                            "restorationPending": surface == "taskbar",
                            "injectionManagerOwned": surface == "taskbar",
                            "shutdownConnected": surface == "taskbar",
                            "restoreConflicts": 0,
                            "installedHooks": (
                                [
                                    "actor-monitor-index",
                                    "panel-barriers",
                                    "hot-corners",
                                    "overview-workspace-views",
                                    "overview-primary-workspace",
                                    "box-pointer-height",
                                    "looking-glass-resize",
                                    "looking-glass-open",
                                    "message-banner-offset",
                                    "shutdown-cleanup",
                                ]
                                if surface == "taskbar" else []
                            ),
                        },
                        "statusArea": {
                            "hostOwned": surface == "taskbar",
                            "nativeMenuManagerPreserved": True,
                            "restorationPending": surface == "taskbar",
                            "adoptedRoles": (
                                ["activities", "quickSettings", "dateMenu"]
                                if surface == "taskbar" else []
                            ),
                            "roleCount": 9,
                            "orphanRoles": [],
                            "dateMenu": {"present": True, "onStage": True},
                            "quickSettings": {"present": True, "onStage": True},
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


def test_audit_ignores_desktop_window_work_area_geometry(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot(active_layout="Hybrid")
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    taskbar = dict(runtime["taskbar"])
    taskbar["window"] = {
        "normal": False,
        "maximized": True,
        "frame": {"x": 0, "y": 0, "width": 1920, "height": 1118},
        "workArea": {"x": 0, "y": 0, "width": 1920, "height": 1042},
    }
    runtime["taskbar"] = taskbar
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(active_layout="Hybrid", runtime_diagnostics=diagnostics),
            tmp_path,
        )
    )

    assert "taskbar-maximized-work-area" not in failures


def test_audit_rejects_normal_maximized_window_outside_work_area(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot(active_layout="Hybrid")
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    taskbar = dict(runtime["taskbar"])
    taskbar["window"] = {
        "normal": True,
        "maximized": True,
        "frame": {"x": 0, "y": 0, "width": 1920, "height": 1080},
        "workArea": {"x": 0, "y": 0, "width": 1920, "height": 1042},
    }
    runtime["taskbar"] = taskbar
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(
            _snapshot(active_layout="Hybrid", runtime_diagnostics=diagnostics),
            tmp_path,
        )
    )

    assert "taskbar-maximized-work-area" in failures


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


def test_audit_rejects_inherited_or_disconnected_dock_desktop_bridge(tmp_path):
    _payload(tmp_path)
    snapshot = _snapshot(enabled_extensions=(RUNTIME_UUID, HELPER_UUID, DESKTOP_ICONS_UUID))
    diagnostics = dict(snapshot.runtime_diagnostics)
    runtime = dict(diagnostics["runtime"])
    dock = dict(runtime["dock"])
    dock["desktopBridge"] = {
        "implementation": "inherited",
        "ownerUuid": "wrong@example.org",
        "connected": False,
        "pending": True,
        "recipientUuids": [],
    }
    runtime["dock"] = dock
    diagnostics["runtime"] = runtime

    failures = _failures(
        audit_snapshot(_snapshot(
            enabled_extensions=(RUNTIME_UUID, HELPER_UUID, DESKTOP_ICONS_UUID),
            runtime_diagnostics=diagnostics,
        ), tmp_path)
    )

    assert "dock-desktop-bridge-implementation" in failures
    assert "dock-desktop-bridge-owner" in failures
    assert "dock-desktop-bridge-connection" in failures
    assert "dock-desktop-bridge-settled" in failures
    assert "dock-desktop-bridge-recipient" in failures


def test_audit_reports_missing_internal_payload(tmp_path):
    _payload(tmp_path)
    (tmp_path / f"usr/share/gnome-shell/extensions/{COMMUNITY_PANEL_UUID}/extension.js").unlink()

    failures = _failures(audit_snapshot(_snapshot(), tmp_path))

    assert f"payload:{COMMUNITY_PANEL_UUID}" in failures


def test_extension_state_parser_accepts_gnome_50_and_typed_variants():
    assert _extension_state_from_output("({'state': <1.0>},)", RUNTIME_UUID) == 1
    assert _extension_state_from_output("({'state': <uint32 2>},)", RUNTIME_UUID) == 2


def test_extension_state_retries_a_transient_dbus_no_reply(monkeypatch):
    responses = iter(
        [
            AuditEnvironmentError("GDBus.Error:org.freedesktop.DBus.Error.NoReply"),
            "({'state': <1.0>},)",
        ]
    )

    def fake_run(_args):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(runtime_audit, "_run", fake_run)
    monkeypatch.setattr(runtime_audit.time, "sleep", lambda _delay: None)

    assert runtime_audit._extension_state(RUNTIME_UUID) == 1


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
        "panelHost": {"owned": False, "activePanels": 0},
        "monitorHost": {
            "owned": False,
            "resetting": True,
            "signalGroups": 0,
            "monitorCount": 0,
            "panelMonitors": [],
            "resetFailures": 1,
        },
        "serviceHost": {
            "owned": False,
            "active": False,
            "overviewOwned": False,
            "overviewActive": False,
            "overviewIntegration": {
                "implementation": "inherited",
                "connected": False,
                "active": False,
                "signalsOwned": 0,
                "hooksOwned": 0,
                "hookLabels": [],
                "allocationHookOwned": False,
                "workspaceIsolationOwned": True,
                "configuredWorkspaceIsolation": False,
                "hotkeysEnabled": False,
                "configuredHotkeys": True,
                "keybindingsOwned": 0,
                "nativeKeybindingsSuppressed": 0,
                "clickToExitOwned": False,
                "configuredClickToExit": True,
                "dashVisible": True,
                "configuredDashVisible": False,
                "overviewVisible": False,
                "overviewVisibleTarget": False,
                "overviewState": "invalid",
                "overviewStateValue": -1,
                "searchActive": False,
                "appGridActive": False,
                "hotkeyPreviewActive": True,
                "pendingTimeouts": 1,
                "restorationPending": False,
                "restoreConflicts": 1,
                "lastConflict": "external",
                "entryCount": -1,
                "exitCount": -1,
                "stateChangeCount": -1,
                "allocationCount": -1,
                "lastState": "invalid",
                "actorsCreated": 1,
                "orphanActors": 1,
            },
            "notificationsOwned": False,
            "launcherSubscriptionOwned": False,
            "unityBusOwned": False,
            "notificationApps": 1,
            "notificationMonitor": {
                "implementation": "inherited",
                "connected": False,
                "launcherSubscriptionOwned": False,
                "unityBusOwned": False,
                "trackedSources": -1,
                "stateApps": 0,
                "totalNotifications": -1,
                "urgentApps": ["invalid"],
                "updateCount": -1,
                "lastUpdateApp": "invalid",
            },
            "desktopIconsOwned": False,
            "desktopMargins": {},
            "desktopMarginsPending": True,
            "desktopBridge": {
                "implementation": "inherited",
                "ownerUuid": "wrong@example.org",
                "connected": False,
                "pending": True,
                "recipientUuids": [DESKTOP_ICONS_UUID],
            },
            "signalsOwned": False,
            "signalGroups": 0,
            "keybindingOwned": False,
            "activationFailures": 1,
        },
        "shellHooks": {
            "owned": False,
            "active": False,
            "restorationPending": False,
            "injectionManagerOwned": False,
            "shutdownConnected": False,
            "restoreConflicts": 1,
            "installedHooks": [],
        },
        "statusArea": {
            "hostOwned": False,
            "nativeMenuManagerPreserved": False,
        },
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
    assert "taskbar-panel-host-ownership" in failures
    assert "taskbar-panel-host-count" in failures
    assert "taskbar-monitor-host-ownership" in failures
    assert "taskbar-monitor-host-settled" in failures
    assert "taskbar-monitor-signals" in failures
    assert "taskbar-monitor-count" in failures
    assert "taskbar-monitor-reset-failures" in failures
    assert "taskbar-monitor-coverage" in failures
    assert "taskbar-primary-monitor" in failures
    assert "taskbar-service-host-ownership" in failures
    assert "taskbar-service-host-active" in failures
    assert "taskbar-overview-service" in failures
    assert "taskbar-overview-implementation" in failures
    assert "taskbar-overview-connection" in failures
    assert "taskbar-overview-hooks" in failures
    assert "taskbar-overview-restoration" in failures
    assert "taskbar-overview-state" in failures
    assert "taskbar-overview-residue" in failures
    assert "taskbar-notification-service" in failures
    assert "taskbar-notification-implementation" in failures
    assert "taskbar-notification-connection" in failures
    assert "taskbar-notification-telemetry" in failures
    assert "taskbar-desktop-icons-service" in failures
    assert "taskbar-desktop-bridge-implementation" in failures
    assert "taskbar-desktop-bridge-owner" in failures
    assert "taskbar-desktop-bridge-connection" in failures
    assert "taskbar-desktop-bridge-settled" in failures
    assert "taskbar-manager-signals" in failures
    assert "taskbar-manager-signal-groups" in failures
    assert "taskbar-keybinding-service" in failures
    assert "taskbar-desktop-margins-settled" in failures
    assert "taskbar-service-activation-failures" in failures
    assert "taskbar-notification-subscriptions" in failures
    assert "taskbar-desktop-margin-coverage" in failures
    assert "taskbar-desktop-margin-geometry" in failures
    assert "taskbar-desktop-bridge-recipient" in failures
    assert "taskbar-shell-hooks-ownership" in failures
    assert "taskbar-shell-hooks-active" in failures
    assert "taskbar-shell-hooks-restoration" in failures
    assert "taskbar-shell-hooks-conflicts" in failures
    assert "taskbar-shell-hooks-installed" in failures
    assert "taskbar-shell-injections" in failures
    assert "taskbar-shell-shutdown-hook" in failures
    assert "taskbar-status-host-ownership" in failures
    assert "taskbar-native-menu-manager" in failures
    assert "taskbar-activation-settled" in failures


def test_audit_rejects_application_and_runtime_layout_drift(tmp_path):
    _payload(tmp_path)
    checks = audit_snapshot(
        _snapshot(active_layout="Hybrid", app_active_layout="G-Unity"),
        tmp_path,
    )

    failures = {check.name for check in checks if check.status == "FAIL"}
    assert "application-layout-state" in failures


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
