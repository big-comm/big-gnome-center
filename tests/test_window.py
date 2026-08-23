# SPDX-License-Identifier: MIT
"""Static compatibility checks for the main GTK4 window."""

from pathlib import Path


SOURCE = Path(__file__).parents[1] / "usr/share/layout-switcher/ui/window.py"


def test_main_window_uses_gtk4_compatible_sizing_api():
    source = SOURCE.read_text()

    assert "self.set_default_size(1080, 700)" in source
    assert "self.set_size_request(860, 560)" in source
    assert "set_maximizable" not in source
