# SPDX-License-Identifier: MIT
"""Headless export of bundled original layouts for installers."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

from constants import LAYOUTS
from layout_applier import LayoutApplier


def _catalog(layouts_dir: Path) -> list[dict[str, str]]:
    catalog = []
    for display_name, filename, icon, _fallback, _description in LAYOUTS:
        layout_id = Path(filename).stem
        if (layouts_dir / filename).is_file():
            catalog.append(
                {
                    "id": layout_id,
                    "display_name": display_name,
                    "filename": filename,
                    "icon": icon,
                }
            )
    return catalog


def layout_catalog(layouts_dir: Optional[Path] = None) -> list[dict[str, str]]:
    """Return installed layout metadata in the canonical UI order."""
    root = layouts_dir or Path(__file__).resolve().parent / "layouts"
    return _catalog(root)


def _shell_major() -> int:
    try:
        result = subprocess.run(
            ["gnome-shell", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    match = re.search(r"\b(\d+)(?:\.\d+)?\b", result.stdout)
    return int(match.group(1)) if match else 0


def _layout_entry(layout_id: str, layouts_dir: Path) -> dict[str, str]:
    for entry in _catalog(layouts_dir):
        if entry["id"] == layout_id:
            return entry
    raise ValueError(f"unknown layout: {layout_id}")


def prepare_layout(
    layout_id: str,
    *,
    layouts_dir: Optional[Path] = None,
    shell_major: Optional[int] = None,
    monitor_ids: Optional[Iterable[str]] = None,
) -> dict[str, object]:
    """Build the canonical factory state without touching live dconf."""
    root = layouts_dir or Path(__file__).resolve().parent / "layouts"
    entry = _layout_entry(layout_id, root)
    source = root / entry["filename"]
    data = source.read_text(encoding="utf-8")
    if not data.strip():
        raise ValueError(f"layout file is empty: {source}")

    local_monitors = set(monitor_ids or ())
    if not local_monitors:
        local_monitors = LayoutApplier._read_dtp_monitor_keys()
    if local_monitors:
        data = LayoutApplier._rewrite_dtp_keys_in_text(data, local_monitors)

    data = LayoutApplier._inject_helper_uuid(
        data,
        persistent_uuids=(),
        active_helper_uuid="",
        available_uuids=None,
    )
    data = LayoutApplier._inject_runtime_active_layout(data, layout_id)
    data = LayoutApplier._apply_original_frosted_glass_defaults(data)
    detected_shell = _shell_major() if shell_major is None else shell_major
    if detected_shell == 50:
        data = LayoutApplier._apply_gnome50_overview_default(data, layout_id)
    data = LayoutApplier._retire_blur_my_shell(data)

    return {
        "layout": layout_id,
        "display_name": entry["display_name"],
        "settings_gnome": data,
        "app_settings": {"active_layout": entry["display_name"]},
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export an original Big Gnome Center profile for installers."
    )
    parser.add_argument("layout", nargs="?", help="Layout id, for example biggnome")
    parser.add_argument("--catalog", action="store_true", help="Print layout metadata as JSON")
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Print settings and metadata as JSON",
    )
    parser.add_argument("--layouts-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--shell-major", type=int, help="Target GNOME Shell major version")
    parser.add_argument(
        "--monitor-id",
        action="append",
        default=[],
        help="Dash to Panel monitor id; repeat for multiple monitors",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    layouts_dir = args.layouts_dir or Path(__file__).resolve().parent / "layouts"
    if args.catalog:
        json.dump(layout_catalog(layouts_dir), sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    if not args.layout:
        _parser().error("layout is required unless --catalog is used")
    try:
        manifest = prepare_layout(
            args.layout,
            layouts_dir=layouts_dir,
            shell_major=args.shell_major,
            monitor_ids=args.monitor_id,
        )
    except (OSError, ValueError) as exc:
        print(f"big-gnome-center-export: {exc}", file=sys.stderr)
        return 2
    if args.manifest:
        json.dump(manifest, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(str(manifest["settings_gnome"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
