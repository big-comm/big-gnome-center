# SPDX-License-Identifier: MIT
"""Desktop icon usable-area bridge behavior."""

import subprocess
from pathlib import Path


def test_desktop_icons_usable_area_scenarios():
    result = subprocess.run(
        ["node", str(Path(__file__).with_name("desktop_icons_usable_area.mjs"))],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "3 desktop usable-area scenarios passed" in result.stdout
