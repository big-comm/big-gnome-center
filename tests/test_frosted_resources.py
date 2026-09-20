"""Nested blur resources, style ownership and serialized CSS writes."""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("group", ["styles", "resources", "writer"])
def test_frosted_resources(group):
    result = subprocess.run(
        ["node", str(Path(__file__).with_name("frosted_resources.mjs")), group],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
