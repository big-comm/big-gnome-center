"""Palette extraction across native pixel layouts."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_runtime_palette():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required")
    subprocess.run(
        [node, str(Path(__file__).with_name("runtime_palette.mjs"))],
        check=True,
        timeout=30,
    )
