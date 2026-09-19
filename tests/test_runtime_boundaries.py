"""Native-boundary validation and callback ownership."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("group", ["topology", "preview", "launcher", "notifications"])
def test_runtime_boundaries(group):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required")
    subprocess.run(
        [node, str(Path(__file__).with_name("runtime_boundaries.mjs")), group],
        check=True,
        timeout=30,
    )
