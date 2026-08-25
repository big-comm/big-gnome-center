# SPDX-License-Identifier: MIT
"""Tests for layout_applier.py — apply layout via dconf load."""

from pathlib import Path
from unittest.mock import patch

import pytest

from layout_applier import _HELPER_PERSIST_UUIDS, LayoutApplier

CURRENT_DCONF = """\
[org/gnome/desktop/input-sources]
sources=[('xkb', 'br')]

[org/gnome/desktop/peripherals/touchpad]
natural-scroll=false

[org/gnome/shell]
enabled-extensions=[]
"""


def test_pamac_updates_is_not_preserved_across_layout_switches():
    assert "pamac-updates@manjaro.org" not in _HELPER_PERSIST_UUIDS


@pytest.fixture(autouse=True)
def required_helper_available():
    """Keep layout tests focused on the apply stage after helper preflight."""
    with (
        patch("layout_applier.HelperClient.ensure_available", return_value=(True, "")),
        patch("layout_applier.HelperClient.helper_version", return_value=0),
        patch("layout_applier.HelperClient._call", return_value=None),
        patch("layout_applier.gnome_shell_version", return_value=(50, 4)),
        patch("shell_reloader.run_cmd", return_value=(False, "test isolation")),
    ):
        yield


class TestLayoutApplier:
    def test_layout_big_shot_falls_back_to_installed_legacy_uuid(self):
        data = """\
[org/gnome/shell]
enabled-extensions=['big-shot@communitybig.org']
disabled-extensions=[]
"""

        migrated = LayoutApplier._migrate_layout_component_uuids(
            data,
            available_uuids={"big-shot@bigcommunity.org"},
        )

        assert "enabled-extensions=['big-shot@bigcommunity.org']" in migrated
        assert "big-shot@communitybig.org" not in migrated

    def test_menu_component_overrides_are_global_and_explicit(self):
        class FakeSettings:
            values = {
                "desktop_icons_enabled": True,
                "community_menu_enabled": False,
                "super_key_opens_menu": False,
            }

            def get(self, key, default=None):
                return self.values.get(key, default)

        data = """\
[org/gnome/shell]
enabled-extensions=['community-menu@communitybig.org']
disabled-extensions=['gtk4-ding@smedius.gitlab.com']

[org/gnome/shell/extensions/community-menu]
layout='MINT'
"""
        with patch("layout_applier.Settings", FakeSettings):
            out = LayoutApplier._apply_user_component_overrides(data)

        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])
        assert "gtk4-ding@smedius.gitlab.com" not in enabled
        assert "community-menu@communitybig.org" not in enabled
        assert "gtk4-ding@smedius.gitlab.com" in disabled
        assert "community-menu@communitybig.org" in disabled
        menu = LayoutApplier._section_key_values(
            out,
            "/org/gnome/shell/extensions/community-menu",
        )
        assert menu["super-key-opens-menu"] == "false"

    def test_absent_component_preferences_keep_layout_defaults(self):
        class FakeSettings:
            def get(self, key, default=None):
                return default

        data = """\
[org/gnome/shell]
enabled-extensions=['community-menu@communitybig.org']
"""
        with patch("layout_applier.Settings", FakeSettings):
            out = LayoutApplier._apply_user_component_overrides(data)

        assert out == data

    @pytest.mark.parametrize("layout_id", ["biggnome", "minimal", "g-unity"])
    def test_native_menu_layouts_reject_global_community_menu_override(self, layout_id):
        class FakeSettings:
            values = {
                "community_menu_enabled": True,
                "super_key_opens_menu": True,
            }

            def get(self, key, default=None):
                return self.values.get(key, default)

        data = """\
[org/gnome/shell]
enabled-extensions=['community-menu@communitybig.org', 'stay@ext']
disabled-extensions=[]
"""
        with patch("layout_applier.Settings", FakeSettings):
            out = LayoutApplier._apply_user_component_overrides(
                data,
                layout_id=layout_id,
            )

        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])
        assert "community-menu@communitybig.org" not in enabled
        assert "community-menu@communitybig.org" in disabled

    @pytest.mark.parametrize("layout_id", ["classic", "desk-ux", "hybrid"])
    def test_community_menu_layouts_accept_global_menu_override(self, layout_id):
        class FakeSettings:
            values = {"community_menu_enabled": True}

            def get(self, key, default=None):
                return self.values.get(key, default)

        data = """\
[org/gnome/shell]
enabled-extensions=['stay@ext']
disabled-extensions=['community-menu@communitybig.org']
"""
        with patch("layout_applier.Settings", FakeSettings):
            out = LayoutApplier._apply_user_component_overrides(
                data,
                layout_id=layout_id,
            )

        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])
        assert "community-menu@communitybig.org" in enabled
        assert "community-menu@communitybig.org" not in disabled

    @patch("layout_applier.time.sleep")
    @patch(
        "layout_applier.LayoutApplier._preserve_user_color_scheme",
        side_effect=lambda data, **_kwargs: data,
    )
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=True)
    @patch("layout_applier.run_cmd")
    def test_apply_full_flow(
        self,
        mock_run,
        _has,
        mock_persist,
        mock_reload_visual,
        mock_preserve_theme,
        _sleep,
        tmp_path,
    ):
        """Cobre fluxo completo: mutter gdbus probe -> dtp dconf fallback (5
        reads) -> read enabled-ext (before, vazio) -> stop watcher Qt ->
        persist -> orphan scan -> load -> read enabled-ext (after) ->
        start watcher Qt."""

        def respond(cmd, **_kwargs):
            if cmd[:2] == ["dconf", "dump"]:
                return True, CURRENT_DCONF
            if cmd[:2] == ["dconf", "read"]:
                return True, "[]"
            return True, ""

        mock_run.side_effect = respond
        layout = tmp_path / "classic.txt"
        layout.write_text("[/]\nfoo='bar'")

        ok, msg = LayoutApplier.apply(layout)
        assert ok is True

        # 1 mutter gdbus probe + 5 dconf reads (dtp fallback) + 1 read
        # enabled-extensions (before) + stop watcher + dconf dump scan +
        # staged Shell load + main load + 1 read enabled-extensions (after) +
        # start watcher = 13.
        # (The light-mode icon/label adjusts early-return: this layout text
        # carries no icon-theme / dash-to-panel label keys.)
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert mock_run.call_count == 13, "\n".join(map(str, calls))
        # 1: gdbus probe to mutter for monitor IDs
        assert calls[0][0] == "gdbus"
        assert "Mutter.DisplayConfig" in calls[0][4]
        # 2-6: dtp monitor-key probes (fallback because mutter returned empty)
        assert all(c[:2] == ["dconf", "read"] for c in calls[1:6])
        assert all("dash-to-panel" in c[2] for c in calls[1:6])
        # 7: enabled-extensions before
        assert calls[6] == ["dconf", "read", "/org/gnome/shell/enabled-extensions"]
        # 8: stop Qt theme watcher
        assert calls[7][:3] == ["systemctl", "--user", "stop"]
        # 9-11: orphan scan + staged Shell load + main layout load
        assert calls[8] == ["dconf", "dump", "/"]
        assert calls[9] == ["dconf", "load", "/"]
        assert calls[10] == ["dconf", "load", "/"]
        # 12: enabled-extensions after
        assert calls[11] == ["dconf", "read", "/org/gnome/shell/enabled-extensions"]
        # 13: start Qt theme watcher
        assert calls[12][:3] == ["systemctl", "--user", "start"]
        mock_preserve_theme.assert_called_once()
        mock_persist.assert_called_once()
        mock_reload_visual.assert_not_called()

    @patch("layout_applier.time.sleep")
    @patch(
        "layout_applier.LayoutApplier._preserve_user_color_scheme",
        side_effect=lambda data, **_kwargs: data,
    )
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd")
    def test_apply_without_sync_service(
        self,
        mock_run,
        _has,
        mock_persist,
        mock_reload_visual,
        mock_preserve_theme,
        _sleep,
        tmp_path,
    ):
        """Quando o watcher Qt nao existe, systemctl e pulado."""

        def respond(cmd, **_kwargs):
            if cmd[:2] == ["dconf", "dump"]:
                return True, CURRENT_DCONF
            if cmd[:2] == ["dconf", "read"]:
                return True, "[]"
            return True, ""

        mock_run.side_effect = respond
        layout = tmp_path / "x.txt"
        layout.write_text("[/]\nx=1")

        ok, _ = LayoutApplier.apply(layout)
        assert ok is True
        # 1 gdbus mutter probe + 5 dtp dconf reads + 1 enabled-ext read
        # (before) + dconf dump scan + staged Shell load + main load + 1
        # enabled-ext read (after) = 11.
        # No systemctl stop/start (watcher ausente), no per-UUID disables.
        assert mock_run.call_count == 11
        # 1st: gdbus mutter probe
        assert mock_run.call_args_list[0].args[0][0] == "gdbus"
        # 2nd-6th: reads de dash-to-panel
        assert all(c.args[0][:2] == ["dconf", "read"] for c in mock_run.call_args_list[1:6])
        # 7th: enabled-extensions before
        assert mock_run.call_args_list[6].args[0] == [
            "dconf",
            "read",
            "/org/gnome/shell/enabled-extensions",
        ]
        # 8th-10th: orphan scan + staged Shell load + main layout load
        assert mock_run.call_args_list[7].args[0] == ["dconf", "dump", "/"]
        assert mock_run.call_args_list[8].args[0] == ["dconf", "load", "/"]
        assert mock_run.call_args_list[9].args[0] == ["dconf", "load", "/"]
        # 11th: enabled-extensions after
        assert mock_run.call_args_list[10].args[0] == [
            "dconf",
            "read",
            "/org/gnome/shell/enabled-extensions",
        ]
        mock_preserve_theme.assert_called_once()
        mock_persist.assert_called_once()
        mock_reload_visual.assert_not_called()

    def test_apply_nonexistent_file(self):
        ok, msg = LayoutApplier.apply(Path("/nonexistent/layout.txt"))
        assert ok is False
        assert "not found" in msg

    def test_apply_none_path(self):
        ok, msg = LayoutApplier.apply(None)
        assert ok is False

    def test_apply_empty_file(self, tmp_path):
        layout = tmp_path / "empty.txt"
        layout.write_text("")
        ok, msg = LayoutApplier.apply(layout)
        assert ok is False
        assert "empty" in msg.lower()

    @patch("layout_applier.time.sleep")
    @patch(
        "layout_applier.LayoutApplier._preserve_user_color_scheme",
        side_effect=lambda data, **_kwargs: data,
    )
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=True)
    @patch("layout_applier.run_cmd")
    def test_apply_load_failure_still_cleans_up(
        self,
        mock_run,
        _has,
        mock_persist,
        mock_reload_visual,
        _preserve_theme,
        _sleep,
        tmp_path,
    ):
        """Se o dconf load falhar: watcher Qt reinicia e shell nao recarrega."""
        # 1 mutter gdbus probe (returns empty so dconf fallback runs),
        # 5 dtp dconf reads, read-before (vazio -> []), stop OK, orphan scan
        # OK, load FAIL, start OK (finally). Sem read-after.
        mock_run.side_effect = [
            (True, ""),  # gdbus mutter probe
            (True, ""),  # dtp probe 1
            (True, ""),  # dtp probe 2
            (True, ""),  # dtp probe 3
            (True, ""),  # dtp probe 4
            (True, ""),  # dtp probe 5
            (True, "[]"),  # read enabled-extensions (before)
            (True, ""),  # systemctl stop watcher
            (True, ""),  # dconf dump orphan scan
            (False, "dconf error"),  # layout dconf load FAILS
            (True, ""),  # systemctl start watcher (finally)
        ]
        layout = tmp_path / "bad.txt"
        layout.write_text("[/]\ndata=true")

        ok, msg = LayoutApplier.apply(layout)
        assert ok is False
        mock_persist.assert_called_once()
        mock_reload_visual.assert_not_called()
        # Garantir que a ultima chamada foi start do watcher (finally rodou)
        assert mock_run.call_args_list[-1].args[0][:3] == [
            "systemctl",
            "--user",
            "start",
        ]

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.ShellReloader.list_extensions_state", return_value={})
    @patch(
        "layout_applier.ShellReloader.enable_extension_dbus",
        return_value=(False, "timed out after 2s"),
    )
    def test_disable_extensions_stops_after_repeated_dbus_timeouts(
        self,
        mock_disable,
        _mock_states,
        mock_sleep,
    ):
        """Repeated Shell DBus timeouts must not stall the apply for minutes."""
        ok = LayoutApplier._disable_extensions_in_order(
            ["z@ext", "a@ext", "m@ext", "b@ext", "c@ext"]
        )

        assert ok is False
        assert mock_disable.call_count == LayoutApplier._MAX_DISABLE_DBUS_TIMEOUTS
        assert mock_sleep.call_count == 0
        assert all(
            call.kwargs["timeout"] == LayoutApplier._SHELL_DBUS_TIMEOUT_SEC
            for call in mock_disable.call_args_list
        )

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.ShellReloader.get_extension_state", return_value=2)
    @patch(
        "layout_applier.ShellReloader.enable_extension_dbus",
        return_value=(True, ""),
    )
    @patch(
        "layout_applier.ShellReloader.list_extensions_state",
        return_value={"err@ext": 3, "live@ext": 1},
    )
    def test_disable_extensions_skips_non_live_shell_state(
        self,
        _mock_states,
        mock_disable,
        _mock_get_state,
        mock_sleep,
    ):
        """Do not call DisableExtension for UUIDs Shell already disabled/errored."""
        ok = LayoutApplier._disable_extensions_in_order(
            ["err@ext", "live@ext"],
            sort=False,
        )

        assert ok is True
        mock_disable.assert_called_once_with(
            "live@ext",
            enable=False,
            timeout=LayoutApplier._SHELL_DBUS_TIMEOUT_SEC,
        )
        mock_sleep.assert_called_once()

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.ShellReloader.get_extension_state", side_effect=[1, 2])
    @patch(
        "layout_applier.ShellReloader.enable_extension_dbus",
        return_value=(True, ""),
    )
    @patch(
        "layout_applier.ShellReloader.list_extensions_state",
        return_value={"panel@ext": 1},
    )
    def test_disable_extensions_waits_until_shell_state_not_live(
        self,
        _mock_states,
        _mock_disable,
        mock_get_state,
        mock_sleep,
    ):
        """Fragile Shell actors must finish disabling before the load continues."""
        ok = LayoutApplier._disable_extensions_in_order(["panel@ext"], sort=False)

        assert ok is True
        assert mock_get_state.call_count == 2
        assert mock_sleep.call_count == 2

    def test_leaving_extensions_disable_newest_first(self):
        """Leaving extensions follow reverse active order to avoid Shell rebase."""
        before = [
            "older@ext",
            "arcmenu@arcmenu.com",
            "community-panel@communitybig.org",
            "copyous@boerdereinar.dev",
        ]
        leaving = {
            "community-panel@communitybig.org",
            "arcmenu@arcmenu.com",
            "unknown@ext",
        }

        ordered = LayoutApplier._leaving_extensions_in_disable_order(before, leaving)

        assert ordered == [
            "community-panel@communitybig.org",
            "arcmenu@arcmenu.com",
            "unknown@ext",
        ]

    def test_split_shell_extension_switch_keys_loads_extensions_last(self):
        """Extension enable lists are loaded after extension settings."""
        data = (
            "[org/gnome/shell]\n"
            "favorite-apps=['a.desktop']\n"
            "enabled-extensions=['community-panel@communitybig.org']\n"
            "disabled-extensions=['dash-to-dock@micxgx.gmail.com']\n"
            "\n"
            "[org/gnome/shell/extensions/dash-to-panel]\n"
            "panel-sizes='{\"monitor\":42}'\n"
        )

        settings_data, switch_data = LayoutApplier._split_shell_extension_switch_keys(data)

        assert "favorite-apps=['a.desktop']" in settings_data
        assert "panel-sizes" in settings_data
        assert "enabled-extensions" not in settings_data
        assert "disabled-extensions" not in settings_data
        assert switch_data == (
            "[org/gnome/shell]\n"
            "disabled-extensions=['dash-to-dock@micxgx.gmail.com']\n"
            "enabled-extensions=['community-panel@communitybig.org']\n"
        )

    def test_replace_existing_dconf_key_does_not_append_duplicate_section(self):
        """Replacing an early section must not append the same section at EOF."""
        data = (
            "[org/gnome/desktop/interface]\n"
            "gtk-theme='adw-gtk3'\n"
            "\n"
            "[org/gtk/settings/file-chooser]\n"
            "show-hidden=false\n"
        )

        out = LayoutApplier._replace_or_add_dconf_key(
            data,
            "/org/gnome/desktop/interface",
            "gtk-theme",
            "'adw-gtk3-dark'",
        )

        assert out.count("[org/gnome/desktop/interface]") == 1
        assert "gtk-theme='adw-gtk3-dark'" in out
        assert out.rstrip().endswith("show-hidden=false")

    @patch("layout_applier.run_cmd")
    def test_preserve_user_dark_color_scheme(self, mock_run):
        """Original layouts keep user dark mode but restore factory themes."""
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/desktop/interface]\n"
            "gtk-theme='adw-gtk3'\n"
            "icon-theme='bigicons-papient'\n"
            "\n"
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{user_theme}']\n"
            f"enabled-extensions=['{light_style}', 'community-panel@communitybig.org']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name=''\n"
        )
        mock_run.side_effect = [
            (True, "'prefer-dark'"),
        ]

        out = LayoutApplier._preserve_user_color_scheme(data)

        assert "color-scheme='prefer-dark'" in out
        assert "gtk-theme='adw-gtk3'\n" in out
        assert "icon-theme='bigicons-papient'\n" in out
        assert "name=''" in out
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])
        assert user_theme not in enabled
        assert light_style not in enabled
        assert light_style in disabled
        assert user_theme in disabled

    @patch.object(LayoutApplier, "_current_color_scheme_value", return_value="'prefer-dark'")
    def test_classic_dark_uses_dark_papient_variant(self, _mock_scheme):
        data = "[org/gnome/desktop/interface]\nicon-theme='bigicons-papient-light'\n"

        out = LayoutApplier._adjust_icon_theme_for_scheme(data)

        assert "icon-theme='bigicons-papient-dark'" in out

    @patch.object(LayoutApplier, "_current_color_scheme_value", return_value="'default'")
    def test_classic_light_uses_light_papient_variant(self, _mock_scheme):
        data = "[org/gnome/desktop/interface]\nicon-theme='bigicons-papient-dark'\n"

        out = LayoutApplier._adjust_icon_theme_for_scheme(data, light_variant=True)

        assert "icon-theme='bigicons-papient-light'" in out

    @patch.object(LayoutApplier, "_current_color_scheme_value", return_value="'default'")
    def test_other_light_layout_uses_unsuffixed_papient_variant(self, _mock_scheme):
        data = "[org/gnome/desktop/interface]\nicon-theme='bigicons-papient-dark'\n"

        out = LayoutApplier._adjust_icon_theme_for_scheme(data)

        assert "icon-theme='bigicons-papient'" in out

    def test_light_mode_selects_light_adw_gtk3_variant(self):
        data = (
            "[org/gnome/desktop/interface]\n"
            "color-scheme='default'\n"
            "gtk-theme='adw-gtk3-dark'\n"
        )

        out = LayoutApplier._adjust_gtk_theme_for_scheme(data)

        assert "gtk-theme='adw-gtk3'" in out

    def test_dark_mode_selects_dark_adw_gtk3_variant(self):
        data = (
            "[org/gnome/desktop/interface]\n"
            "color-scheme='prefer-dark'\n"
            "gtk-theme='adw-gtk3'\n"
        )

        out = LayoutApplier._adjust_gtk_theme_for_scheme(data)

        assert "gtk-theme='adw-gtk3-dark'" in out

    def test_desk_ux_uses_native_dark_shell(self):
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/desktop/interface]\n"
            "icon-theme='bigicons-papient-dark'\n"
            "\n"
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{user_theme}']\n"
            f"enabled-extensions=['{light_style}', 'stay@ext']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name=''\n"
        )

        out = LayoutApplier._rewrite_shell_theme_mode(
            data,
            prefer_dark=True,
        )
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])

        assert "name=''" in out
        assert user_theme not in enabled
        assert light_style not in enabled
        assert light_style in disabled
        assert user_theme in disabled

    @patch("layout_applier.run_cmd")
    def test_preserve_user_light_color_scheme(self, mock_run):
        """Original layouts keep user light mode but restore factory themes."""
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/desktop/interface]\n"
            "color-scheme='prefer-dark'\n"
            "gtk-theme='adw-gtk3-dark'\n"
            "icon-theme='bigicons-papient-dark'\n"
            "\n"
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{light_style}']\n"
            f"enabled-extensions=['{user_theme}', 'dash-to-dock@micxgx.gmail.com']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name='Big-Blue'\n"
        )
        mock_run.side_effect = [
            (True, "'prefer-light'"),
        ]

        out = LayoutApplier._preserve_user_color_scheme(data)

        assert "color-scheme='prefer-light'" in out
        assert "gtk-theme='adw-gtk3-dark'" in out
        assert "icon-theme='bigicons-papient-dark'" in out
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])
        assert light_style in enabled
        assert user_theme not in enabled
        assert user_theme in disabled
        assert light_style not in disabled
        assert "name='Big-Blue'" in out

    @patch("layout_applier.run_cmd")
    def test_preserve_user_color_scheme_uses_effective_gsettings(self, mock_run):
        """Preserve light/dark even when dconf has no explicit override."""
        data = (
            "[org/gnome/desktop/interface]\ncolor-scheme='prefer-dark'\ngtk-theme='adw-gtk3-dark'\n"
        )
        mock_run.side_effect = [
            (True, ""),  # dconf read: default/unset
            (True, "'prefer-light'"),  # gsettings effective value
        ]

        out = LayoutApplier._preserve_user_color_scheme(data)

        assert "color-scheme='prefer-light'" in out
        assert "gtk-theme='adw-gtk3-dark'" in out
        assert mock_run.call_args_list[0].args[0] == [
            "dconf",
            "read",
            "/org/gnome/desktop/interface/color-scheme",
        ]
        assert mock_run.call_args_list[1].args[0] == [
            "gsettings",
            "get",
            "org.gnome.desktop.interface",
            "color-scheme",
        ]

    @patch.object(LayoutApplier, "_current_color_scheme_value", return_value="'prefer-dark'")
    def test_preserve_color_scheme_keeps_original_accent(self, _mock_scheme):
        data = "[org/gnome/desktop/interface]\naccent-color='blue'\ncolor-scheme='default'\n"

        out = LayoutApplier._preserve_user_color_scheme(data)

        assert "accent-color='blue'" in out
        assert "color-scheme='prefer-dark'" in out

    @patch("layout_applier.run_cmd")
    def test_g_unity_preserves_light_apps_and_dark_shell(self, mock_run):
        """G-Unity keeps light apps without replacing its Shell CSS."""
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/desktop/interface]\n"
            "color-scheme='prefer-dark'\n"
            "gtk-theme='adw-gtk3-dark'\n"
            "\n"
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{light_style}']\n"
            f"enabled-extensions=['{user_theme}', 'dash-to-dock@micxgx.gmail.com']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name=''\n"
        )
        mock_run.return_value = (True, "'prefer-light'")

        out = LayoutApplier._preserve_user_color_scheme(
            data,
            force_shell_dark=True,
        )

        assert "color-scheme='default'" in out
        assert "gtk-theme='adw-gtk3-dark'" in out
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])
        assert user_theme not in enabled
        assert light_style not in enabled
        assert light_style in disabled
        assert user_theme in disabled

    @patch("layout_applier.run_cmd")
    def test_preserve_user_dark_color_scheme_keeps_named_shell_theme(self, mock_run):
        """Named Shell themes still use user-theme in dark mode."""
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/desktop/interface]\n"
            "gtk-theme='adw-gtk3'\n"
            "\n"
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{user_theme}']\n"
            f"enabled-extensions=['{light_style}']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name='Big-Blue'\n"
        )
        mock_run.return_value = (True, "'prefer-dark'")

        out = LayoutApplier._preserve_user_color_scheme(data)

        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])
        assert user_theme in enabled
        assert light_style not in enabled
        assert light_style in disabled
        assert user_theme not in disabled
        assert "name='Big-Blue'" in out

    @patch("layout_applier.run_cmd")
    def test_biggnome_preserves_light_apps_and_dark_shell(self, mock_run):
        """BigGnome keeps light apps and its named dark Shell theme."""
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/desktop/interface]\n"
            "color-scheme='prefer-dark'\n"
            "gtk-theme='adw-gtk3-dark'\n"
            "\n"
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{light_style}']\n"
            f"enabled-extensions=['{user_theme}', 'dash-to-dock@micxgx.gmail.com']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name='Big-Blue'\n"
        )
        mock_run.return_value = (True, "'prefer-light'")

        out = LayoutApplier._preserve_user_color_scheme(
            data,
            force_shell_dark=True,
        )

        assert "color-scheme='default'" in out
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])
        assert user_theme in enabled
        assert light_style not in enabled
        assert light_style in disabled
        assert user_theme not in disabled

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.ShellReloader.reload_extension", return_value=True)
    def test_reload_visual_extensions_skips_fragile_or_slow_extensions(
        self,
        mock_reload,
        _mock_sleep,
    ):
        """Avoid ReloadExtension for extensions that error or block."""
        LayoutApplier._reload_visual_extensions(
            [
                "arcmenu@arcmenu.com",
                "community-panel@communitybig.org",
                "dash-to-dock@micxgx.gmail.com",
                "big-shot@bigcommunity.org",
            ]
        )

        mock_reload.assert_not_called()

    @patch(
        "layout_applier.LayoutApplier._preserve_layout_independent_settings",
        side_effect=lambda data: data,
    )
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch("layout_applier.LayoutApplier._enabled_extensions", return_value={"after@ext"})
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=False)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_skips_remaining_shell_dbus_after_breaker(
        self,
        mock_run,
        _has,
        mock_persist,
        _reset,
        mock_disable,
        _enabled,
        mock_reload,
        _preserve,
    ):
        """Once Shell DBus times out repeatedly, finish via dconf without more DBus."""
        data = "[org/gnome/shell]\nenabled-extensions=['stay@ext']\n"

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=["leave@ext", "stay@ext"],
        )

        assert ok is True
        assert mock_disable.call_count == 1
        assert mock_disable.call_args.args[0] == ["leave@ext"]
        assert mock_disable.call_args.kwargs == {"sort": False}
        mock_persist.assert_called_once()
        mock_reload.assert_not_called()
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0].args[0] == ["dconf", "load", "/"]
        assert mock_run.call_args_list[0].kwargs["stdin_text"] == "[org/gnome/shell]\n"
        assert mock_run.call_args_list[1].args[0] == ["dconf", "load", "/"]
        assert (
            "enabled-extensions=['layout-switcher-helper@communitybig.org', 'stay@ext']"
            in mock_run.call_args_list[1].kwargs["stdin_text"]
        )

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._restart_dash_to_panel_after_load")
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch(
        "layout_applier.LayoutApplier._enabled_extensions",
        return_value=[
            "stay@ext",
            "community-panel@communitybig.org",
        ],
    )
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_restarts_staying_dash_to_panel_before_other_leavers(
        self,
        _mock_run,
        _has,
        _persist,
        _reset,
        mock_disable,
        _enabled,
        _reload,
        mock_restart_dtp,
        mock_sleep,
    ):
        """Protect staying dash-to-panel from Shell rebase during removals."""
        data = (
            "[org/gnome/shell]\n"
            "enabled-extensions=['stay@ext', 'community-panel@communitybig.org']\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=[
                "leave@ext",
                "community-panel@communitybig.org",
                "stay@ext",
            ],
        )

        assert ok is True
        assert mock_disable.call_args.args[0] == [
            "community-panel@communitybig.org",
            "leave@ext",
        ]
        assert mock_disable.call_args.kwargs == {"sort": False}
        mock_restart_dtp.assert_called_once_with(["stay@ext", "community-panel@communitybig.org"])
        mock_sleep.assert_any_call(LayoutApplier._SETTLE_SEC)

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._restart_dash_to_panel_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch(
        "layout_applier.LayoutApplier._enabled_extensions",
        return_value=["community-panel@communitybig.org"],
    )
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_restarts_dash_to_panel_when_reapplying_same_layout(
        self,
        _mock_run,
        _has,
        _persist,
        _reset,
        mock_disable,
        _enabled,
        _reload,
        mock_restart_dtp,
        mock_sleep,
    ):
        """Reapplying a DTP layout must rebuild DTP panel actors."""
        data = "[org/gnome/shell]\nenabled-extensions=['community-panel@communitybig.org']\n"

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=["community-panel@communitybig.org"],
        )

        assert ok is True
        assert mock_disable.call_args.args[0] == [
            "community-panel@communitybig.org",
        ]
        assert mock_disable.call_args.kwargs == {"sort": False}
        mock_restart_dtp.assert_called_once_with(["community-panel@communitybig.org"])
        mock_sleep.assert_any_call(LayoutApplier._SETTLE_SEC)

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._enable_extensions_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._restart_dash_to_panel_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch(
        "layout_applier.LayoutApplier._enabled_extensions",
        return_value=["community-panel@communitybig.org"],
    )
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order")
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_restarts_dash_to_panel_after_layout_load(
        self,
        _mock_run,
        _has,
        _persist,
        _reset,
        mock_disable_batch,
        _enabled,
        _reload,
        mock_restart_dtp,
        mock_enable_after_load,
        mock_sleep,
    ):
        """DTP is rebuilt after its target settings are loaded."""
        data = "[org/gnome/shell]\nenabled-extensions=['community-panel@communitybig.org']\n"

        ok, _ = LayoutApplier.load_dconf_safely(data, before_uuids=[])

        assert ok is True
        mock_disable_batch.assert_not_called()
        mock_restart_dtp.assert_called_once_with(["community-panel@communitybig.org"])
        mock_enable_after_load.assert_not_called()

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._enable_user_theme_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch(
        "layout_applier.LayoutApplier._enabled_extensions",
        return_value=["user-theme@gnome-shell-extensions.gcampax.github.com"],
    )
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_enables_named_user_theme_after_settings_load(
        self,
        mock_run,
        _has,
        _persist,
        _reset,
        mock_disable,
        _enabled,
        _reload,
        mock_enable_user_theme,
        _sleep,
    ):
        """Named Shell themes must start after their name key is loaded."""
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/shell]\n"
            "disabled-extensions=[]\n"
            f"enabled-extensions=['{user_theme}', 'stay@ext']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name='Big-Blue'\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=["leave@ext"],
        )

        assert ok is True
        assert mock_disable.call_args.args[0] == ["leave@ext"]
        assert mock_disable.call_args.kwargs == {"sort": False}
        assert mock_run.call_count == 2
        assert "enabled-extensions" not in mock_run.call_args_list[0].kwargs["stdin_text"]
        switch_data = mock_run.call_args_list[1].kwargs["stdin_text"]
        assert (
            "enabled-extensions=['layout-switcher-helper@communitybig.org', "
            f"'{user_theme}', 'stay@ext']"
        ) in switch_data
        mock_enable_user_theme.assert_not_called()

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._enable_user_theme_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch("layout_applier.LayoutApplier._enabled_extensions", return_value=[])
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=False)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_disables_empty_user_theme_name_in_shell_switch(
        self,
        mock_run,
        _has,
        _persist,
        _reset,
        mock_disable,
        _enabled,
        _reload,
        mock_enable_user_theme,
        _sleep,
    ):
        """Empty user-theme names must not enable the user-theme extension."""
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{light_style}']\n"
            f"enabled-extensions=['{user_theme}', 'stay@ext']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name=''\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=["leave@ext"],
        )

        assert ok is True
        assert mock_disable.call_args.args[0] == ["leave@ext"]
        assert mock_disable.call_args.kwargs == {"sort": False}
        switch_data = mock_run.call_args_list[1].kwargs["stdin_text"]
        assert (
            "enabled-extensions=['layout-switcher-helper@communitybig.org', 'stay@ext']"
            in switch_data
        )
        assert (
            f"'{user_theme}'"
            not in LayoutApplier._section_key_values(
                switch_data,
                "/org/gnome/shell",
            )["enabled-extensions"]
        )
        disabled = LayoutApplier._string_list(
            LayoutApplier._section_key_values(
                switch_data,
                "/org/gnome/shell",
            )["disabled-extensions"]
        )
        assert light_style in disabled
        assert user_theme in disabled
        mock_enable_user_theme.assert_not_called()

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._enable_user_theme_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch("layout_applier.LayoutApplier._enabled_extensions", return_value=[])
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_keeps_running_user_theme_for_name_changes(
        self,
        mock_run,
        _has,
        _persist,
        _reset,
        mock_disable,
        _enabled,
        _reload,
        mock_enable_user_theme,
        _sleep,
    ):
        """Running user-theme consumes name changes without a DBus restart."""
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{light_style}']\n"
            f"enabled-extensions=['{user_theme}', 'stay@ext']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name=''\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=[user_theme, "leave@ext"],
        )

        assert ok is True
        assert mock_disable.call_args.args[0] == ["leave@ext"]
        assert mock_disable.call_args.kwargs == {"sort": False}
        switch_data = mock_run.call_args_list[1].kwargs["stdin_text"]
        shell = LayoutApplier._section_key_values(switch_data, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])
        assert user_theme not in enabled
        assert "stay@ext" in enabled
        assert light_style in disabled
        assert user_theme in disabled
        mock_enable_user_theme.assert_not_called()

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._wait_extension_live", return_value=True)
    @patch("layout_applier.LayoutApplier._enable_extensions_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._restart_dash_to_panel_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch(
        "layout_applier.LayoutApplier._enabled_extensions",
        side_effect=[
            ["stay@ext"],
            ["stay@ext", "community-panel@communitybig.org"],
            ["stay@ext", "community-panel@communitybig.org", "arcmenu@arcmenu.com"],
        ],
    )
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_stages_new_dash_to_panel_after_settings_load(
        self,
        mock_run,
        _has,
        _persist,
        _reset,
        mock_disable,
        _enabled,
        _reload,
        mock_restart_dtp,
        mock_enable_after_load,
        _wait_live,
        _sleep,
    ):
        """New DTP starts first; ArcMenu starts after the DTP panel exists."""
        arcmenu = "arcmenu@arcmenu.com"
        dash_to_panel = "community-panel@communitybig.org"
        data = (
            "[org/gnome/shell]\n"
            "disabled-extensions=[]\n"
            f"enabled-extensions=['stay@ext', '{arcmenu}', '{dash_to_panel}']\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(data, before_uuids=["stay@ext"])

        assert ok is True
        mock_disable.assert_not_called()
        switch_data = mock_run.call_args_list[1].kwargs["stdin_text"]
        assert (
            "enabled-extensions=['layout-switcher-helper@communitybig.org', 'stay@ext']"
            in switch_data
        )
        assert f"'{arcmenu}'" not in switch_data
        assert f"'{dash_to_panel}'" not in switch_data
        mock_restart_dtp.assert_called_once_with(["stay@ext"])
        mock_enable_after_load.assert_called_once_with([arcmenu])

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._wait_extension_live", return_value=True)
    @patch("layout_applier.LayoutApplier._enable_extensions_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._restart_dash_to_panel_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch(
        "layout_applier.LayoutApplier._enabled_extensions",
        side_effect=[
            ["stay@ext", "light-style@gnome-shell-extensions.gcampax.github.com"],
            [
                "stay@ext",
                "light-style@gnome-shell-extensions.gcampax.github.com",
                "community-panel@communitybig.org",
            ],
        ],
    )
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_keeps_light_style_stable_before_dash_to_panel_enters(
        self,
        _mock_run,
        _has,
        _persist,
        _reset,
        _disable,
        _enabled,
        _reload,
        mock_restart_dtp,
        _enable_after_load,
        _wait_live,
        _sleep,
    ):
        """Light DTP layouts start DTP after light-style is already active."""
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        dash_to_panel = "community-panel@communitybig.org"
        data = (
            "[org/gnome/shell]\n"
            "disabled-extensions=[]\n"
            f"enabled-extensions=['stay@ext', '{light_style}', '{dash_to_panel}']\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(data, before_uuids=["stay@ext"])

        assert ok is True
        mock_restart_dtp.assert_called_once_with(["stay@ext", light_style])
        _enable_after_load.assert_not_called()

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._enable_extensions_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._restart_dash_to_panel_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch("layout_applier.LayoutApplier._enabled_extensions", return_value=[])
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=False)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_still_enables_target_panel_after_disable_timeout(
        self,
        _mock_run,
        _has,
        _persist,
        _reset,
        mock_disable,
        _enabled,
        _reload,
        mock_restart_dtp,
        mock_enable_after_load,
        _sleep,
    ):
        """Target panel extensions are required even after secondary DBus timeouts."""
        arcmenu = "arcmenu@arcmenu.com"
        dash_to_panel = "community-panel@communitybig.org"
        data = (
            "[org/gnome/shell]\n"
            "disabled-extensions=[]\n"
            f"enabled-extensions=['stay@ext', '{arcmenu}', '{dash_to_panel}']\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=["leave@ext", "stay@ext"],
        )

        assert ok is True
        mock_disable.assert_not_called()
        mock_restart_dtp.assert_called_once_with(
            ["layout-switcher-helper@communitybig.org", "stay@ext"]
        )
        mock_enable_after_load.assert_called_once_with([arcmenu])

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.ShellReloader.get_extension_state", return_value=1)
    @patch(
        "layout_applier.ShellReloader.enable_extension_dbus",
        side_effect=[(False, "timeout"), (True, "")],
    )
    def test_enable_extensions_after_load_continues_after_one_timeout(
        self,
        mock_enable,
        _state,
        _sleep,
    ):
        """One extension timeout must not skip the next target extension."""
        ok = LayoutApplier._enable_extensions_after_load(
            ["arcmenu@arcmenu.com", "community-panel@communitybig.org"]
        )

        assert ok is False
        assert [call.args[0] for call in mock_enable.call_args_list] == [
            "arcmenu@arcmenu.com",
            "community-panel@communitybig.org",
        ]

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._wait_extension_not_live", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch("layout_applier.LayoutApplier._enabled_extensions", return_value=[])
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_disables_leaving_dash_to_panel_before_final_switch(
        self,
        _mock_run,
        _has,
        _persist,
        mock_reset,
        mock_disable,
        _enabled,
        _reload,
        _wait_not_live,
        _sleep,
    ):
        """Leaving DTP is torn down before the final Shell extension list."""
        arcmenu = "arcmenu@arcmenu.com"
        dash_to_panel = "community-panel@communitybig.org"
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{arcmenu}', '{dash_to_panel}', '{light_style}']\n"
            "enabled-extensions=['stay@ext']\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=[light_style, arcmenu, dash_to_panel, "stay@ext"],
        )

        assert ok is True
        mock_disable.assert_called_once_with(
            [
                "community-panel@communitybig.org",
                "arcmenu@arcmenu.com",
                "light-style@gnome-shell-extensions.gcampax.github.com",
            ],
            sort=False,
        )
        assert mock_reset.call_args.kwargs["skip_subdirs"] == {
            "/org/gnome/shell/extensions/arcmenu/",
            "/org/gnome/shell/extensions/dash-to-panel/",
            "/org/gnome/shell/extensions/light-style/",
        }

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._wait_extension_not_live", return_value=True)
    @patch("layout_applier.LayoutApplier._enable_extensions_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch(
        "layout_applier.LayoutApplier._enabled_extensions",
        side_effect=[
            ["stay@ext"],
            [
                "stay@ext",
                "community-dock@communitybig.org",
                "kiwi@kemma",
            ],
        ],
    )
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_stages_dark_shell_extensions_after_light_style_leaves(
        self,
        mock_run,
        _has,
        _persist,
        _reset,
        mock_disable,
        _enabled,
        _reload,
        mock_enable_after_load,
        _wait_not_live,
        _sleep,
    ):
        """Classic -> G-Unity starts Kiwi/Community Dock after light-style leaves."""
        arcmenu = "arcmenu@arcmenu.com"
        dash_to_panel = "community-panel@communitybig.org"
        community_dock = "community-dock@communitybig.org"
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        kiwi = "kiwi@kemma"
        data = (
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{arcmenu}', '{dash_to_panel}', '{light_style}']\n"
            f"enabled-extensions=['{community_dock}', '{kiwi}', 'stay@ext']\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=[light_style, arcmenu, dash_to_panel, "stay@ext"],
        )

        assert ok is True
        mock_disable.assert_called_once_with(
            [
                "community-panel@communitybig.org",
                "arcmenu@arcmenu.com",
                "light-style@gnome-shell-extensions.gcampax.github.com",
            ],
            sort=False,
        )
        switch_data = mock_run.call_args_list[1].kwargs["stdin_text"]
        assert f"'{community_dock}'" not in switch_data
        assert f"'{kiwi}'" not in switch_data
        assert f"'{light_style}'" in switch_data
        mock_enable_after_load.assert_called_once_with([community_dock, kiwi])

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._enable_user_theme_after_load", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch(
        "layout_applier.LayoutApplier._enabled_extensions",
        return_value=["user-theme@gnome-shell-extensions.gcampax.github.com"],
    )
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._read_dconf_value", return_value="'Big-Blue'")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_keeps_same_named_user_theme_running(
        self,
        mock_run,
        _has,
        _persist,
        _read_dconf,
        _reset,
        mock_disable,
        _enabled,
        _reload,
        mock_enable_user_theme,
        _sleep,
    ):
        """Desk UX -> BigGnome should not churn the same Big-Blue user-theme."""
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/shell]\n"
            "disabled-extensions=[]\n"
            f"enabled-extensions=['{user_theme}', 'stay@ext']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name='Big-Blue'\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=[user_theme, "leave@ext"],
        )

        assert ok is True
        assert mock_disable.call_args.args[0] == ["leave@ext"]
        assert mock_disable.call_args.kwargs == {"sort": False}
        switch_data = mock_run.call_args_list[1].kwargs["stdin_text"]
        assert f"'{user_theme}'" in switch_data
        mock_enable_user_theme.assert_not_called()

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._wait_extension_live", return_value=True)
    @patch("layout_applier.LayoutApplier._wait_extension_not_live", return_value=True)
    @patch("layout_applier.LayoutApplier._reload_visual_extensions")
    @patch(
        "layout_applier.LayoutApplier._enabled_extensions",
        return_value=["light-style@gnome-shell-extensions.gcampax.github.com"],
    )
    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_load_to_light_layout_forces_dark_shell_helpers_off(
        self,
        mock_run,
        _has,
        _persist,
        mock_reset,
        mock_disable,
        _enabled,
        _reload,
        _wait_not_live,
        _wait_live,
        _sleep,
    ):
        """Leaving G-Unity for a light layout must drop dark Shell helpers."""
        community_dock = "community-dock@communitybig.org"
        light_style = "light-style@gnome-shell-extensions.gcampax.github.com"
        user_theme = "user-theme@gnome-shell-extensions.gcampax.github.com"
        data = (
            "[org/gnome/shell]\n"
            f"disabled-extensions=['{user_theme}', '{community_dock}']\n"
            f"enabled-extensions=['{light_style}']\n"
            "\n"
            "[org/gnome/shell/extensions/user-theme]\n"
            "name='Big-Blue'\n"
        )

        ok, _ = LayoutApplier.load_dconf_safely(
            data,
            before_uuids=[user_theme, community_dock],
        )

        assert ok is True
        mock_disable.assert_called_once_with([community_dock], sort=False)
        settings_data = mock_run.call_args_list[0].kwargs["stdin_text"]
        assert "name='Big-Blue'" not in settings_data
        assert mock_reset.call_args.kwargs["skip_subdirs"] == {
            "/org/gnome/shell/extensions/dash-to-dock/",
            "/org/gnome/shell/extensions/user-theme/",
        }

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.LayoutApplier._set_enabled_extensions", return_value=True)
    @patch("layout_applier.ShellReloader.enable_extension_dbus", return_value=(True, ""))
    @patch(
        "layout_applier.ShellReloader.get_extension_state",
        side_effect=[
            2,
            1,
        ],
    )
    def test_restart_dash_to_panel_recovers_enabled_but_disabled_state(
        self,
        _mock_states,
        mock_enable,
        mock_set_enabled,
        _mock_sleep,
    ):
        """Remove DTP from enabled-extensions before enabling a disabled shell state."""
        ok = LayoutApplier._restart_dash_to_panel_after_load(
            ["stay@ext", "community-panel@communitybig.org"]
        )

        assert ok is True
        assert [call.args[0] for call in mock_set_enabled.call_args_list] == [
            ["stay@ext"],
            ["stay@ext", "community-panel@communitybig.org"],
        ]
        assert mock_enable.call_count == 2

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.ShellReloader.get_extension_state", return_value=1)
    @patch("layout_applier.ShellReloader.enable_extension_dbus", return_value=(True, ""))
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_enable_user_theme_after_load_writes_name_first(
        self,
        mock_run,
        mock_enable,
        _mock_state,
        mock_sleep,
    ):
        ok = LayoutApplier._enable_user_theme_after_load("Big-Blue")

        assert ok is True
        mock_run.assert_called_once_with(
            [
                "dconf",
                "write",
                "/org/gnome/shell/extensions/user-theme/name",
                "'Big-Blue'",
            ],
            timeout=5,
        )
        mock_enable.assert_called_once_with(
            "user-theme@gnome-shell-extensions.gcampax.github.com",
            enable=True,
            timeout=LayoutApplier._SHELL_DBUS_TIMEOUT_SEC,
        )
        assert mock_sleep.call_count == 2

    @patch("layout_applier.time.sleep")
    @patch("layout_applier.ShellReloader.get_extension_state", return_value=1)
    @patch("layout_applier.ShellReloader.enable_extension_dbus", return_value=(True, ""))
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_enable_user_theme_after_load_accepts_empty_name(
        self,
        mock_run,
        mock_enable,
        _mock_state,
        _mock_sleep,
    ):
        ok = LayoutApplier._enable_user_theme_after_load("")

        assert ok is True
        mock_run.assert_called_once_with(
            [
                "dconf",
                "write",
                "/org/gnome/shell/extensions/user-theme/name",
                "''",
            ],
            timeout=5,
        )
        mock_enable.assert_called_once_with(
            "user-theme@gnome-shell-extensions.gcampax.github.com",
            enable=True,
            timeout=LayoutApplier._SHELL_DBUS_TIMEOUT_SEC,
        )

    @patch("layout_applier.run_cmd")
    def test_reset_orphan_keys_resets_leaving_branches_and_stale_keys(
        self,
        mock_run,
    ):
        """Treat layout text as exact state, not a merge patch."""
        live = (
            "[org/gnome/shell/extensions/leaving]\n"
            "old=true\n"
            "\n"
            "[org/gnome/shell/extensions/staying]\n"
            "keep=true\n"
            "old=true\n"
        )
        target = "[org/gnome/shell/extensions/staying]\nkeep=true\n"
        mock_run.side_effect = [
            (True, live),
            (True, ""),
            (True, ""),
        ]

        count = LayoutApplier._reset_orphan_keys(target)

        assert count == 2
        assert mock_run.call_count == 3
        assert mock_run.call_args_list[0].args[0] == ["dconf", "dump", "/"]
        assert mock_run.call_args_list[1].args[0] == [
            "dconf",
            "reset",
            "-f",
            "/org/gnome/shell/extensions/leaving/",
        ]
        assert mock_run.call_args_list[2].args[0] == [
            "dconf",
            "reset",
            "/org/gnome/shell/extensions/staying/old",
        ]


class TestRewriteDtpKeysInText:
    """Garante que o rewrite text-level converte monitor IDs DTP para os locais."""

    def test_rewrites_foreign_keys_to_local(self):
        """Layout vem com 'unknown-unknown'; local é 'CMN-0x00000000'."""
        text = (
            "[org/gnome/shell/extensions/dash-to-panel]\n"
            'panel-positions=\'{"unknown-unknown":"BOTTOM"}\'\n'
        )
        out = LayoutApplier._rewrite_dtp_keys_in_text(text, {"CMN-0x00000000"})
        assert "CMN-0x00000000" in out
        assert "unknown-unknown" not in out
        assert "BOTTOM" in out

    def test_noop_when_keys_already_match(self):
        """Se o layout já tem o ID local, mantém intacto."""
        text = "[org/gnome/shell/extensions/dash-to-panel]\npanel-sizes='{\"DEL-12345\":48}'\n"
        out = LayoutApplier._rewrite_dtp_keys_in_text(text, {"DEL-12345"})
        assert out == text

    def test_empty_local_keys_returns_text_unchanged(self):
        """Sem IDs locais (mutter/dconf vazios), não mexe no texto."""
        text = '[org/gnome/shell/extensions/dash-to-panel]\npanel-positions=\'{"foo":"BOTTOM"}\'\n'
        assert LayoutApplier._rewrite_dtp_keys_in_text(text, set()) == text

    def test_non_dtp_lines_pass_through(self):
        """Chaves fora da lista DTP monitor-keyed não são tocadas."""
        text = (
            "[org/gnome/desktop/interface]\n"
            "gtk-theme='adw-gtk3-dark'\n"
            "icon-theme='bigicons-papient'\n"
        )
        out = LayoutApplier._rewrite_dtp_keys_in_text(text, {"CMN-0x00000000"})
        assert out == text

    def test_preserves_trailing_newline(self):
        """Newline final do dump deve ser preservado."""
        text = "[/]\nfoo='bar'\n"
        out = LayoutApplier._rewrite_dtp_keys_in_text(text, {"X"})
        assert out.endswith("\n")

    def test_replicates_value_to_all_local_monitors(self):
        """Com múltiplos monitores locais, replica o valor original em cada um."""
        text = '[org/gnome/shell/extensions/dash-to-panel]\npanel-positions=\'{"old":"BOTTOM"}\'\n'
        out = LayoutApplier._rewrite_dtp_keys_in_text(text, {"A-1", "B-2"})
        assert "A-1" in out
        assert "B-2" in out
        assert "old" not in out


class TestCuratedLayoutFiles:
    def test_desk_ux_helper_label_uses_canonical_spelling(self):
        assert LayoutApplier._layout_display_label("desk-ux") == "Desk UX"

    def test_layout_apply_data_records_the_unified_runtime_profile(self):
        source = "[org/gnome/shell]\nenabled-extensions=[]\n"

        result = LayoutApplier._inject_runtime_active_layout(source, "desk-ux")
        runtime = LayoutApplier._section_key_values(
            result,
            "/org/communitybig/layout-switcher/runtime",
        )

        assert runtime["active-layout"] == "'Desk UX'"

    def test_saved_snapshot_without_layout_identity_is_unchanged(self):
        source = "[org/gnome/shell]\nenabled-extensions=[]\n"

        assert LayoutApplier._inject_runtime_active_layout(source, "") == source

    def test_original_dock_layout_resets_overrides_and_live_panel_defaults(self):
        class FakeRuntimeSettings:
            def serialized_overrides_without_layout(self, layout):
                assert layout == "BigGnome"
                return {
                    "indicator-style-overrides": "{'G-Unity': 'dot'}",
                    "dock-opacity-overrides": "{'G-Unity': uint32 80}",
                    "dock-hover-overrides": "{'G-Unity': 'lift'}",
                }

            def default(self, layout, setting):
                assert layout == "BigGnome"
                return {
                    "panel-opacity": 65,
                    "panel-visibility": "always-visible",
                }[setting]

        source = "[org/gnome/shell]\nenabled-extensions=[]\n"
        with patch("layout_applier.RuntimeSettings", FakeRuntimeSettings):
            result = LayoutApplier._reset_original_runtime_overrides(
                source,
                "biggnome",
            )

        runtime = LayoutApplier._section_key_values(
            result,
            "/org/communitybig/layout-switcher/runtime",
        )
        assert runtime["indicator-style-overrides"] == "{'G-Unity': 'dot'}"
        assert runtime["dock-opacity-overrides"] == "{'G-Unity': uint32 80}"
        assert runtime["dock-hover-overrides"] == "{'G-Unity': 'lift'}"
        panel = LayoutApplier._section_key_values(
            result,
            "/org/communitybig/panel-and-dock",
        )
        assert panel["panel-opacity"] == "uint32 65"
        assert panel["panel-visibility"] == "'always-visible'"

    def test_desk_ux_dtp_position_and_size_are_explicit(self):
        """Desk UX must not depend on inherited DTP defaults."""
        text = Path("usr/share/layout-switcher/layouts/desk-ux.txt").read_text(encoding="utf-8")
        values = LayoutApplier._section_key_values(
            text,
            "/org/gnome/shell/extensions/dash-to-panel",
        )

        assert LayoutApplier._parse_dtp_json(values["panel-positions"])
        assert LayoutApplier._parse_dtp_json(values["panel-sizes"])
        assert values["group-apps"] == "true"
        assert values["show-favorites"] == "true"
        assert values["show-running-apps"] == "true"
        assert values["trans-use-custom-bg"] == "true"
        assert values["trans-bg-color"] == "'#000000'"
        assert values["trans-use-custom-opacity"] == "true"
        assert float(values["trans-panel-opacity"]) == 0.65
        assert values["tray-padding"] == "9"
        assert values["status-icon-padding"] == "0"


class TestShellReloader:
    @patch("shell_reloader.run_cmd")
    def test_list_extensions_state_handles_nested_metadata(self, mock_run):
        from shell_reloader import ShellReloader

        mock_run.return_value = (
            True,
            "({'arcmenu@arcmenu.com': {"
            "'uuid': <'arcmenu@arcmenu.com'>, "
            "'donations': <{'paypal': <'azaech'>}>, "
            "'state': <6.0>, 'enabled': <false>}, "
            "'community-panel@communitybig.org': {"
            "'uuid': <'community-panel@communitybig.org'>, "
            "'donations': <{'paypal': <'charlesg99'>}>, "
            "'state': <1.0>, 'enabled': <true>}},)",
        )

        assert ShellReloader.list_extensions_state() == {
            "arcmenu@arcmenu.com": 6,
            "community-panel@communitybig.org": 1,
        }

    @patch("shell_reloader.run_cmd")
    def test_get_extension_state_handles_nested_metadata(self, mock_run):
        from shell_reloader import ShellReloader

        mock_run.return_value = (
            True,
            "({'uuid': <'community-panel@communitybig.org'>, "
            "'donations': <{'paypal': <'charlesg99'>}>, "
            "'state': <1.0>, 'enabled': <true>},)",
        )

        assert ShellReloader.get_extension_state("community-panel@communitybig.org") == 1

    @patch("shell_reloader.run_cmd", return_value=(True, ""))
    @patch("shell_reloader.is_wayland", return_value=True)
    def test_reload_all_wayland(self, _mock_way, mock_run):
        from shell_reloader import ShellReloader

        # before = {a, c}; after = {a, b}.
        # Esperado: Disable c (em before, não em after), Enable b (em after,
        # não em before). a@x fica em paz (em ambos). Sem reexec no Wayland.
        ShellReloader.reload_all(
            before_uuids=["a@x", "c@z"],
            after_uuids=["a@x", "b@y"],
        )
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert mock_run.call_count == 3
        assert any("DisableExtension" in args[-2] and "c@z" in args[-1] for args in calls)
        assert any("ListExtensions" in args[-1] for args in calls)
        assert any("EnableExtension" in args[-2] and "b@y" in args[-1] for args in calls)
        # a@x não deve ser tocada
        for args in calls:
            assert "a@x" != args[-1]
        assert not any("reexec" in str(c) for c in mock_run.call_args_list)

    @patch("shell_reloader.run_cmd", return_value=(True, ""))
    @patch("shell_reloader.is_wayland", return_value=False)
    def test_reload_all_x11(self, _mock_way, mock_run):
        from shell_reloader import ShellReloader

        ShellReloader.reload_all(before_uuids=["x@1"], after_uuids=["y@2"])
        # Disable x@1 (removed) + Enable y@2 (added) + reexec_self (X11) = 3
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("DisableExtension" in c and "x@1" in c for c in calls)
        assert any("EnableExtension" in c and "y@2" in c for c in calls)
        assert any("reexec" in c for c in calls)

    @patch("shell_reloader.run_cmd", return_value=(True, ""))
    @patch("shell_reloader.is_wayland", return_value=True)
    def test_reload_all_no_args_is_noop_on_wayland(self, _mock_way, mock_run):
        """Sem before/after, em Wayland, reload_all não emite chamadas."""
        from shell_reloader import ShellReloader

        ShellReloader.reload_all()
        assert mock_run.call_count == 0

    @patch("shell_reloader.ShellReloader.reload_extension")
    @patch("shell_reloader.ShellReloader.enable_extension_dbus", return_value=(True, ""))
    def test_apply_extension_state_disable_does_not_reload(self, _mock_dbus, mock_reload):
        from shell_reloader import ShellReloader

        ok, _ = ShellReloader.apply_extension_state("uuid@x", enable=False)

        assert ok is True
        mock_reload.assert_not_called()

    @patch("shell_reloader.ShellReloader.enable_extension_dbus")
    def test_required_helper_cannot_be_disabled(self, mock_dbus):
        from helper_client import HELPER_UUID
        from shell_reloader import ShellReloader

        ok, msg = ShellReloader.apply_extension_state(HELPER_UUID, enable=False)

        assert ok is False
        assert msg
        mock_dbus.assert_not_called()


class TestHelperIntegration:
    """The in-shell helper path (preferred) vs the legacy external fallback."""

    def test_managed_subdirs_include_legacy_arcmenu_for_cleanup(self, tmp_path):
        data = (
            "[org/gnome/shell/extensions/community-menu]\n"
            "layout='APPS_ONLY'\n\n"
            "[org/gnome/shell/extensions/appindicator]\n"
            "tray-pos='center'\n\n"
            "[org/gnome/shell/extensions/gsconnect]\n"
            "devices={}\n\n"
            "[org/gnome/shell/extensions/gtk4-ding]\n"
            "icon-size='standard'\n"
        )
        (tmp_path / "classic.txt").write_text(data)

        subdirs = LayoutApplier._managed_extension_subdirs(data, tmp_path)

        assert "community-menu" in subdirs
        assert "arcmenu" in subdirs
        assert "appindicator" in subdirs
        assert "gsconnect" not in subdirs
        assert "gtk4-ding" not in subdirs

    def test_inject_helper_uuid_adds(self):
        from helper_client import HELPER_UUID

        data = "[org/gnome/shell]\nenabled-extensions=['kiwi@kemma']\n"
        out = LayoutApplier._inject_helper_uuid(data)
        assert HELPER_UUID in out

    def test_inject_helper_uuid_idempotent(self):
        from helper_client import HELPER_UUID

        data = f"[org/gnome/shell]\nenabled-extensions=['{HELPER_UUID}']\n"
        out = LayoutApplier._inject_helper_uuid(data)
        assert out.count(HELPER_UUID) == 1

    def test_inject_helper_uuid_migrates_legacy_community_menu_uuid(self):
        from helper_client import HELPER_UUID

        legacy = "community-menu@bigcommunity.org"
        current = "community-menu@communitybig.org"
        data = (
            "[org/gnome/shell]\n"
            f"enabled-extensions=['{legacy}', '{current}', 'stay@ext']\n"
            f"disabled-extensions=['{legacy}', 'disabled@ext']\n"
        )

        out = LayoutApplier._inject_helper_uuid(data)
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")

        assert LayoutApplier._string_list(shell["enabled-extensions"]) == [
            HELPER_UUID,
            current,
            "stay@ext",
        ]
        assert LayoutApplier._string_list(shell["disabled-extensions"]) == [
            "disabled@ext",
        ]
        assert legacy not in out

    @pytest.mark.parametrize(
        ("legacy", "current"),
        [
            ("dash-to-dock@micxgx.gmail.com", "layout-switcher-runtime@communitybig.org"),
            ("dash-to-panel@jderose9.github.com", "layout-switcher-runtime@communitybig.org"),
            ("big-shot@bigcommunity.org", "big-shot@communitybig.org"),
        ],
    )
    def test_inject_helper_uuid_migrates_saved_layout_components(self, legacy, current):
        data = (
            "[org/gnome/shell]\n"
            f"enabled-extensions=['{legacy}', 'stay@ext']\n"
            "disabled-extensions=[]\n"
        )

        out = LayoutApplier._inject_helper_uuid(data)
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])

        assert current in enabled
        assert legacy not in out

    def test_inject_helper_uuid_keeps_installed_legacy_big_shot_at_runtime(self):
        legacy = "big-shot@bigcommunity.org"
        current = "big-shot@communitybig.org"
        data = (
            "[org/gnome/shell]\n"
            f"enabled-extensions=['{current}', 'stay@ext']\n"
            "disabled-extensions=[]\n"
        )

        out = LayoutApplier._inject_helper_uuid(
            data,
            available_uuids={legacy},
        )
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])

        assert legacy in enabled
        assert current not in enabled

    def test_inject_helper_uuid_retires_legacy_from_saved_lists(self):
        from helper_client import HELPER_UUID, LEGACY_HELPER_UUID

        data = (
            "[org/gnome/shell]\n"
            f"enabled-extensions=['{LEGACY_HELPER_UUID}', 'stay@ext']\n"
            f"disabled-extensions=['{HELPER_UUID}', '{LEGACY_HELPER_UUID}']\n"
        )
        out = LayoutApplier._inject_helper_uuid(data)
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")

        assert LayoutApplier._string_list(shell["enabled-extensions"]) == [
            HELPER_UUID,
            "stay@ext",
        ]
        assert LayoutApplier._string_list(shell["disabled-extensions"]) == []

    def test_inject_helper_uuid_keeps_loaded_legacy_until_logout(self):
        from helper_client import HELPER_UUID, LEGACY_HELPER_UUID

        data = (
            "[org/gnome/shell]\n"
            "enabled-extensions=['stay@ext']\n"
            f"disabled-extensions=['{LEGACY_HELPER_UUID}']\n"
        )
        out = LayoutApplier._inject_helper_uuid(
            data,
            active_helper_uuid=LEGACY_HELPER_UUID,
        )
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")

        assert LayoutApplier._string_list(shell["enabled-extensions"]) == [
            LEGACY_HELPER_UUID,
            HELPER_UUID,
            "stay@ext",
        ]
        assert LayoutApplier._string_list(shell["disabled-extensions"]) == []

    def test_inject_helper_uuid_preserves_active_frosted_glass(self):
        from helper_client import HELPER_UUID

        frosted = "frosted-glass@communitybig.org"
        data = "[org/gnome/shell]\nenabled-extensions=['kiwi@kemma']\n"
        out = LayoutApplier._inject_helper_uuid(data, [frosted])
        enabled = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        values = LayoutApplier._string_list(enabled["enabled-extensions"])

        assert values[0] == HELPER_UUID
        assert frosted in values

    def test_inject_helper_uuid_does_not_override_desktop_icon_layout_default(self):
        from helper_client import HELPER_UUID

        desktop_icons = "gtk4-ding@smedius.gitlab.com"
        data = (
            "[org/gnome/shell]\n"
            "enabled-extensions=['kiwi@kemma']\n"
            f"disabled-extensions=['{desktop_icons}']\n"
        )
        out = LayoutApplier._inject_helper_uuid(data, [desktop_icons])
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])
        disabled = LayoutApplier._string_list(shell["disabled-extensions"])

        assert enabled[0] == HELPER_UUID
        assert desktop_icons not in enabled
        assert desktop_icons in disabled

    def test_inject_helper_uuid_resolves_duplicate_desktop_icon_state(self):
        desktop_icons = "gtk4-ding@smedius.gitlab.com"
        data = (
            "[org/gnome/shell]\n"
            f"enabled-extensions=['{desktop_icons}', 'stay@ext']\n"
            f"disabled-extensions=['{desktop_icons}']\n"
        )

        out = LayoutApplier._inject_helper_uuid(data, [])
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")

        assert desktop_icons in LayoutApplier._string_list(shell["enabled-extensions"])
        assert desktop_icons not in LayoutApplier._string_list(shell["disabled-extensions"])

    def test_preserves_global_feature_settings_over_old_snapshot(self, tmp_path):
        current = tmp_path / "settings.gnome"
        current.write_text(
            "[org/communitybig/frosted-glass]\n"
            "blur-strength=0.75\n\n"
            "[org/gnome/shell/extensions/gtk4-ding]\n"
            "icon-size='large'\n\n"
            "[org/gnome/desktop/interface]\n"
            "color-scheme='prefer-dark'\n"
        )
        snapshot = (
            "[org/communitybig/frosted-glass]\n"
            "blur-strength=0.25\n\n"
            "[org/gnome/shell/extensions/gtk4-ding]\n"
            "icon-size='tiny'\n\n"
            "[org/gnome/desktop/interface]\n"
            "color-scheme='default'\n"
        )

        with patch("layout_applier.SETTINGS_GNOME", current):
            out = LayoutApplier._preserve_layout_independent_settings(snapshot)

        assert "blur-strength=0.75" in out
        assert "blur-strength=0.25" not in out
        assert "icon-size='large'" in out
        assert "icon-size='tiny'" not in out
        assert "color-scheme='default'" in out

    @pytest.mark.parametrize(
        ("layout_id", "expected"),
        [
            ("biggnome", True),
            ("desk-ux", True),
            ("g-unity", True),
            ("classic", False),
            ("hybrid", False),
            ("minimal", False),
        ],
    )
    def test_gnome50_overview_default_is_owned_by_three_original_layouts(self, layout_id, expected):
        data = "[org/gnome/shell]\nenabled-extensions=['stay@ext']\n"

        out = LayoutApplier._apply_gnome50_overview_default(data, layout_id)
        glass = LayoutApplier._section_key_values(out, "/org/communitybig/frosted-glass")
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")
        enabled = LayoutApplier._string_list(shell["enabled-extensions"])

        value = "true" if expected else "false"
        assert glass["enabled"] == value
        assert glass["overview-enabled"] == value
        assert ("frosted-glass@communitybig.org" in enabled) is expected

    def test_original_frosted_glass_default_resets_material_opacity(self):
        data = "[org/communitybig/frosted-glass]\nglass-opacity=100\n"

        out = LayoutApplier._apply_original_frosted_glass_defaults(data)
        glass = LayoutApplier._section_key_values(out, "/org/communitybig/frosted-glass")

        assert glass["glass-opacity"] == "37"

    def test_inject_helper_uuid_retires_blur_my_shell(self):
        blur_my_shell = "blur-my-shell@aunetx"
        data = (
            "[org/gnome/shell]\n"
            f"enabled-extensions=['kiwi@kemma', '{blur_my_shell}']\n"
            "disabled-extensions=[]\n"
        )

        out = LayoutApplier._inject_helper_uuid(data)
        shell = LayoutApplier._section_key_values(out, "/org/gnome/shell")

        assert blur_my_shell not in LayoutApplier._string_list(shell["enabled-extensions"])
        assert blur_my_shell in LayoutApplier._string_list(shell["disabled-extensions"])

    @patch(
        "layout_applier.ShellReloader.list_extensions_state",
        return_value={"community-panel@communitybig.org": 4},
    )
    def test_rejects_outdated_structural_extension(self, _states):
        data = "[org/gnome/shell]\nenabled-extensions=['community-panel@communitybig.org']\n"

        ok, msg = LayoutApplier._validate_structural_extensions(data)

        assert ok is False
        assert "incompatible" in msg

    @patch(
        "layout_applier.HelperClient.ensure_available",
        return_value=(False, "helper missing"),
    )
    @patch("layout_applier.run_cmd")
    def test_aborts_before_writing_when_required_helper_is_unavailable(
        self,
        mock_run,
        _mock_available,
    ):
        ok, msg = LayoutApplier.load_dconf_safely("[/]\nfoo='bar'", before_uuids=[])

        assert ok is False
        assert "helper missing" in msg
        mock_run.assert_not_called()

    @patch("layout_applier.HelperClient.apply_layout", return_value=(True, "steps"))
    @patch("layout_applier.HelperClient.helper_version", return_value=6)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    def test_prefers_helper_when_available(self, _has, _persist, _run, _ver, mock_apply):
        from helper_client import HELPER_UUID

        data = "[org/gnome/shell]\nenabled-extensions=['kiwi@kemma']\n"
        ok, _msg = LayoutApplier.load_dconf_safely(data, before_uuids=[])
        assert ok is True
        mock_apply.assert_called_once()
        target = mock_apply.call_args.args[0]
        assert "kiwi@kemma" in target
        assert HELPER_UUID in target
        # kiwi is appearance-owning → in the reload set
        assert "kiwi@kemma" in mock_apply.call_args.kwargs["reload"]

    @patch("layout_applier.LayoutApplier._apply_via_helper_v7", return_value=(True, "ok"))
    @patch("layout_applier.HelperClient.helper_version", return_value=7)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    def test_prefers_cleanroom_on_v7_helper(self, _has, _persist, _run, _ver, mock_v7):
        """A v7+ helper routes the apply through the clean-room protocol."""
        data = "[org/gnome/shell]\nenabled-extensions=['kiwi@kemma']\n"
        ok, _msg = LayoutApplier.load_dconf_safely(data, before_uuids=[], layout_label="G-Unity")
        assert ok is True
        mock_v7.assert_called_once()
        assert mock_v7.call_args.kwargs["layout_label"] == "G-Unity"

    @patch("layout_applier.ShellReloader.list_extensions_state", return_value={})
    @patch("layout_applier.HelperClient.reload_extension", return_value=True)
    @patch("layout_applier.HelperClient.complete_switch", return_value=(True, "steps"))
    @patch("layout_applier.HelperClient.begin_switch", return_value=(True, ""))
    @patch("layout_applier.HelperClient.ping_info", return_value={})
    @patch("layout_applier.LayoutApplier._enabled_extensions", return_value=[])
    @patch("layout_applier.LayoutApplier._managed_extension_subdirs", return_value=[])
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    def test_cleanroom_reloads_kiwi_when_forced_focus_is_disabled(
        self,
        _run,
        _subdirs,
        _enabled,
        _ping,
        _begin,
        _complete,
        mock_reload,
        _states,
    ):
        data = (
            "[org/gnome/shell]\n"
            "disabled-extensions=[]\n"
            "enabled-extensions=['kiwi@kemma']\n\n"
            "[org/gnome/shell/extensions/kiwi]\n"
            "focus-launched-windows=false\n"
        )

        ok, _msg = LayoutApplier._apply_via_helper_v7(data)

        assert ok is True
        mock_reload.assert_called_once_with("kiwi@kemma")

    @patch("layout_applier.LayoutApplier._disable_extensions_in_order", return_value=True)
    @patch("layout_applier.LayoutApplier._reset_orphan_keys")
    @patch("layout_applier.HelperClient.apply_layout")
    @patch("layout_applier.HelperClient.helper_version", return_value=0)
    @patch("layout_applier.run_cmd", return_value=(True, ""))
    @patch("layout_applier.LayoutApplier._persist_to_settings_file", return_value=(True, "/x"))
    @patch("layout_applier.LayoutApplier._has_user_unit", return_value=False)
    @patch("layout_applier.time.sleep")
    def test_falls_back_to_legacy_when_unavailable(
        self, _sleep, _has, _persist, _run, _avail, mock_apply, _reset, _disable
    ):
        data = "[org/gnome/shell]\nenabled-extensions=['kiwi@kemma']\n"
        ok, _msg = LayoutApplier.load_dconf_safely(data, before_uuids=["leave@ext"])
        assert ok is True
        mock_apply.assert_not_called()
