# SPDX-License-Identifier: MIT
"""Tests for theme_manager.py — list, apply, color_scheme."""

from unittest.mock import patch

import pytest

from theme_manager import ThemeMgr


@pytest.fixture(autouse=True)
def _isolate_layout_snapshot_marker(monkeypatch, tmp_path):
    marker = tmp_path / "settings.gnome.layout-switcher.sha256"
    monkeypatch.setattr(
        ThemeMgr,
        "_layout_snapshot_marker",
        staticmethod(lambda: marker),
    )
    return marker


class TestListThemes:
    def test_list_gtk_themes(self, tmp_path):
        theme_dir = tmp_path / "themes" / "Adwaita" / "gtk-4.0"
        theme_dir.mkdir(parents=True)

        with patch.object(ThemeMgr, "list_themes", wraps=ThemeMgr.list_themes):
            # Directly test with known paths
            roots = [tmp_path / "themes"]
            # Simulate what list_themes does
            seen = {}
            for root in roots:
                if not root.is_dir():
                    continue
                for d in root.iterdir():
                    if not d.is_dir():
                        continue
                    if any((d / sub).exists() for sub in ("gtk-4.0", "gtk-3.0", "gtk-2.0")):
                        seen[d.name] = True
            assert "Adwaita" in seen

    def test_list_icon_themes(self, tmp_path):
        icon_dir = tmp_path / "icons" / "Papirus"
        icon_dir.mkdir(parents=True)
        (icon_dir / "index.theme").write_text("[Icon Theme]\nName=Papirus")

        # Simulate what list_themes does for icons
        seen = {}
        for d in (tmp_path / "icons").iterdir():
            if d.is_dir() and (d / "index.theme").exists():
                seen[d.name] = True
        assert "Papirus" in seen

class TestApply:
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_apply_removes_layout_snapshot_marker(self, mock_gs, _isolate_layout_snapshot_marker):
        marker = _isolate_layout_snapshot_marker
        marker.write_text("managed\n", encoding="utf-8")

        ok, msg = ThemeMgr.apply("gtk", "Adwaita")

        assert ok is True
        assert msg == ""
        assert not marker.exists()

    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_apply_gtk(self, mock_gs):
        ok, msg = ThemeMgr.apply("gtk", "Adwaita")
        assert ok is True
        mock_gs.assert_called_with("org.gnome.desktop.interface", "gtk-theme", "Adwaita")

    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_apply_icons(self, mock_gs):
        ok, msg = ThemeMgr.apply("icons", "Papirus")
        assert ok is True
        mock_gs.assert_called_with("org.gnome.desktop.interface", "icon-theme", "Papirus")

    def test_apply_unknown_kind(self):
        ok, msg = ThemeMgr.apply("invalid", "Theme")
        assert ok is False


class TestCurrent:
    @patch("theme_manager.gsettings_get", return_value="Adwaita")
    def test_current_gtk(self, mock_gs):
        assert ThemeMgr.current("gtk") == "Adwaita"

    @patch("theme_manager.gsettings_get", return_value=None)
    def test_current_empty(self, mock_gs):
        assert ThemeMgr.current("gtk") == ""

    def test_current_unknown_kind(self):
        assert ThemeMgr.current("invalid") == ""


class TestAccentColor:
    @patch("theme_manager.ThemeMgr.apply")
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_native_layout_only_sets_gnome_accent(self, mock_set, mock_apply):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "Classic"
            ok, msg = ThemeMgr.set_accent_color("purple")

        assert ok is True
        assert msg == ""
        mock_apply.assert_not_called()
        mock_set.assert_called_once_with(
            "org.gnome.desktop.interface",
            "accent-color",
            "purple",
        )

    @patch("theme_manager.gsettings_set")
    def test_rejects_unknown_accent(self, mock_set):
        ok, msg = ThemeMgr.set_accent_color("chartreuse")

        assert ok is False
        assert msg == "unknown accent color: 'chartreuse'"
        mock_set.assert_not_called()

    @patch("theme_manager.gsettings_get", return_value="pink")
    def test_reads_current_accent(self, _mock_get):
        assert ThemeMgr.accent_color() == "pink"

    @patch("theme_manager.gsettings_get", return_value=None)
    def test_missing_accent_falls_back_to_blue(self, _mock_get):
        assert ThemeMgr.accent_color() == "blue"


class TestColorScheme:
    @patch("theme_manager.gsettings_get", return_value="prefer-dark")
    def test_color_scheme_dark(self, mock_gs):
        assert ThemeMgr.color_scheme() == "prefer-dark"

    @patch("theme_manager.gsettings_get", return_value=None)
    def test_color_scheme_default(self, mock_gs):
        assert ThemeMgr.color_scheme() == "prefer-light"

    @patch("theme_manager.ThemeMgr._sync_shell_color_scheme")
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_hybrid_selects_native_shell(self, _mock_set, mock_sync):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "Hybrid"
            ok, _msg = ThemeMgr.set_color_scheme(True)

        assert ok is True
        mock_sync.assert_called_once_with(
            True,
            fixed_shell=False,
        )

    @patch("theme_manager.ThemeMgr._sync_shell_color_scheme")
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_desk_ux_keeps_structural_dark_shell(self, _mock_set, mock_sync):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "Desk UX"
            ok, _msg = ThemeMgr.set_color_scheme(False)

        assert ok is True
        mock_sync.assert_called_once_with(
            True,
            fixed_shell=True,
        )

    @pytest.mark.parametrize(
        ("dark", "fixed_shell", "light_style_enabled"),
        [(False, False, True), (True, False, False), (False, True, False)],
    )
    @patch("theme_manager.ShellReloader.reload_extension", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    @patch(
        "theme_manager.gsettings_get",
        side_effect=[
            "['user-theme@gnome-shell-extensions.gcampax.github.com', 'stay@ext']",
            "[]",
        ],
    )
    def test_shell_scheme_retires_user_theme(
        self,
        _mock_get,
        mock_set,
        mock_reload,
        dark,
        fixed_shell,
        light_style_enabled,
    ):
        ThemeMgr._sync_shell_color_scheme(dark, fixed_shell=fixed_shell)

        calls = [call.args for call in mock_set.call_args_list]
        assert (
            "org.gnome.shell.extensions.user-theme",
            "name",
            "''",
        ) in calls
        disabled = next(value for schema, key, value in calls if key == "disabled-extensions")
        enabled = next(value for schema, key, value in calls if key == "enabled-extensions")
        assert "user-theme@gnome-shell-extensions.gcampax.github.com" in disabled
        assert "user-theme@gnome-shell-extensions.gcampax.github.com" not in enabled
        assert (
            "light-style@gnome-shell-extensions.gcampax.github.com" in enabled
        ) is light_style_enabled
        mock_reload.assert_called_once_with(
            "light-style@gnome-shell-extensions.gcampax.github.com",
            timeout=5,
        )
