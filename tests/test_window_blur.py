"""Exercise window blur lifecycle with Shell API doubles."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_window_blur_lifecycle():
    if shutil.which("node") is None:
        pytest.skip("node is required for the window blur harness")
    subprocess.run(
        ["node", str(Path(__file__).with_name("window_blur.mjs"))],
        check=True, capture_output=True, text=True,
    )
