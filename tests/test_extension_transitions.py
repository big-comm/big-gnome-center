# SPDX-License-Identifier: MIT
"""Run both helper entry points against deferred Shell transitions."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("script", ["extension_transitions.mjs", "helper_lifecycle.mjs"])
def test_shared_extension_transitions(script):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    subprocess.run(
        [node, str(Path(__file__).with_name(script))],
        check=True,
        capture_output=True,
        text=True,
    )
