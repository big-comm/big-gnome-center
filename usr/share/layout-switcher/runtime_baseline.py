# SPDX-License-Identifier: MIT
"""Capture the accepted Shell baseline and exercise surface transitions."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Sequence

from layout_applier import LayoutApplier
from runtime_audit import AuditEnvironmentError, audit_snapshot, collect_snapshot

LAYOUT_FILES = {
    "BigGnome": "biggnome.txt",
    "G-Unity": "g-unity.txt",
    "Hybrid": "hybrid.txt",
    "Desk UX": "desk-ux.txt",
    "Classic": "classic.txt",
    "Minimal": "minimal.txt",
}
REFERENCE_ORDER = tuple(LAYOUT_FILES)
TRANSITIONS = (
    ("BigGnome", "G-Unity", "dock-to-dock"),
    ("G-Unity", "Hybrid", "dock-to-taskbar"),
    ("Hybrid", "BigGnome", "taskbar-to-dock"),
    ("Hybrid", "Desk UX", "taskbar-to-taskbar"),
    ("Minimal", "BigGnome", "native-to-dock"),
    ("BigGnome", "Minimal", "dock-to-native"),
    ("Minimal", "Classic", "native-to-taskbar"),
    ("Classic", "Minimal", "taskbar-to-native"),
)
SCHEMES = {"light": "prefer-light", "dark": "prefer-dark"}


def _run(args: Sequence[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )


def _set_scheme(scheme: str) -> None:
    result = _run(
        ("gsettings", "set", "org.gnome.desktop.interface", "color-scheme", SCHEMES[scheme])
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"cannot set {scheme} scheme")


def _apply(layout: str, layouts_dir: Path) -> float:
    started = time.monotonic()
    ok, detail = LayoutApplier.apply(layouts_dir / LAYOUT_FILES[layout])
    if not ok:
        raise RuntimeError(f"cannot apply {layout}: {detail}")
    return time.monotonic() - started


def _settled_snapshot(root: Path, timeout: float):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        try:
            snapshot = collect_snapshot()
            checks = audit_snapshot(snapshot, root, strict_layout=True)
            latest = (snapshot, checks)
            if not any(check.status == "FAIL" for check in checks):
                return snapshot, checks
        except AuditEnvironmentError:
            pass
        time.sleep(0.4)
    if latest:
        return latest
    raise RuntimeError("runtime audit did not become available")


def _screenshot(path: Path) -> str:
    command = shutil.which("gnome-screenshot")
    if not command:
        return "gnome-screenshot not installed"
    result = _run((command, "-f", str(path)), timeout=20)
    if result.returncode:
        return result.stderr.strip() or "screenshot failed"
    return ""


def _record(
    artifact_dir: Path,
    name: str,
    layout: str,
    scheme: str,
    duration: float,
    root: Path,
    settle_timeout: float,
    screenshots: bool,
    external_capture: bool,
) -> dict:
    snapshot, checks = _settled_snapshot(root, settle_timeout)
    item_dir = artifact_dir / name
    item_dir.mkdir(parents=True, exist_ok=True)
    screenshot_error = ""
    if screenshots:
        screenshot_error = _screenshot(item_dir / "desktop.png")
    if external_capture:
        print(f"CAPTURE {name}", flush=True)
        input()
    result = {
        "name": name,
        "layout": layout,
        "scheme": scheme,
        "apply_seconds": round(duration, 3),
        "snapshot": asdict(snapshot),
        "checks": [asdict(check) for check in checks],
        "screenshot_error": screenshot_error,
        "passed": not any(check.status == "FAIL" for check in checks),
    }
    (item_dir / "audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def _reference_run(args, artifact_dir: Path, scheme: str) -> list[dict]:
    results = []
    for index, layout in enumerate(REFERENCE_ORDER, 1):
        duration = _apply(layout, args.layouts_dir)
        _set_scheme(scheme)
        time.sleep(args.scheme_settle)
        results.append(
            _record(
                artifact_dir,
                f"reference-{scheme}-{index:02d}-{LAYOUT_FILES[layout][:-4]}",
                layout,
                scheme,
                duration,
                args.root,
                args.settle_timeout,
                not args.no_screenshots,
                args.external_capture,
            )
        )
        print(f"reference {scheme}: {layout}: {'PASS' if results[-1]['passed'] else 'FAIL'}")
    return results


def _transition_run(args, artifact_dir: Path) -> list[dict]:
    results = []
    scheme = args.transition_scheme
    _set_scheme(scheme)
    for index, (source, target, contract) in enumerate(TRANSITIONS, 1):
        _apply(source, args.layouts_dir)
        _set_scheme(scheme)
        time.sleep(args.scheme_settle)
        duration = _apply(target, args.layouts_dir)
        results.append(
            _record(
                artifact_dir,
                f"transition-{index:02d}-{contract}",
                target,
                scheme,
                duration,
                args.root,
                args.settle_timeout,
                not args.no_screenshots,
                args.external_capture,
            )
        )
        print(f"transition {source} -> {target}: {'PASS' if results[-1]['passed'] else 'FAIL'}")
    return results


def _default_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("references", "transitions", "all"), default="all")
    parser.add_argument("--scheme", choices=("light", "dark", "both"), default="both")
    parser.add_argument("--transition-scheme", choices=("light", "dark"), default="dark")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--no-screenshots", action="store_true")
    parser.add_argument(
        "--external-capture",
        action="store_true",
        help="pause after each state so an external hypervisor can capture it",
    )
    parser.add_argument("--settle-timeout", type=float, default=12.0)
    parser.add_argument("--scheme-settle", type=float, default=1.0)
    parser.add_argument("--root", type=Path, default=_default_root(), help=argparse.SUPPRESS)
    parser.add_argument("--layouts-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.layouts_dir = args.layouts_dir or args.root / "usr/share/layout-switcher/layouts"
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    artifact_dir = args.artifacts or Path.home() / ".cache/layout-switcher/baseline" / stamp
    artifact_dir.mkdir(parents=True, exist_ok=True)

    results = []
    try:
        if args.mode in {"references", "all"}:
            schemes = ("light", "dark") if args.scheme == "both" else (args.scheme,)
            for scheme in schemes:
                results.extend(_reference_run(args, artifact_dir, scheme))
        if args.mode in {"transitions", "all"}:
            results.extend(_transition_run(args, artifact_dir))
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        (artifact_dir / "fatal.txt").write_text(f"{error}\n", encoding="utf-8")
        print(f"FAIL: {error}")
        return 1

    summary = {
        "created": datetime.now().astimezone().isoformat(),
        "artifact_dir": str(artifact_dir),
        "results": results,
        "passed": bool(results) and all(item["passed"] for item in results),
    }
    (artifact_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"artifacts: {artifact_dir}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
