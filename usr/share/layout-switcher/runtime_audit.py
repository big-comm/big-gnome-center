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
    dock = runtime.get("dock") or {}
    panel = dock.get("panel") or {}
    taskbar = runtime.get("taskbar") or {}
    taskbar_lifecycle = taskbar.get("lifecycle") or {}
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
            bool(taskbar_lifecycle.get("managerOwned")) == expected_taskbars,
            "taskbar-manager-ownership",
            f"owned={expected_taskbars}",
            "expected manager ownership="
            f"{expected_taskbars}, got {bool(taskbar_lifecycle.get('managerOwned'))}",
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
            )
        )

    if expected_taskbars:
        expected_visible = expected.get("visibility") == "always-visible"
        taskbar_window = taskbar.get("window") or {}
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
        if taskbar_window.get("maximized"):
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
                    (snapshot.runtime_diagnostics.get("runtime") or {})
                    .get("expected", {})
                    .get("hover")
                    == HOVER_DEFAULTS[layout],
                    "layout-hover",
                    HOVER_DEFAULTS[layout],
                    "expected "
                    f"{HOVER_DEFAULTS[layout]}, got "
                    f"{(snapshot.runtime_diagnostics.get('runtime') or {}).get('expected', {}).get('hover')}",
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
