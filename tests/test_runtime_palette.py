"""Palette extraction across native pixel layouts."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("implementation", ["taskbar", "dock"])
def test_runtime_palette(implementation):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required")
    subprocess.run(
        [node, str(Path(__file__).with_name("runtime_palette.mjs")), implementation],
        check=True,
        timeout=30,
    )
