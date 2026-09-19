"""Community Menu catalog and callback ownership regressions."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("group", ["catalog", "search", "activation", "tooltip", "drag"])
def test_community_menu_lifecycle(group):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required")
    subprocess.run(
        [node, str(Path(__file__).with_name("community_menu_lifecycle.mjs")), group],
        check=True,
        timeout=30,
    )
