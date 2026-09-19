# SPDX-License-Identifier: MIT
"""Frosted extension lifecycle and asynchronous backend ownership."""

import subprocess
from pathlib import Path


def test_frosted_lifecycle():
    result = subprocess.run(
        ["node", str(Path(__file__).with_name("frosted_lifecycle.mjs"))],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "24 Frosted lifecycle scenarios passed" in result.stdout
