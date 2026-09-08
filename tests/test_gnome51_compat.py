"""Guard RC removals used by bundled components."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1] / "usr/share/gnome-shell/extensions"


@pytest.mark.parametrize("relative", [
    "layout-switcher-runtime@communitybig.org/dock/dash.js",
    "layout-switcher-runtime@communitybig.org/dock/windowPreview.js",
    "layout-switcher-helper@communitybig.org/extension.js",
])
def test_box_layouts_use_supported_orientation(relative):
    source = (ROOT / relative).read_text()
    assert "vertical:" not in source
    assert ".set_vertical(" not in source
    assert "Clutter.Orientation.VERTICAL" in source


def test_popup_animation_versions():
    if shutil.which("node") is None:
        pytest.skip("node required")
    subprocess.run(["node", str(Path(__file__).with_name("popup_compat.mjs"))],
                   check=True, capture_output=True, text=True)
