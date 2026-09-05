# SPDX-License-Identifier: MIT
"""Exercise panel motion, pressure, fallback dwell, and teardown."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("harness", [
    "panel_autohide.mjs", "panel_session.mjs", "notification_positions.mjs",
])
def test_panel_autohide_behavior(harness):
    if shutil.which("node") is None:
        pytest.skip("node is required for the Shell behavior harness")
    subprocess.run(
        ["node", str(Path(__file__).with_name(harness))],
        check=True, capture_output=True, text=True,
    )
