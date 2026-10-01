# SPDX-License-Identifier: MIT
"""Run both helper entry points against deferred Shell transitions."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_shared_extension_transitions():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    subprocess.run(
        [node, str(Path(__file__).with_name("extension_transitions.mjs"))],
        check=True,
        capture_output=True,
        text=True,
    )
