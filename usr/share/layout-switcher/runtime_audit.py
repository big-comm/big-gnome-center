# SPDX-License-Identifier: MIT
"""Read-only audit for the accepted Layout Switcher Shell baseline."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

RUNTIME_UUID = "layout-switcher-runtime@communitybig.org"
HELPER_UUID = "layout-switcher-helper@communitybig.org"
COMMUNITY_DOCK_UUID = "community-dock@communitybig.org"
COMMUNITY_PANEL_UUID = "community-panel@communitybig.org"
LEGACY_DOCK_UUID = "dash-to-dock@micxgx.gmail.com"
LEGACY_PANEL_UUID = "dash-to-panel@jderose9.github.com"
COMMUNITY_MENU_UUID = "community-menu@communitybig.org"
DESKTOP_ICONS_UUID = "gtk4-ding@smedius.gitlab.com"

RUNTIME_SCHEMA = "org.communitybig.layout-switcher.runtime"
SHELL_SCHEMA = "org.gnome.shell"
INTERFACE_SCHEMA = "org.gnome.desktop.interface"

SURFACES = {
    "BigGnome": "dock-bottom",
    "G-Unity": "dock-left",
    "Hybrid": "taskbar-bottom",
    "Desk UX": "taskbar-bottom",
    "Classic": "taskbar-bottom-labels",
    "Minimal": "native",
}
INDICATOR_DEFAULTS = {
    "BigGnome": "desk-ux",
    "G-Unity": "dot",
    "Hybrid": "hybrid",
    "Desk UX": "desk-ux",
    "Classic": "none",
    "Minimal": "none",
}
HOVER_DEFAULTS = {
    "BigGnome": "default",
    "G-Unity": "default",
    "Hybrid": "lift",
    "Desk UX": "default",
    "Classic": "default",
    "Minimal": "default",
}
VISIBILITY_DEFAULTS = {
    "BigGnome": "intelligent",
    "G-Unity": "always-visible",
}
EXTENDED_DOCK_DEFAULTS = {
    "BigGnome": False,
    "G-Unity": True,
}
MENU_LAYOUTS = {"Hybrid", "Desk UX", "Classic"}
DESKTOP_ICON_LAYOUTS = {"Hybrid", "Classic"}
RETIRED_RUNTIME_UUIDS = {
    COMMUNITY_DOCK_UUID,
    COMMUNITY_PANEL_UUID,
    LEGACY_DOCK_UUID,
    LEGACY_PANEL_UUID,
}


class AuditEnvironmentError(RuntimeError):
    """Raised when the live session cannot provide an audit input."""


@dataclass(frozen=True)
class Snapshot:
    active_layout: str
    app_active_layout: str
    enabled_extensions: tuple[str, ...]
    runtime_state: int
    helper_state: int
    shell_version: str
    session_type: str
    color_scheme: str
    icon_theme: str
    indicator_overrides: dict[str, str]
    runtime_diagnostics: dict = field(default_factory=dict)
    payload_hashes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Check:
    status: str
    name: str
    detail: str


def _run(args: Sequence[str]) -> str:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            check=False,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AuditEnvironmentError(f"cannot run {' '.join(args)}: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise AuditEnvironmentError(f"{' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _variant_literal(raw: str):
    value = re.sub(r"^@[A-Za-z0-9{}]+\s+", "", raw.strip())
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError) as error:
        raise AuditEnvironmentError(f"invalid GSettings value: {raw}") from error


def _setting(schema: str, key: str):
    return _variant_literal(_run(("gsettings", "get", schema, key)))


def _extension_state_from_output(output: str, uuid: str) -> int:
    match = re.search(
        r"['\"]state['\"]:\s*<(?:(?:u?int32)\s+)?(\d+)(?:\.0)?>",
        output,
    )
    if not match:
        raise AuditEnvironmentError(f"cannot parse Shell state for {uuid}: {output}")
    return int(match.group(1))


def _extension_state(uuid: str) -> int:
    for attempt in range(3):
        try:
            output = _run(
                (
                    "gdbus",
                    "call",
                    "--session",
                    "--dest",
                    "org.gnome.Shell.Extensions",
                    "--object-path",
                    "/org/gnome/Shell/Extensions",
                    "--method",
                    "org.gnome.Shell.Extensions.GetExtensionInfo",
                    uuid,
                )
            )
            return _extension_state_from_output(output, uuid)
        except AuditEnvironmentError as error:
            if "NoReply" not in str(error) or attempt == 2:
                raise
            time.sleep(0.2)
    raise AssertionError("unreachable")


def _helper_json(method: str) -> dict:
    output = _run(
        (
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.Shell",
            "--object-path",
            "/org/bigcommunity/LayoutSwitcherHelper",
            "--method",
            f"org.bigcommunity.LayoutSwitcherHelper.{method}",
        )
    )
    try:
        values = ast.literal_eval(output)
        return json.loads(values[0])
    except (IndexError, TypeError, SyntaxError, ValueError, json.JSONDecodeError) as error:
        raise AuditEnvironmentError(f"cannot parse helper {method}: {output}") from error


def _tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return "missing"
    if path.is_file():
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        return digest.hexdigest()
    files = sorted(
        item for item in path.rglob("*")
        if item.is_file()
        and item.name != "gschemas.compiled"
        and item.suffix != ".pyc"
        and "__pycache__" not in item.parts
    )
    for item in files:
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _application_active_layout() -> str:
    path = Path.home() / ".config/big-appearance/settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return ""
    value = data.get("active_layout")
    return value if isinstance(value, str) else ""


def _payload_hashes(root: Path) -> dict[str, str]:
    extension_root = root / "usr/share/gnome-shell/extensions"
    hashes = {
        uuid: _tree_hash(extension_root / uuid)
        for uuid in (RUNTIME_UUID, HELPER_UUID, COMMUNITY_DOCK_UUID, COMMUNITY_PANEL_UUID)
    }
    hashes["runtime-audit-tool"] = _tree_hash(
        root / "usr/share/layout-switcher/runtime_audit.py"
    )
    hashes["runtime-baseline-tool"] = _tree_hash(
        root / "usr/share/layout-switcher/runtime_baseline.py"
    )
    return hashes


def collect_snapshot() -> Snapshot:
    enabled = _setting(SHELL_SCHEMA, "enabled-extensions")
    overrides = _setting(RUNTIME_SCHEMA, "indicator-style-overrides")
    if not isinstance(enabled, list) or not all(isinstance(item, str) for item in enabled):
        raise AuditEnvironmentError("enabled-extensions is not a string list")
    if not isinstance(overrides, dict):
        raise AuditEnvironmentError("indicator-style-overrides is not a dictionary")

    return Snapshot(
        active_layout=str(_setting(RUNTIME_SCHEMA, "active-layout")),
        app_active_layout=_application_active_layout(),
        enabled_extensions=tuple(enabled),
        runtime_state=_extension_state(RUNTIME_UUID),
        helper_state=_extension_state(HELPER_UUID),
        shell_version=_run(("gnome-shell", "--version")),
        session_type=os.environ.get("XDG_SESSION_TYPE", "unknown"),
        color_scheme=str(_setting(INTERFACE_SCHEMA, "color-scheme")),
        icon_theme=str(_setting(INTERFACE_SCHEMA, "icon-theme")),
        indicator_overrides={str(key): str(value) for key, value in overrides.items()},
        runtime_diagnostics=_helper_json("AuditRuntime"),
        payload_hashes=_payload_hashes(_default_root()),
    )


def _check(condition: bool, name: str, success: str, failure: str) -> Check:
    if condition:
        return Check("PASS", name, success)
    return Check("FAIL", name, failure)


def _runtime_checks(snapshot: Snapshot) -> list[Check]:
    diagnostics = snapshot.runtime_diagnostics
    runtime = diagnostics.get("runtime") or {}
    stage = diagnostics.get("stage") or {}
    expected = runtime.get("expected") or {}
    startup_overview = runtime.get("startupOverview") or {}
    dock = runtime.get("dock") or {}
    panel = dock.get("panel") or {}
    dock_desktop_bridge = dock.get("desktopBridge") or {}
    taskbar = runtime.get("taskbar") or {}
    taskbar_lifecycle = taskbar.get("lifecycle") or {}
    panel_host = taskbar_lifecycle.get("panelHost") or {}
    monitor_host = taskbar_lifecycle.get("monitorHost") or {}
    service_host = taskbar_lifecycle.get("serviceHost") or {}
    overview_integration = service_host.get("overviewIntegration") or {}
    notification_monitor = service_host.get("notificationMonitor") or {}
    desktop_bridge = service_host.get("desktopBridge") or {}
    shell_hooks = taskbar_lifecycle.get("shellHooks") or {}
    status_fullscreen = taskbar_lifecycle.get("statusFullscreen") or {}
    fullscreen_surface = status_fullscreen.get("fullscreenSurface") or {}
    status_area = taskbar_lifecycle.get("statusArea") or {}
    dock_actors = dock.get("actors") or []
    taskbar_actors = taskbar.get("actors") or []
    stage_docks = stage.get("dock") or []
    stage_taskbars = stage.get("taskbar") or []
    logical_monitors = diagnostics.get("monitors") or []
    shell_theme = diagnostics.get("shellTheme") or {}
    custom_stylesheets = shell_theme.get("customStylesheets") or []
    logical_monitor_indices = sorted(
        monitor.get("index") for monitor in logical_monitors
        if isinstance(monitor.get("index"), int)
    )
    surface = expected.get("surface")
    edge = expected.get("edge")
    expected_docks = surface == "dock"
    expected_taskbars = surface == "taskbar"

    checks = [
        _check(
            not diagnostics.get("runtimeError") and bool(runtime),
            "runtime-diagnostics",
            f"runtime build {runtime.get('build', 'unknown')}",
            diagnostics.get("runtimeError") or "runtime diagnostics are empty",
        ),
        _check(
            runtime.get("layout") == snapshot.active_layout,
            "runtime-layout",
            snapshot.active_layout,
            f"settings={snapshot.active_layout}, runtime={runtime.get('layout', '<empty>')}",
        ),
        _check(
            snapshot.app_active_layout == snapshot.active_layout,
            "application-layout-state",
            snapshot.active_layout,
            f"application={snapshot.app_active_layout or '<empty>'}, "
            f"runtime={snapshot.active_layout or '<empty>'}",
        ),
        _check(
            startup_overview.get("implementation") == "layout-switcher-runtime",
            "startup-overview-implementation",
            "runtime-owned",
            f"implementation={startup_overview.get('implementation')}",
        ),
        _check(
            startup_overview.get("skipRequested")
            == expected.get("skipStartupOverview"),
            "startup-overview-setting",
            f"skip={expected.get('skipStartupOverview')}",
            "expected skip="
            f"{expected.get('skipStartupOverview')}, got "
            f"{startup_overview.get('skipRequested')}",
        ),
        _check(
            not startup_overview.get("connected")
            and not startup_overview.get("restorationPending")
            and not startup_overview.get("restoreConflicts")
            and not startup_overview.get("lastConflict"),
            "startup-overview-restoration",
            "settled without conflicts",
            f"integration={startup_overview}",
        ),
        _check(
            bool(dock.get("active")) == expected_docks,
            "dock-state",
            f"active={expected_docks}",
            f"expected active={expected_docks}, got {bool(dock.get('active'))}",
        ),
        _check(
            bool(taskbar.get("active")) == expected_taskbars,
            "taskbar-state",
            f"active={expected_taskbars}",
            f"expected active={expected_taskbars}, got {bool(taskbar.get('active'))}",
        ),
        _check(
            (dock_desktop_bridge.get("implementation")
             == "layout-switcher-runtime") == expected_docks,
            "dock-desktop-bridge-implementation",
            f"runtime-owned={expected_docks}",
            "expected runtime-owned Dock desktop bridge="
            f"{expected_docks}, got "
            f"{dock_desktop_bridge.get('implementation')}",
        ),
        _check(
            (dock_desktop_bridge.get("ownerUuid") == COMMUNITY_DOCK_UUID)
            == expected_docks,
            "dock-desktop-bridge-owner",
            COMMUNITY_DOCK_UUID if expected_docks else "none",
            f"owner={dock_desktop_bridge.get('ownerUuid')}",
        ),
        _check(
            bool(dock_desktop_bridge.get("connected")) == expected_docks,
            "dock-desktop-bridge-connection",
            f"connected={expected_docks}",
            "expected Dock desktop bridge connection="
            f"{expected_docks}, got {dock_desktop_bridge.get('connected')}",
        ),
        _check(
            not dock_desktop_bridge.get("pending"),
            "dock-desktop-bridge-settled",
            "Dock desktop bridge settled",
            "Dock desktop bridge dispatch is pending",
        ),
        _check(
            bool(taskbar_lifecycle.get("managerOwned")) == expected_taskbars,
            "taskbar-manager-ownership",
            f"owned={expected_taskbars}",
            "expected manager ownership="
            f"{expected_taskbars}, got {bool(taskbar_lifecycle.get('managerOwned'))}",
        ),
        _check(
            (
                taskbar_lifecycle.get("rendererImplementation")
                == "layout-switcher-runtime"
            ) == expected_taskbars
            and taskbar_lifecycle.get("rendererModules", 0)
            == (13 if expected_taskbars else 0),
            "taskbar-renderer-implementation",
            f"runtime-owned={expected_taskbars}",
            "expected runtime-owned Taskbar renderer="
            f"{expected_taskbars}, got "
            f"{taskbar_lifecycle.get('rendererImplementation')}/"
            f"{taskbar_lifecycle.get('rendererModules', 0)} modules",
        ),
        _check(
            bool(taskbar_lifecycle.get("globalOwned")) == expected_taskbars,
            "taskbar-global-ownership",
            f"owned={expected_taskbars}",
            "expected global ownership="
            f"{expected_taskbars}, got {bool(taskbar_lifecycle.get('globalOwned'))}",
        ),
        _check(
            bool(taskbar_lifecycle.get("appActionsOwned")) == expected_taskbars,
            "taskbar-app-actions-ownership",
            f"owned={expected_taskbars}",
            "expected app-action ownership="
            f"{expected_taskbars}, got "
            f"{bool(taskbar_lifecycle.get('appActionsOwned'))}",
        ),
        _check(
            bool(taskbar_lifecycle.get("interactionsOwned")) == expected_taskbars,
            "taskbar-interactions-ownership",
            f"owned={expected_taskbars}",
            "expected interaction ownership="
            f"{expected_taskbars}, got "
            f"{bool(taskbar_lifecycle.get('interactionsOwned'))}",
        ),
        _check(
            bool(taskbar_lifecycle.get("indicatorRendererOwned")) == expected_taskbars,
            "taskbar-indicator-renderer-ownership",
            f"owned={expected_taskbars}",
            "expected indicator-renderer ownership="
            f"{expected_taskbars}, got "
            f"{bool(taskbar_lifecycle.get('indicatorRendererOwned'))}",
        ),
        _check(
            bool(panel_host.get("owned")) == expected_taskbars,
            "taskbar-panel-host-ownership",
            f"owned={expected_taskbars}",
            "expected panel-host ownership="
            f"{expected_taskbars}, got {bool(panel_host.get('owned'))}",
        ),
        _check(
            panel_host.get("activePanels", 0) == len(taskbar_actors),
            "taskbar-panel-host-count",
            f"active={len(taskbar_actors)}",
            f"host={panel_host.get('activePanels')}, actors={len(taskbar_actors)}",
        ),
        _check(
            bool(monitor_host.get("owned")) == expected_taskbars,
            "taskbar-monitor-host-ownership",
            f"owned={expected_taskbars}",
            "expected monitor-host ownership="
            f"{expected_taskbars}, got {bool(monitor_host.get('owned'))}",
        ),
        _check(
            not monitor_host.get("resetting"),
            "taskbar-monitor-host-settled",
            "monitor host settled",
            "monitor host is resetting",
        ),
        _check(
            monitor_host.get("signalGroups", 0) == (2 if expected_taskbars else 0),
            "taskbar-monitor-signals",
            f"signal groups={2 if expected_taskbars else 0}",
            "expected signal groups="
            f"{2 if expected_taskbars else 0}, got "
            f"{monitor_host.get('signalGroups')}",
        ),
        _check(
            monitor_host.get("monitorCount") == len(logical_monitors),
            "taskbar-monitor-count",
            f"logical monitors={len(logical_monitors)}",
            f"host={monitor_host.get('monitorCount')}, "
            f"logical={len(logical_monitors)}",
        ),
        _check(
            not monitor_host.get("resetFailures"),
            "taskbar-monitor-reset-failures",
            "no monitor reset failures",
            f"failures={monitor_host.get('resetFailures')}, "
            f"last={monitor_host.get('lastError')}",
        ),
        _check(
            bool(service_host.get("owned")) == expected_taskbars,
            "taskbar-service-host-ownership",
            f"owned={expected_taskbars}",
            "expected service-host ownership="
            f"{expected_taskbars}, got {bool(service_host.get('owned'))}",
        ),
        _check(
            bool(service_host.get("active")) == expected_taskbars,
            "taskbar-service-host-active",
            f"active={expected_taskbars}",
            "expected service host active="
            f"{expected_taskbars}, got {bool(service_host.get('active'))}",
        ),
        _check(
            bool(service_host.get("overviewOwned")) == expected_taskbars
            and bool(service_host.get("overviewActive")) == expected_taskbars,
            "taskbar-overview-service",
            f"owned/active={expected_taskbars}",
            f"overviewOwned={service_host.get('overviewOwned')}, "
            f"overviewActive={service_host.get('overviewActive')}",
        ),
        _check(
            (overview_integration.get("implementation")
             == "layout-switcher-runtime") == expected_taskbars,
            "taskbar-overview-implementation",
            f"runtime-owned={expected_taskbars}",
            "expected runtime-owned Overview integration="
            f"{expected_taskbars}, got "
            f"{overview_integration.get('implementation')}",
        ),
        _check(
            bool(overview_integration.get("connected")) == expected_taskbars
            and bool(overview_integration.get("active")) == expected_taskbars,
            "taskbar-overview-connection",
            f"connected/active={expected_taskbars}",
            f"integration={overview_integration}",
        ),
        _check(
            not expected_taskbars or (
                isinstance(overview_integration.get("signalsOwned"), int)
                and overview_integration.get("signalsOwned") > 0
                and isinstance(overview_integration.get("hooksOwned"), int)
                and overview_integration.get("hooksOwned") > 0
                and overview_integration.get("allocationHookOwned") is True
                and "overview-allocation"
                in overview_integration.get("hookLabels", [])
                and overview_integration.get("workspaceIsolationOwned")
                == overview_integration.get("configuredWorkspaceIsolation")
                and overview_integration.get("hotkeysEnabled")
                == overview_integration.get("configuredHotkeys")
                and overview_integration.get("clickToExitOwned")
                == overview_integration.get("configuredClickToExit")
                and overview_integration.get("dashVisible")
                == overview_integration.get("configuredDashVisible")
            ),
            "taskbar-overview-hooks",
            "Overview signals, hooks, and configured behavior are owned",
            f"integration={overview_integration}",
        ),
        _check(
            not expected_taskbars or (
                overview_integration.get("restorationPending") is True
                and not overview_integration.get("restoreConflicts")
                and not overview_integration.get("lastConflict")
            ),
            "taskbar-overview-restoration",
            "restoration pending without conflicts",
            f"integration={overview_integration}",
        ),
        _check(
            not expected_taskbars or (
                overview_integration.get("overviewState") in {
                    "hidden", "entering", "window-picker",
                    "transitioning", "app-grid",
                }
                and overview_integration.get("lastState") in {
                    "hidden", "showing", "shown", "hiding",
                }
                and all(
                    isinstance(overview_integration.get(key), int)
                    and overview_integration.get(key) >= 0
                    for key in (
                        "entryCount", "exitCount", "stateChangeCount",
                        "allocationCount",
                    )
                )
            ),
            "taskbar-overview-state",
            "Overview state and counters are coherent",
            f"integration={overview_integration}",
        ),
        _check(
            not expected_taskbars or (
                not overview_integration.get("hotkeyPreviewActive")
                and not overview_integration.get("pendingTimeouts")
                and overview_integration.get("actorsCreated") == 0
                and overview_integration.get("orphanActors") == 0
            ),
            "taskbar-overview-residue",
            "no pending Overview work or orphan actors",
            f"integration={overview_integration}",
        ),
        _check(
            bool(service_host.get("notificationsOwned")) == expected_taskbars,
            "taskbar-notification-service",
            f"owned={expected_taskbars}",
            "expected notification ownership="
            f"{expected_taskbars}, got "
            f"{bool(service_host.get('notificationsOwned'))}",
        ),
        _check(
            (notification_monitor.get("implementation")
             == "layout-switcher-runtime") == expected_taskbars,
            "taskbar-notification-implementation",
            f"runtime-owned={expected_taskbars}",
            "expected runtime-owned notification monitor="
            f"{expected_taskbars}, got "
            f"{notification_monitor.get('implementation')}",
        ),
        _check(
            bool(notification_monitor.get("connected")) == expected_taskbars,
            "taskbar-notification-connection",
            f"connected={expected_taskbars}",
            "expected notification connection="
            f"{expected_taskbars}, got "
            f"{notification_monitor.get('connected')}",
        ),
        _check(
            not expected_taskbars or (
                all(
                    isinstance(notification_monitor.get(key), int)
                    and notification_monitor.get(key) >= 0
                    for key in (
                        "trackedSources",
                        "stateApps",
                        "totalNotifications",
                        "updateCount",
                    )
                )
                and notification_monitor.get("stateApps")
                == service_host.get("notificationApps")
                and isinstance(notification_monitor.get("urgentApps"), list)
                and all(
                    isinstance(app_id, str) and app_id.endswith(".desktop")
                    for app_id in notification_monitor.get("urgentApps")
                )
                and (
                    not notification_monitor.get("lastUpdateApp")
                    or notification_monitor.get("lastUpdateApp").endswith(".desktop")
                )
            ),
            "taskbar-notification-telemetry",
            "notification telemetry is coherent",
            f"monitor={notification_monitor}, "
            f"apps={service_host.get('notificationApps')}",
        ),
        _check(
            bool(service_host.get("desktopIconsOwned")) == expected_taskbars,
            "taskbar-desktop-icons-service",
            f"owned={expected_taskbars}",
            "expected desktop-icons ownership="
            f"{expected_taskbars}, got "
            f"{bool(service_host.get('desktopIconsOwned'))}",
        ),
        _check(
            (desktop_bridge.get("implementation")
             == "layout-switcher-runtime") == expected_taskbars,
            "taskbar-desktop-bridge-implementation",
            f"runtime-owned={expected_taskbars}",
            "expected runtime-owned desktop bridge="
            f"{expected_taskbars}, got {desktop_bridge.get('implementation')}",
        ),
        _check(
            (desktop_bridge.get("ownerUuid") == COMMUNITY_PANEL_UUID)
            == expected_taskbars,
            "taskbar-desktop-bridge-owner",
            COMMUNITY_PANEL_UUID if expected_taskbars else "none",
            f"owner={desktop_bridge.get('ownerUuid')}",
        ),
        _check(
            bool(desktop_bridge.get("connected")) == expected_taskbars,
            "taskbar-desktop-bridge-connection",
            f"connected={expected_taskbars}",
            "expected desktop bridge connection="
            f"{expected_taskbars}, got {desktop_bridge.get('connected')}",
        ),
        _check(
            not desktop_bridge.get("pending"),
            "taskbar-desktop-bridge-settled",
            "desktop bridge settled",
            "desktop bridge dispatch is pending",
        ),
        _check(
            bool(service_host.get("signalsOwned")) == expected_taskbars,
            "taskbar-manager-signals",
            f"owned={expected_taskbars}",
            "expected manager-signal ownership="
            f"{expected_taskbars}, got {bool(service_host.get('signalsOwned'))}",
        ),
        _check(
            service_host.get("signalGroups", 0)
            == (9 if expected_taskbars else 0),
            "taskbar-manager-signal-groups",
            f"signal groups={9 if expected_taskbars else 0}",
            "expected signal groups="
            f"{9 if expected_taskbars else 0}, got "
            f"{service_host.get('signalGroups')}",
        ),
        _check(
            bool(service_host.get("keybindingOwned")) == expected_taskbars,
            "taskbar-keybinding-service",
            f"owned={expected_taskbars}",
            "expected keybinding ownership="
            f"{expected_taskbars}, got "
            f"{bool(service_host.get('keybindingOwned'))}",
        ),
        _check(
            not service_host.get("desktopMarginsPending"),
            "taskbar-desktop-margins-settled",
            "desktop margins settled",
            "desktop margin update is pending",
        ),
        _check(
            not service_host.get("activationFailures"),
            "taskbar-service-activation-failures",
            "no service activation failures",
            f"failures={service_host.get('activationFailures')}, "
            f"last={service_host.get('lastError')}",
        ),
        _check(
            bool(shell_hooks.get("owned")) == expected_taskbars,
            "taskbar-shell-hooks-ownership",
            f"owned={expected_taskbars}",
            "expected Shell-hook ownership="
            f"{expected_taskbars}, got {bool(shell_hooks.get('owned'))}",
        ),
        _check(
            bool(shell_hooks.get("active")) == expected_taskbars,
            "taskbar-shell-hooks-active",
            f"active={expected_taskbars}",
            "expected Shell hooks active="
            f"{expected_taskbars}, got {bool(shell_hooks.get('active'))}",
        ),
        _check(
            bool(shell_hooks.get("restorationPending")) == expected_taskbars,
            "taskbar-shell-hooks-restoration",
            f"pending={expected_taskbars}",
            "expected Shell-hook restoration pending="
            f"{expected_taskbars}, got "
            f"{bool(shell_hooks.get('restorationPending'))}",
        ),
        _check(
            not shell_hooks.get("restoreConflicts"),
            "taskbar-shell-hooks-conflicts",
            "no restoration conflicts",
            f"conflicts={shell_hooks.get('restoreConflicts')}, "
            f"last={shell_hooks.get('lastConflict')}",
        ),
        _check(
            (status_fullscreen.get("implementation")
             == "layout-switcher-runtime") == expected_taskbars,
            "taskbar-status-fullscreen-implementation",
            f"runtime-owned={expected_taskbars}",
            "expected runtime-owned status/fullscreen integration="
            f"{expected_taskbars}, got "
            f"{status_fullscreen.get('implementation')}",
        ),
        _check(
            bool(status_fullscreen.get("active")) == expected_taskbars
            and bool(status_fullscreen.get("connected")) == expected_taskbars,
            "taskbar-status-fullscreen-connection",
            f"active/connected={expected_taskbars}",
            f"integration={status_fullscreen}",
        ),
        _check(
            not expected_taskbars or (
                status_fullscreen.get("panelsOwned") == len(taskbar_actors)
                and status_fullscreen.get("styledPanels") == len(taskbar_actors)
                and status_fullscreen.get("signalsOwned") == 5
                and status_fullscreen.get("styledActors", 0) > 0
            ),
            "taskbar-status-fullscreen-ownership",
            "Panel chrome and status styles are owned",
            f"integration={status_fullscreen}, actors={len(taskbar_actors)}",
        ),
        _check(
            not expected_taskbars or (
                status_fullscreen.get("restorationPending") is True
                and not status_fullscreen.get("restoreConflicts")
                and not status_fullscreen.get("lastConflict")
            ),
            "taskbar-status-fullscreen-restoration",
            "restoration pending without conflicts",
            f"integration={status_fullscreen}",
        ),
        _check(
            not expected_taskbars or (
                not status_fullscreen.get("orphanStyles")
                and all(
                    isinstance(status_fullscreen.get(key), int)
                    and status_fullscreen.get(key) >= 0
                    for key in (
                        "fullscreenEvents", "overviewEntries", "overviewExits",
                        "visibilityUpdates", "trackMutations",
                    )
                )
                and not fullscreen_surface.get("repairPending")
                and all(
                    isinstance(fullscreen_surface.get(key), int)
                    and fullscreen_surface.get(key) >= 0
                    for key in (
                        "windowSignalsOwned", "windowActorSignalsOwned",
                        "surfaceSignalsOwned", "surfaceChildSignalsOwned",
                        "repairCount",
                    )
                )
            ),
            "taskbar-status-fullscreen-state",
            "status/fullscreen state and counters are coherent",
            f"integration={status_fullscreen}",
        ),
        _check(
            bool(status_area.get("hostOwned")) == expected_taskbars,
            "taskbar-status-host-ownership",
            f"owned={expected_taskbars}",
            "expected status-host ownership="
            f"{expected_taskbars}, got {bool(status_area.get('hostOwned'))}",
        ),
        _check(
            bool(status_area.get("nativeMenuManagerPreserved")),
            "taskbar-native-menu-manager",
            "native manager preserved",
            "native panel menu manager was replaced",
        ),
        _check(
            not taskbar_lifecycle.get("activationPending"),
            "taskbar-activation-settled",
            "no pending activation",
            "Taskbar activation is still pending",
        ),
        _check(
            bool(dock_actors) == expected_docks,
            "dock-actors",
            f"runtime actors={len(dock_actors)}",
            f"expected actors={int(expected_docks)}, got {len(dock_actors)}",
        ),
        _check(
            bool(taskbar_actors) == expected_taskbars,
            "taskbar-actors",
            f"runtime actors={len(taskbar_actors)}",
            f"expected actors={int(expected_taskbars)}, got {len(taskbar_actors)}",
        ),
        _check(
            len(stage_docks) == len(dock_actors),
            "dock-stage-residue",
            f"stage={len(stage_docks)}, runtime={len(dock_actors)}",
            f"stage={len(stage_docks)}, runtime={len(dock_actors)}",
        ),
        _check(
            len(stage_taskbars) == len(taskbar_actors),
            "taskbar-stage-residue",
            f"stage={len(stage_taskbars)}, runtime={len(taskbar_actors)}",
            f"stage={len(stage_taskbars)}, runtime={len(taskbar_actors)}",
        ),
    ]

    checks.extend(
        (
            _check(
                not status_area.get("orphanRoles"),
                "taskbar-status-actors",
                f"roles={status_area.get('roleCount', 0)}, no orphans",
                f"orphan roles={status_area.get('orphanRoles')}",
            ),
            _check(
                bool((status_area.get("dateMenu") or {}).get("present"))
                and bool((status_area.get("dateMenu") or {}).get("onStage")),
                "taskbar-date-menu",
                "native date menu on stage",
                f"dateMenu={status_area.get('dateMenu')}",
            ),
            _check(
                bool((status_area.get("quickSettings") or {}).get("present"))
                and bool((status_area.get("quickSettings") or {}).get("onStage")),
                "taskbar-quick-settings",
                "native quick settings on stage",
                f"quickSettings={status_area.get('quickSettings')}",
            ),
            _check(
                bool(status_area.get("restorationPending")) == expected_taskbars,
                "taskbar-status-restoration",
                f"pending={expected_taskbars}",
                "expected restoration pending="
                f"{expected_taskbars}, got "
                f"{bool(status_area.get('restorationPending'))}",
            ),
        )
    )

    if expected_taskbars:
        adopted_roles = set(status_area.get("adoptedRoles") or [])
        installed_hooks = set(shell_hooks.get("installedHooks") or [])
        required_hooks = {
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
        }
        taskbar_monitor_indices = sorted(
            actor.get("monitor") for actor in taskbar_actors
            if isinstance(actor.get("monitor"), int)
        )

        desktop_margin_indices = sorted(
            int(index) for index in (service_host.get("desktopMargins") or {})
            if str(index).isdigit()
        )
        desktop_margins = service_host.get("desktopMargins") or {}
        margin_sides = {
            "top": "top",
            "bottom": "bottom",
            "left": "left",
            "right": "right",
        }
        desktop_margin_geometry = all(
            (desktop_margins.get(str(actor.get("monitor")))
             or desktop_margins.get(actor.get("monitor")))
            == {side: (actor.get("outerSize") if side == margin_sides.get(
                actor.get("edge")) else 0)
                for side in margin_sides}
            for actor in taskbar_actors
        )
        checks.extend(
            (
                _check(
                    sorted(monitor_host.get("panelMonitors") or [])
                    == taskbar_monitor_indices,
                    "taskbar-monitor-coverage",
                    f"panel monitors={taskbar_monitor_indices}",
                    f"host={monitor_host.get('panelMonitors')}, "
                    f"actors={taskbar_monitor_indices}",
                ),
                _check(
                    monitor_host.get("primaryMonitor")
                    in logical_monitor_indices,
                    "taskbar-primary-monitor",
                    f"primary={monitor_host.get('primaryMonitor')}",
                    f"primary={monitor_host.get('primaryMonitor')}, "
                    f"logical={logical_monitor_indices}",
                ),
                _check(
                    required_hooks <= installed_hooks,
                    "taskbar-shell-hooks-installed",
                    f"required hooks={len(required_hooks)}",
                    f"missing hooks={sorted(required_hooks - installed_hooks)}",
                ),
                _check(
                    bool(shell_hooks.get("injectionManagerOwned")),
                    "taskbar-shell-injections",
                    "injection manager owned",
                    "Shell injection manager is not owned",
                ),
                _check(
                    bool(shell_hooks.get("shutdownConnected")),
                    "taskbar-shell-shutdown-hook",
                    "shutdown cleanup connected",
                    "shutdown cleanup is not connected",
                ),
                _check(
                    bool(service_host.get("launcherSubscriptionOwned"))
                    and bool(service_host.get("unityBusOwned")),
                    "taskbar-notification-subscriptions",
                    "launcher subscription and Unity bus owned",
                    "launcherSubscriptionOwned="
                    f"{service_host.get('launcherSubscriptionOwned')}, "
                    f"unityBusOwned={service_host.get('unityBusOwned')}",
                ),
                _check(
                    desktop_margin_indices == taskbar_monitor_indices,
                    "taskbar-desktop-margin-coverage",
                    f"margin monitors={taskbar_monitor_indices}",
                    f"margins={desktop_margin_indices}, "
                    f"actors={taskbar_monitor_indices}",
                ),
                _check(
                    desktop_margin_geometry,
                    "taskbar-desktop-margin-geometry",
                    "desktop margins match Taskbar outer geometry",
                    f"margins={desktop_margins}, actors={taskbar_actors}",
                ),
                _check(
                    (DESKTOP_ICONS_UUID
                     in desktop_bridge.get("recipientUuids", []))
                    == (DESKTOP_ICONS_UUID in snapshot.enabled_extensions),
                    "taskbar-desktop-bridge-recipient",
                    "DING recipient matches enabled extensions",
                    "recipients="
                    f"{desktop_bridge.get('recipientUuids', [])}, "
                    f"enabled={DESKTOP_ICONS_UUID in snapshot.enabled_extensions}",
                ),
                _check(
                    {"activities", "quickSettings", "dateMenu"}
                    <= adopted_roles,
                    "taskbar-native-status-adoption",
                    "activities/date/quick settings adopted",
                    f"adopted roles={sorted(adopted_roles)}",
                ),
            )
        )

    if shell_theme:
        checks.extend(
            (
                _check(
                    "<null>" not in custom_stylesheets,
                    "shell-theme-stylesheets",
                    f"valid={len(custom_stylesheets)}",
                    "Shell theme contains a null custom stylesheet",
                ),
                _check(
                    len(custom_stylesheets) == len(set(custom_stylesheets)),
                    "shell-theme-stylesheet-uniqueness",
                    "no duplicate custom stylesheets",
                    "duplicate custom stylesheets: "
                    + ", ".join(
                        sorted(
                            path
                            for path in set(custom_stylesheets)
                            if custom_stylesheets.count(path) > 1
                        )
                    ),
                ),
            )
        )

    if expected_docks:
        dock_monitor_indices = sorted(
            actor.get("monitor") for actor in dock_actors
            if isinstance(actor.get("monitor"), int)
        )
        checks.extend(
            (
                _check(
                    (DESKTOP_ICONS_UUID
                     in dock_desktop_bridge.get("recipientUuids", []))
                    == (DESKTOP_ICONS_UUID in snapshot.enabled_extensions),
                    "dock-desktop-bridge-recipient",
                    "DING recipient matches enabled extensions",
                    "recipients="
                    f"{dock_desktop_bridge.get('recipientUuids', [])}, "
                    "enabled="
                    f"{DESKTOP_ICONS_UUID in snapshot.enabled_extensions}",
                ),
                _check(
                    dock_monitor_indices == logical_monitor_indices,
                    "dock-monitor-coverage",
                    f"monitors={logical_monitor_indices}",
                    f"expected monitors={logical_monitor_indices}, got {dock_monitor_indices}",
                ),
                _check(
                    dock.get("visibility") == expected.get("visibility"),
                    "dock-visibility",
                    str(expected.get("visibility")),
                    "expected "
                    f"{expected.get('visibility')}, got {dock.get('visibility')}",
                ),
                _check(
                    dock.get("indicator") == expected.get("indicator"),
                    "dock-indicator",
                    str(expected.get("indicator")),
                    "expected "
                    f"{expected.get('indicator')}, got {dock.get('indicator')}",
                ),
                _check(
                    dock.get("hover") == expected.get("hover"),
                    "dock-hover",
                    str(expected.get("hover")),
                    f"expected {expected.get('hover')}, got {dock.get('hover')}",
                ),
                _check(
                    dock.get("opacity") == expected.get("opacity"),
                    "dock-opacity-setting",
                    f"{expected.get('opacity')}%",
                    f"expected {expected.get('opacity')}%, got {dock.get('opacity')}%",
                ),
                _check(
                    dock.get("iconSize") == expected.get("iconSize"),
                    "dock-size-setting",
                    f"{expected.get('iconSize')} px",
                    "expected "
                    f"{expected.get('iconSize')} px, got {dock.get('iconSize')} px",
                ),
                _check(
                    not panel.get("fullscreen") or not panel.get("visible"),
                    "fullscreen-panel",
                    "hidden while the focused window is fullscreen"
                    if panel.get("fullscreen")
                    else "no focused fullscreen window",
                    "panel remains visible over the focused fullscreen window",
                ),
                _check(
                    not panel.get("fullscreen") or (
                        bool(panel.get("dockVisible"))
                        and not any(panel.get("dockVisible", ()))
                    ),
                    "fullscreen-dock",
                    "dock hidden while the focused window is fullscreen"
                    if panel.get("fullscreen")
                    else "no focused fullscreen window",
                    "dock remains visible over the focused fullscreen window",
                ),
                _check(
                    dock.get("extended") == expected.get("extended"),
                    "dock-extended",
                    str(expected.get("extended")),
                    "expected "
                    f"{expected.get('extended')}, got {dock.get('extended')}",
                ),
                _check(
                    dock.get("menuSide") == expected.get("menuSide"),
                    "dock-menu-side",
                    str(expected.get("menuSide")),
                    "expected "
                    f"{expected.get('menuSide')}, got {dock.get('menuSide')}",
                ),
            )
        )
        for actor in dock_actors:
            checks.extend(
                (
                    _check(
                        expected.get("menuSide") is None
                        or actor.get("menuSide") == expected.get("menuSide"),
                        "dock-menu-side-actor",
                        str(expected.get("menuSide")),
                        "expected "
                        f"{expected.get('menuSide')}, got {actor.get('menuSide')}",
                    ),
                    _check(
                        actor.get("opacity") == expected.get("opacity"),
                        "dock-opacity",
                        f"{expected.get('opacity')}%",
                        f"expected {expected.get('opacity')}%, got "
                        f"{actor.get('opacity')}%",
                    ),
                    _check(
                        actor.get("iconSize") == expected.get("iconSize"),
                        "dock-size",
                        f"{expected.get('iconSize')} px",
                        f"expected {expected.get('iconSize')} px, got "
                        f"{actor.get('iconSize')} px",
                    ),
                )
            )

    if expected_taskbars:
        expected_visible = expected.get("visibility") == "always-visible"
        taskbar_window = taskbar.get("window") or {}
        indicator_renderer = taskbar_lifecycle.get("indicatorRenderer") or {}
        checks.append(
            _check(
                taskbar.get("indicator") == expected.get("indicator"),
                "taskbar-indicator-setting",
                str(expected.get("indicator")),
                "expected "
                f"{expected.get('indicator')}, got {taskbar.get('indicator')}",
            )
        )
        checks.append(
            _check(
                indicator_renderer.get("style") == expected.get("indicator"),
                "taskbar-indicator",
                str(expected.get("indicator")),
                "expected "
                f"{expected.get('indicator')}, got {indicator_renderer.get('style')}",
            )
        )
        checks.append(
            _check(
                taskbar.get("hover") == expected.get("hover"),
                "taskbar-hover",
                str(expected.get("hover")),
                f"expected {expected.get('hover')}, got {taskbar.get('hover')}",
            )
        )
        checks.append(
            _check(
                taskbar.get("visibility") == expected.get("visibility"),
                "taskbar-visibility",
                str(expected.get("visibility")),
                "expected "
                f"{expected.get('visibility')}, got {taskbar.get('visibility')}",
            )
        )
        checks.append(
            _check(
                taskbar.get("opacity") == expected.get("opacity"),
                "taskbar-opacity-setting",
                f"{expected.get('opacity')}%",
                f"expected {expected.get('opacity')}%, got {taskbar.get('opacity')}%",
            )
        )
        if taskbar_window.get("normal", True) and taskbar_window.get("maximized"):
            checks.append(
                _check(
                    taskbar_window.get("frame") == taskbar_window.get("workArea"),
                    "taskbar-maximized-work-area",
                    f"frame={taskbar_window.get('workArea')}",
                    f"frame={taskbar_window.get('frame')}, "
                    f"workArea={taskbar_window.get('workArea')}",
                )
            )
        for actor in taskbar_actors:
            monitor = next(
                (item for item in logical_monitors
                 if item.get("index") == actor.get("monitor")),
                {},
            )
            checks.extend(
                (
                    _check(
                        actor.get("width") == monitor.get("width") and
                        actor.get("height") == expected.get("actorHeight"),
                        "taskbar-exact-geometry",
                        f"{monitor.get('width')}x{expected.get('actorHeight')}",
                        f"got {actor.get('width')}x{actor.get('height')}",
                    ),
                    _check(
                        bool(actor.get("grouped")) != bool(expected.get("labels")),
                        "taskbar-grouping-labels",
                        "labels" if expected.get("labels") else "grouped",
                        f"grouped={actor.get('grouped')}",
                    ),
                    _check(
                        actor.get("opacity") == expected.get("opacity"),
                        "taskbar-opacity",
                        f"{expected.get('opacity')}%",
                        f"expected {expected.get('opacity')}%, got "
                        f"{actor.get('opacity')}%",
                    ),
                    _check(
                        bool(actor.get("affectsStruts")) == expected_visible,
                        "taskbar-struts",
                        f"affectsStruts={expected_visible}",
                        f"got {bool(actor.get('affectsStruts'))}",
                    ),
                )
            )
    active_actors = dock_actors if expected_docks else taskbar_actors if expected_taskbars else []
    if active_actors:
        actual_edges = {actor.get("edge") for actor in active_actors}
        checks.append(
            _check(
                actual_edges == {edge},
                "surface-edge",
                edge,
                f"expected {edge}, got {', '.join(sorted(map(str, actual_edges)))}",
            )
        )
        invalid_geometry = [
            actor for actor in active_actors
            if actor.get("width", 0) <= 0 or actor.get("height", 0) <= 0
        ]
        checks.append(
            _check(
                not invalid_geometry,
                "surface-geometry",
                "; ".join(
                    f"m{actor.get('monitor')}={actor.get('width')}x{actor.get('height')}"
                    for actor in active_actors
                ),
                f"invalid actors: {invalid_geometry}",
            )
        )
        monitors = [actor.get("monitor") for actor in active_actors]
        checks.append(
            _check(
                len(monitors) == len(set(monitors)),
                "surface-monitor-uniqueness",
                f"monitors={monitors}",
                f"duplicate actors on monitors={monitors}",
            )
        )

    return checks


def audit_snapshot(snapshot: Snapshot, root: Path, strict_layout: bool = False) -> list[Check]:
    enabled = list(snapshot.enabled_extensions)
    enabled_set = set(enabled)
    checks = [
        _check(
            len(enabled) == len(enabled_set),
            "extension-list",
            "no duplicate UUIDs",
            "enabled-extensions contains duplicate UUIDs",
        ),
        _check(
            RUNTIME_UUID in enabled_set,
            "runtime-enabled",
            RUNTIME_UUID,
            f"{RUNTIME_UUID} is not enabled",
        ),
        _check(
            HELPER_UUID in enabled_set,
            "helper-enabled",
            HELPER_UUID,
            f"{HELPER_UUID} is not enabled",
        ),
        _check(
            not (enabled_set & RETIRED_RUNTIME_UUIDS),
            "single-runtime",
            "no standalone or legacy Dock/Panel UUID is enabled",
            "unexpected runtime UUIDs: " + ", ".join(sorted(enabled_set & RETIRED_RUNTIME_UUIDS)),
        ),
        _check(
            snapshot.runtime_state == 1,
            "runtime-active",
            "Shell reports state 1",
            f"Shell reports state {snapshot.runtime_state}",
        ),
        _check(
            snapshot.helper_state == 1,
            "helper-active",
            "Shell reports state 1",
            f"Shell reports state {snapshot.helper_state}",
        ),
        _check(
            snapshot.active_layout in SURFACES,
            "active-layout",
            f"{snapshot.active_layout}: {SURFACES.get(snapshot.active_layout, 'unknown')}",
            f"unsupported layout: {snapshot.active_layout or '<empty>'}",
        ),
    ]

    extension_root = root / "usr/share/gnome-shell/extensions"
    for uuid in (RUNTIME_UUID, COMMUNITY_PANEL_UUID, HELPER_UUID):
        checks.append(
            _check(
                (extension_root / uuid / "extension.js").is_file(),
                f"payload:{uuid}",
                "extension.js present",
                f"missing {extension_root / uuid / 'extension.js'}",
            )
        )
    for uuid in (COMMUNITY_DOCK_UUID, COMMUNITY_PANEL_UUID):
        compiled = extension_root / uuid / "schemas/gschemas.compiled"
        checks.append(
            _check(
                compiled.is_file(),
                f"compiled-schema:{uuid}",
                "gschemas.compiled present",
                f"missing {compiled}",
            )
        )

    shell_major = re.search(r"\b(\d+)\b", snapshot.shell_version)
    supported_shell = bool(shell_major and shell_major.group(1) in {"50", "51"})
    checks.append(
        Check(
            "PASS" if supported_shell else "WARN",
            "shell-version",
            snapshot.shell_version,
        )
    )
    checks.append(
        Check(
            "PASS" if snapshot.session_type == "wayland" else "WARN",
            "session-type",
            snapshot.session_type,
        )
    )
    checks.append(Check("INFO", "color-scheme", snapshot.color_scheme))
    checks.append(Check("INFO", "icon-theme", snapshot.icon_theme))
    checks.extend(_runtime_checks(snapshot))
    for payload, digest in sorted(snapshot.payload_hashes.items()):
        checks.append(Check("INFO", f"hash:{payload}", digest))

    if strict_layout and snapshot.active_layout in SURFACES:
        layout = snapshot.active_layout
        menu_expected = layout in MENU_LAYOUTS
        icons_expected = layout in DESKTOP_ICON_LAYOUTS
        actual_indicator = snapshot.indicator_overrides.get(layout, INDICATOR_DEFAULTS[layout])
        actual_hover = (
            (snapshot.runtime_diagnostics.get("runtime") or {})
            .get("expected", {})
            .get("hover")
        )
        checks.extend(
            (
                _check(
                    (COMMUNITY_MENU_UUID in enabled_set) == menu_expected,
                    "layout-menu",
                    f"menu contract matches {layout}",
                    f"menu contract does not match {layout}",
                ),
                _check(
                    (DESKTOP_ICONS_UUID in enabled_set) == icons_expected,
                    "layout-desktop-icons",
                    f"desktop icon contract matches {layout}",
                    f"desktop icon contract does not match {layout}",
                ),
                _check(
                    actual_indicator == INDICATOR_DEFAULTS[layout],
                    "layout-indicator",
                    f"{actual_indicator}",
                    f"expected {INDICATOR_DEFAULTS[layout]}, got {actual_indicator}",
                ),
                _check(
                    actual_hover == HOVER_DEFAULTS[layout],
                    "layout-hover",
                    HOVER_DEFAULTS[layout],
                    f"expected {HOVER_DEFAULTS[layout]}, got {actual_hover}",
                ),
            )
        )
        if layout in VISIBILITY_DEFAULTS:
            actual_visibility = (
                (snapshot.runtime_diagnostics.get("runtime") or {})
                .get("expected", {})
                .get("visibility")
            )
            checks.append(
                _check(
                    actual_visibility == VISIBILITY_DEFAULTS[layout],
                    "layout-dock-visibility",
                    VISIBILITY_DEFAULTS[layout],
                    f"expected {VISIBILITY_DEFAULTS[layout]}, got {actual_visibility}",
                )
            )
        if layout in EXTENDED_DOCK_DEFAULTS:
            actual_extended = (
                (snapshot.runtime_diagnostics.get("runtime") or {})
                .get("expected", {})
                .get("extended")
            )
            checks.append(
                _check(
                    actual_extended == EXTENDED_DOCK_DEFAULTS[layout],
                    "layout-dock-extended",
                    str(EXTENDED_DOCK_DEFAULTS[layout]),
                    f"expected {EXTENDED_DOCK_DEFAULTS[layout]}, got {actual_extended}",
                )
            )

    return checks


def _default_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _print_human(snapshot: Snapshot, checks: list[Check]) -> None:
    print("Layout Switcher runtime audit")
    print(f"Layout: {snapshot.active_layout}")
    for check in checks:
        print(f"[{check.status:4}] {check.name}: {check.detail}")
    failures = sum(check.status == "FAIL" for check in checks)
    warnings = sum(check.status == "WARN" for check in checks)
    print(f"Summary: {failures} failure(s), {warnings} warning(s)")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-layout",
        action="store_true",
        help="validate defaults after applying an original layout",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    parser.add_argument(
        "--hashes-only",
        action="store_true",
        help="print payload hashes without requiring a graphical session",
    )
    parser.add_argument("--root", type=Path, default=_default_root(), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.hashes_only:
        print(json.dumps(_payload_hashes(args.root), indent=2, sort_keys=True))
        return 0

    try:
        snapshot = collect_snapshot()
        checks = audit_snapshot(snapshot, args.root, args.strict_layout)
    except AuditEnvironmentError as error:
        if args.json:
            print(json.dumps({"error": str(error)}, indent=2, sort_keys=True))
        else:
            print(f"[FAIL] environment: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "snapshot": asdict(snapshot),
                    "checks": [asdict(check) for check in checks],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        _print_human(snapshot, checks)
    return int(any(check.status == "FAIL" for check in checks))


if __name__ == "__main__":
    raise SystemExit(main())
