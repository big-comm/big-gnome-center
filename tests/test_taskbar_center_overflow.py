# SPDX-License-Identifier: MIT
"""Monitor-centered taskbar falls back to the free side instead of clipping."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / (
    "usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/taskbar/panel.js"
)


def test_centered_monitor_placement_scenarios():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    subprocess.run(
        [node, str(Path(__file__).with_name("taskbar_center_overflow.mjs"))],
        check=True,
        capture_output=True,
        text=True,
    )


def test_panel_allocation_uses_free_side_for_centered_taskbar():
    source = PANEL.read_text()

    assert "if (group.position == Pos.CENTERED_MONITOR) {" in source
    assert "Pos.centeredMonitorSpace(" in source
    assert "Pos.centeredMonitorStart(" in source
