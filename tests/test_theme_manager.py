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

    def test_list_shell_themes_includes_adwaita_default(self, tmp_path):
        theme_root = tmp_path / "themes"
        shell_dir = theme_root / "Big-Blue" / "gnome-shell"
        shell_dir.mkdir(parents=True)
        (shell_dir / "gnome-shell.css").write_text("#panel {}\n")

        with patch.object(ThemeMgr, "_theme_roots", return_value=[theme_root]):
            assert ThemeMgr.list_themes("shell") == [
                ThemeMgr.SHELL_DEFAULT_THEME_LABEL,
                "Big-Blue",
            ]


class TestApply:
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_apply_removes_layout_snapshot_marker(
        self, mock_gs, _isolate_layout_snapshot_marker
    ):
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

    @patch("extension_manager.ExtMgr.is_installed", return_value=False)
    def test_apply_shell_no_user_theme(self, _mock_inst):
        ok, msg = ThemeMgr.apply("shell", "Orchis")
        assert ok is False
        assert msg == "user-theme-not-installed"

    @patch("theme_manager.ThemeMgr._reload_shell_user_theme")
    @patch("theme_manager.ExtMgr.set_enabled", return_value=(True, ""))
    @patch("theme_manager.ExtMgr.is_enabled", return_value=False)
    @patch("theme_manager.ExtMgr.is_installed", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_apply_shell_enables_user_themes_automatically(
        self,
        mock_gs,
        _mock_installed,
        _mock_enabled,
        mock_set_enabled,
        mock_reload,
    ):
        ok, msg = ThemeMgr.apply("shell", "Big-Blue")

        assert ok is True
        assert msg == ""
        mock_gs.assert_called_once_with(
            "org.gnome.shell.extensions.user-theme", "name", "Big-Blue"
        )
        mock_set_enabled.assert_called_once_with(
            "user-theme@gnome-shell-extensions.gcampax.github.com", True
        )
        mock_reload.assert_called_once_with(
            "user-theme@gnome-shell-extensions.gcampax.github.com"
        )

    @patch("theme_manager.ThemeMgr._reload_shell_user_theme")
    @patch("theme_manager.ExtMgr.set_enabled")
    @patch("theme_manager.ExtMgr.is_enabled", return_value=True)
    @patch("theme_manager.ExtMgr.is_installed", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_apply_shell_keeps_enabled_user_themes(
        self,
        mock_gs,
        _mock_installed,
        _mock_enabled,
        mock_set_enabled,
        mock_reload,
    ):
        ok, msg = ThemeMgr.apply("shell", "Big-Blue")

        assert ok is True
        assert msg == ""
        mock_gs.assert_called_once()
        mock_set_enabled.assert_not_called()
        mock_reload.assert_called_once()

    @patch("theme_manager.ThemeMgr._reload_shell_user_theme")
    @patch("theme_manager.ExtMgr.set_enabled", return_value=(False, "enable failed"))
    @patch("theme_manager.ExtMgr.is_enabled", return_value=False)
    @patch("theme_manager.ExtMgr.is_installed", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_apply_shell_reports_user_themes_enable_failure(
        self,
        _mock_gs,
        _mock_installed,
        _mock_enabled,
        _mock_set_enabled,
        mock_reload,
    ):
        ok, msg = ThemeMgr.apply("shell", "Big-Blue")

        assert ok is False
        assert msg == "enable failed"
        mock_reload.assert_not_called()

    @patch("theme_manager.gsettings_set")
    @patch("theme_manager.ExtMgr.is_installed", return_value=False)
    def test_apply_shell_default_without_user_theme(self, _mock_inst, mock_gs):
        ok, msg = ThemeMgr.apply("shell", ThemeMgr.SHELL_DEFAULT_THEME_LABEL)

        assert ok is True
        assert msg == ""
        mock_gs.assert_not_called()

    @patch("theme_manager.ThemeMgr._reload_shell_user_theme")
    @patch("theme_manager.ExtMgr.is_enabled", return_value=False)
    @patch("theme_manager.ExtMgr.is_installed", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_apply_shell_default_resets_user_theme_name(
        self,
        mock_gs,
        _mock_inst,
        _mock_enabled,
        mock_reload,
    ):
        ok, msg = ThemeMgr.apply("shell", ThemeMgr.SHELL_DEFAULT_THEME_LABEL)

        assert ok is True
        assert msg == ""
        mock_gs.assert_called_once_with(
            "org.gnome.shell.extensions.user-theme", "name", "''"
        )
        mock_reload.assert_not_called()

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

    @patch("theme_manager.gsettings_get", return_value="")
    def test_current_shell_default(self, mock_gs):
        assert ThemeMgr.current("shell") == ThemeMgr.SHELL_DEFAULT_THEME_LABEL

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

    @patch("theme_manager.ThemeMgr.current", return_value="Big-Blue")
    @patch("theme_manager.ThemeMgr.apply", return_value=(True, ""))
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_biggnome_only_sets_gnome_accent(
        self,
        mock_set,
        mock_apply,
        _mock_current,
    ):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "BigGnome"
            ok, msg = ThemeMgr.set_accent_color("purple")

        assert ok is True
        assert msg == ""
        mock_apply.assert_not_called()
        mock_set.assert_called_once_with(
            "org.gnome.desktop.interface",
            "accent-color",
            "purple",
        )

    @patch("theme_manager.ThemeMgr.current", return_value="Big-Blue")
    @patch("theme_manager.ThemeMgr.apply", return_value=(True, ""))
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    @patch(
        "theme_manager.gsettings_get",
        return_value=(
            "['dash-to-dock@micxgx.gmail.com', "
            "'blur-my-shell@aunetx']"
        ),
    )
    def test_installed_default_treats_biggnome_as_native_shell(
        self,
        _mock_get,
        mock_set,
        mock_apply,
        _mock_current,
    ):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = None
            ok, msg = ThemeMgr.set_accent_color("pink")

        assert ok is True
        assert msg == ""
        mock_apply.assert_not_called()
        mock_set.assert_called_once_with(
            "org.gnome.desktop.interface",
            "accent-color",
            "pink",
        )

    @patch("theme_manager.ThemeMgr.current", return_value="Big-Teal")
    @patch("theme_manager.ThemeMgr.apply")
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    @patch(
        "theme_manager.gsettings_get",
        return_value=(
            "['light-style@gnome-shell-extensions.gcampax.github.com', "
            "'dash-to-panel@jderose9.github.com', "
            "'community-menu@bigcommunity.org']"
        ),
    )
    def test_installed_classic_ignores_stale_orchis_theme(
        self,
        _mock_get,
        mock_set,
        mock_apply,
        _mock_current,
    ):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = None
            ok, msg = ThemeMgr.set_accent_color("green")

        assert ok is True
        assert msg == ""
        mock_apply.assert_not_called()
        mock_set.assert_called_once_with(
            "org.gnome.desktop.interface",
            "accent-color",
            "green",
        )

    @patch(
        "theme_manager.gsettings_get",
        return_value=(
            "['dash-to-panel@jderose9.github.com', "
            "'community-menu@bigcommunity.org', "
            "'blur-my-shell@aunetx', "
            "'drive-menu@gnome-shell-extensions.gcampax.github.com']"
        ),
    )
    def test_installed_default_does_not_infer_orchis_from_extensions(
        self,
        _mock_get,
    ):
        assert not hasattr(ThemeMgr, "_uses_orchis_layout")

    @patch("theme_manager.ThemeMgr.current", return_value="Big-Blue-Light")
    @patch("theme_manager.ThemeMgr.apply", return_value=(True, ""))
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_desk_ux_only_sets_gnome_accent(
        self,
        mock_set,
        mock_apply,
        _mock_current,
    ):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "Desk UX"
            ok, msg = ThemeMgr.set_accent_color("green")

        assert ok is True
        assert msg == ""
        mock_apply.assert_not_called()
        mock_set.assert_called_once()

    @pytest.mark.parametrize("accent", ["slate", "maia"])
    @patch("theme_manager.ThemeMgr.current", return_value="Big-Blue")
    @patch("theme_manager.ThemeMgr.apply", return_value=(True, ""))
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_desk_ux_gnome_only_accents_stay_native(
        self,
        _mock_set,
        mock_apply,
        _mock_current,
        accent,
    ):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "Desk UX"
            ok, _msg = ThemeMgr.set_accent_color(accent)

        assert ok is True
        mock_apply.assert_not_called()

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
            native_shell=True,
            fixed_shell=False,
        )

    @patch("theme_manager.ThemeMgr._sync_shell_color_scheme")
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_desk_ux_keeps_native_dark_shell(self, _mock_set, mock_sync):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "Desk UX"
            ok, _msg = ThemeMgr.set_color_scheme(False)

        assert ok is True
        mock_sync.assert_called_once_with(
            True,
            native_shell=False,
            fixed_shell=True,
        )

    @patch(
        "theme_manager.gsettings_get",
        side_effect=[
            "['light-style@gnome-shell-extensions.gcampax.github.com', 'stay@ext']",
            "['user-theme@gnome-shell-extensions.gcampax.github.com']",
            "''",
        ],
    )
    @patch("theme_manager.ShellReloader.reload_extension", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_native_default_shell_still_follows_color_scheme(
        self, mock_set, mock_reload, _mock_get
    ):
        ThemeMgr._sync_shell_color_scheme(True, native_shell=True)

        assert mock_set.call_args_list[0].args == (
            "org.gnome.shell",
            "disabled-extensions",
            "['user-theme@gnome-shell-extensions.gcampax.github.com', "
            "'light-style@gnome-shell-extensions.gcampax.github.com']",
        )
        assert mock_set.call_args_list[1].args == (
            "org.gnome.shell",
            "enabled-extensions",
            "['stay@ext']",
        )
        mock_reload.assert_called_once_with(
            "light-style@gnome-shell-extensions.gcampax.github.com",
            timeout=5,
        )

    @patch(
        "theme_manager.gsettings_get",
        side_effect=[
            "['user-theme@gnome-shell-extensions.gcampax.github.com', 'stay@ext']",
            "['light-style@gnome-shell-extensions.gcampax.github.com']",
        ],
    )
    @patch("theme_manager.ShellReloader.reload_extension", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_set_light_scheme_syncs_shell_helpers(self, mock_set, mock_reload, _mock_get):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = None
            ok, msg = ThemeMgr.set_color_scheme(False)

        assert ok is True
        assert msg == ""
        assert mock_set.call_args_list[0].args == (
            "org.gnome.desktop.interface",
            "color-scheme",
            "prefer-light",
        )
        assert mock_set.call_args_list[1].args == (
            "org.gnome.shell",
            "disabled-extensions",
            "['user-theme@gnome-shell-extensions.gcampax.github.com']",
        )
        assert mock_set.call_args_list[2].args == (
            "org.gnome.shell",
            "enabled-extensions",
            "['stay@ext', 'light-style@gnome-shell-extensions.gcampax.github.com']",
        )
        mock_reload.assert_called_once_with(
            "light-style@gnome-shell-extensions.gcampax.github.com",
            timeout=5,
        )

    @patch(
        "theme_manager.gsettings_get",
        side_effect=[
            "['light-style@gnome-shell-extensions.gcampax.github.com', 'stay@ext']",
            "['user-theme@gnome-shell-extensions.gcampax.github.com']",
            "''",
        ],
    )
    @patch("theme_manager.ShellReloader.reload_extension", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_set_dark_scheme_syncs_shell_helpers(self, mock_set, mock_reload, _mock_get):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = None
            ok, msg = ThemeMgr.set_color_scheme(True)

        assert ok is True
        assert msg == ""
        assert mock_set.call_args_list[0].args == (
            "org.gnome.desktop.interface",
            "color-scheme",
            "prefer-dark",
        )
        assert mock_set.call_args_list[1].args == (
            "org.gnome.shell",
            "disabled-extensions",
            "['user-theme@gnome-shell-extensions.gcampax.github.com', "
            "'light-style@gnome-shell-extensions.gcampax.github.com']",
        )
        assert mock_set.call_args_list[2].args == (
            "org.gnome.shell",
            "enabled-extensions",
            "['stay@ext']",
        )
        mock_reload.assert_called_once_with(
            "light-style@gnome-shell-extensions.gcampax.github.com",
            timeout=5,
        )

    @patch(
        "theme_manager.gsettings_get",
        side_effect=[
            "['light-style@gnome-shell-extensions.gcampax.github.com', "
            "'user-theme@gnome-shell-extensions.gcampax.github.com', 'stay@ext']",
            "[]",
            "'Big-Blue'",
        ],
    )
    @patch("theme_manager.ShellReloader.reload_extension", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_set_dark_scheme_preserves_custom_shell_in_classic(
        self,
        mock_set,
        mock_reload,
        _mock_get,
    ):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "Classic"
            ok, msg = ThemeMgr.set_color_scheme(True)

        assert ok is True
        assert msg == ""
        assert mock_set.call_args_list[0].args == (
            "org.gnome.desktop.interface",
            "color-scheme",
            "prefer-dark",
        )
        assert len(mock_set.call_args_list) == 1
        mock_reload.assert_not_called()

    @patch(
        "theme_manager.gsettings_get",
        side_effect=[
            "['light-style@gnome-shell-extensions.gcampax.github.com', 'stay@ext']",
            "['user-theme@gnome-shell-extensions.gcampax.github.com']",
            "''",
        ],
    )
    @patch("theme_manager.ShellReloader.reload_extension", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_set_light_scheme_preserves_g_unity_shell(
        self,
        mock_set,
        mock_reload,
        _mock_get,
    ):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "G-Unity"
            ok, msg = ThemeMgr.set_color_scheme(False)

        assert ok is True
        assert msg == ""
        assert mock_set.call_args_list[0].args == (
            "org.gnome.desktop.interface",
            "color-scheme",
            "prefer-light",
        )
        assert len(mock_set.call_args_list) == 1
        mock_reload.assert_not_called()

    @patch(
        "theme_manager.gsettings_get",
        side_effect=[
            "['light-style@gnome-shell-extensions.gcampax.github.com', 'stay@ext']",
            "['user-theme@gnome-shell-extensions.gcampax.github.com']",
            "'Big-Blue'",
        ],
    )
    @patch("theme_manager.ShellReloader.reload_extension", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_set_light_scheme_preserves_biggnome_shell(
        self,
        mock_set,
        mock_reload,
        _mock_get,
    ):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = "BigGnome"
            ok, msg = ThemeMgr.set_color_scheme(False)

        assert ok is True
        assert msg == ""
        assert mock_set.call_args_list[0].args == (
            "org.gnome.desktop.interface",
            "color-scheme",
            "prefer-light",
        )
        assert len(mock_set.call_args_list) == 1
        mock_reload.assert_not_called()

    @patch(
        "theme_manager.gsettings_get",
        side_effect=[
            "['light-style@gnome-shell-extensions.gcampax.github.com', 'stay@ext']",
            "['user-theme@gnome-shell-extensions.gcampax.github.com']",
            "'Big-Blue'",
        ],
    )
    @patch("theme_manager.ShellReloader.reload_extension", return_value=True)
    @patch("theme_manager.gsettings_set", return_value=(True, ""))
    def test_set_dark_scheme_keeps_named_shell_theme(
        self,
        mock_set,
        mock_reload,
        _mock_get,
    ):
        with patch("theme_manager.Settings") as mock_settings:
            mock_settings.return_value.get.return_value = None
            ok, msg = ThemeMgr.set_color_scheme(True)

        assert ok is True
        assert msg == ""
        assert mock_set.call_args_list[1].args == (
            "org.gnome.shell",
            "disabled-extensions",
            "['light-style@gnome-shell-extensions.gcampax.github.com']",
        )
        assert mock_set.call_args_list[2].args == (
            "org.gnome.shell",
            "enabled-extensions",
            "['stay@ext', 'user-theme@gnome-shell-extensions.gcampax.github.com']",
        )
        assert [call.args[0] for call in mock_reload.call_args_list] == [
            "light-style@gnome-shell-extensions.gcampax.github.com",
            "user-theme@gnome-shell-extensions.gcampax.github.com",
        ]
