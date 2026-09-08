"""Native GNOME 51 cursor adapter and legacy import boundary."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_pointer_watcher_lifecycle():
    if shutil.which("node") is None:
        pytest.skip("node required")
    subprocess.run(["node", str(Path(__file__).with_name("pointer_watcher.mjs"))],
                   check=True, capture_output=True, text=True)


def test_only_compatibility_adapter_imports_removed_module():
    root = Path(__file__).resolve().parents[1] / "usr/share/gnome-shell/extensions"
    matches = [path.relative_to(root).as_posix() for path in root.rglob("*.js")
               if "resource:///org/gnome/shell/ui/pointerWatcher.js" in path.read_text()]
    assert matches == ["layout-switcher-runtime@communitybig.org/pointerWatcher.js"]
