"""Exercise window blur lifecycle with Shell API doubles."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_window_blur_lifecycle():
    if shutil.which("node") is None:
        pytest.skip("node is required for the window blur harness")
    result = subprocess.run(
        ["node", str(Path(__file__).with_name("window_blur.mjs"))],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_rounded_backend_abi_guard():
    if shutil.which("node") is None:
        pytest.skip("node required")
    subprocess.run(["node", str(Path(__file__).with_name("rounded_backend.mjs"))],
                   check=True, capture_output=True, text=True)
