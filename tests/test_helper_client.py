# SPDX-License-Identifier: MIT
"""Tests for helper_client.py — D-Bus client for the in-shell helper."""

from unittest.mock import call, patch

from helper_client import (
    ARCMENU_UUID,
    BIG_SHOT_UUID,
    COMMUNITY_DOCK_UUID,
    COMMUNITY_MENU_UUID,
    COMMUNITY_PANEL_UUID,
    HELPER_UUID,
    LEGACY_BIG_SHOT_UUID,
    LEGACY_COMMUNITY_MENU_UUID,
    LEGACY_DASH_TO_DOCK_UUID,
    LEGACY_DASH_TO_PANEL_UUID,
    LEGACY_HELPER_UUID,
    RUNTIME_UUID,
    HelperClient,
)


class TestIsAvailable:
    @patch(
        "helper_client.HelperClient._call",
        return_value='{"helper":"layout-switcher","version":1}',
    )
    def test_available(self, _mock):
        assert HelperClient.is_available() is True

    @patch("helper_client.HelperClient._call", return_value=None)
    def test_unavailable_no_reply(self, _mock):
        assert HelperClient.is_available() is False


class TestRequiredExtensionLists:
    def test_helper_is_first_and_removed_from_disabled(self):
        enabled, disabled = HelperClient.required_extension_lists(
            ["alpha@example.org", HELPER_UUID, "beta@example.org"],
            ["disabled@example.org", HELPER_UUID],
        )

        assert enabled == [HELPER_UUID, "alpha@example.org", "beta@example.org"]
        assert disabled == ["disabled@example.org"]

    def test_does_not_change_optional_extensions(self):
        enabled, disabled = HelperClient.required_extension_lists(
            ["alpha@example.org"],
            ["disabled@example.org"],
        )

        assert enabled == [HELPER_UUID, "alpha@example.org"]
        assert disabled == ["disabled@example.org"]

    def test_retires_legacy_uuid(self):
        enabled, disabled = HelperClient.required_extension_lists(
            [LEGACY_HELPER_UUID, "alpha@example.org"],
            [HELPER_UUID, LEGACY_HELPER_UUID, "disabled@example.org"],
        )

        assert enabled == [HELPER_UUID, "alpha@example.org"]
        assert disabled == ["disabled@example.org"]

    def test_migrates_owned_extension_uuids_without_touching_others(self):
        enabled, disabled = HelperClient.required_extension_lists(
            [LEGACY_COMMUNITY_MENU_UUID, LEGACY_BIG_SHOT_UUID, "user@example.org"],
            [COMMUNITY_MENU_UUID, "disabled@example.org"],
        )

        assert enabled == [
            HELPER_UUID,
            COMMUNITY_MENU_UUID,
            BIG_SHOT_UUID,
            "user@example.org",
        ]
        assert disabled == ["disabled@example.org"]

    def test_migrates_disabled_owned_extension_without_enabling_it(self):
        enabled, disabled = HelperClient.required_extension_lists(
            ["user@example.org"],
            [LEGACY_COMMUNITY_MENU_UUID, LEGACY_BIG_SHOT_UUID],
        )

        assert enabled == [HELPER_UUID, "user@example.org"]
        assert disabled == [COMMUNITY_MENU_UUID, BIG_SHOT_UUID]

    def test_migrates_external_layout_components_to_bundled_replacements(self):
        enabled, disabled = HelperClient.required_extension_lists(
            [LEGACY_DASH_TO_DOCK_UUID, "user@example.org"],
            [LEGACY_DASH_TO_PANEL_UUID],
        )

        assert enabled == [HELPER_UUID, RUNTIME_UUID, "user@example.org"]
        assert disabled == []

    def test_migrates_intermediate_components_to_unified_runtime(self):
        enabled, disabled = HelperClient.required_extension_lists(
            [COMMUNITY_DOCK_UUID, COMMUNITY_PANEL_UUID, "user@example.org"],
            [LEGACY_DASH_TO_DOCK_UUID, LEGACY_DASH_TO_PANEL_UUID],
            available_uuids={HELPER_UUID, RUNTIME_UUID},
        )

        assert enabled == [HELPER_UUID, RUNTIME_UUID, "user@example.org"]
        assert disabled == []

    def test_migrates_stable_hybrid_session_without_touching_user_extensions(self):
        enabled, disabled = HelperClient.required_extension_lists(
            [
                LEGACY_HELPER_UUID,
                LEGACY_DASH_TO_PANEL_UUID,
                ARCMENU_UUID,
                "user@example.org",
            ],
            [LEGACY_DASH_TO_DOCK_UUID, "disabled@example.org"],
            available_uuids={
                HELPER_UUID,
                RUNTIME_UUID,
                COMMUNITY_MENU_UUID,
                ARCMENU_UUID,
                "user@example.org",
            },
            active_layout="Hybrid",
        )

        assert enabled == [
            HELPER_UUID,
            RUNTIME_UUID,
            COMMUNITY_MENU_UUID,
            "user@example.org",
        ]
        assert disabled == ["disabled@example.org", ARCMENU_UUID]

    def test_preserves_arc_menu_outside_saved_hybrid(self):
        enabled, disabled = HelperClient.required_extension_lists(
            [LEGACY_DASH_TO_PANEL_UUID, ARCMENU_UUID],
            [],
            available_uuids={
                HELPER_UUID,
                RUNTIME_UUID,
                COMMUNITY_MENU_UUID,
                ARCMENU_UUID,
            },
        )

        assert enabled == [HELPER_UUID, RUNTIME_UUID, ARCMENU_UUID]
        assert disabled == []

    def test_helper_only_repair_preserves_live_legacy_components(self):
        enabled, disabled = HelperClient.required_helper_lists(
            [LEGACY_HELPER_UUID, LEGACY_DASH_TO_PANEL_UUID, "arcmenu@arcmenu.com"],
            [COMMUNITY_PANEL_UUID],
        )

        assert enabled == [
            HELPER_UUID,
            LEGACY_DASH_TO_PANEL_UUID,
            "arcmenu@arcmenu.com",
        ]
        assert disabled == [COMMUNITY_PANEL_UUID]

    def test_keeps_legacy_big_shot_when_replacement_is_not_installed(self):
        enabled, disabled = HelperClient.required_extension_lists(
            [LEGACY_BIG_SHOT_UUID],
            [],
            available_uuids={HELPER_UUID, LEGACY_BIG_SHOT_UUID},
        )

        assert enabled == [HELPER_UUID, LEGACY_BIG_SHOT_UUID]
        assert disabled == []

    def test_falls_back_from_new_big_shot_to_installed_legacy_uuid(self):
        enabled, disabled = HelperClient.required_extension_lists(
            [BIG_SHOT_UUID],
            [],
            available_uuids={HELPER_UUID, LEGACY_BIG_SHOT_UUID},
        )

        assert enabled == [HELPER_UUID, LEGACY_BIG_SHOT_UUID]
        assert disabled == []

    def test_migrates_panel_only_when_bundled_replacement_is_installed(self):
        enabled, _disabled = HelperClient.required_extension_lists(
            [LEGACY_DASH_TO_PANEL_UUID],
            [],
            available_uuids={HELPER_UUID, RUNTIME_UUID},
        )

        assert enabled == [HELPER_UUID, RUNTIME_UUID]

    def test_places_migrated_panel_before_arc_menu(self):
        enabled, _disabled = HelperClient.required_extension_lists(
            [ARCMENU_UUID, LEGACY_DASH_TO_PANEL_UUID],
            [],
            available_uuids={HELPER_UUID, RUNTIME_UUID, ARCMENU_UUID},
        )

        assert enabled == [HELPER_UUID, RUNTIME_UUID, ARCMENU_UUID]


class TestComponentAssetMigration:
    def test_rewrites_legacy_community_menu_icon_path(self):
        legacy = (
            "/usr/share/gnome-shell/extensions/"
            "community-menu@bigcommunity.org/community-menu.svg"
        )

        migrated = HelperClient.migrate_component_asset_path(legacy)

        assert migrated == (
            "/usr/share/gnome-shell/extensions/"
            "community-menu@communitybig.org/community-menu.svg"
        )

    def test_preserves_unrelated_custom_icon_path(self):
        path = "/home/user/.local/share/icons/custom.svg"

        assert HelperClient.migrate_component_asset_path(path) == path


class TestActiveUuid:
    @patch(
        "helper_client.HelperClient.ping_info",
        return_value={
            "helper": "layout-switcher",
            "uuid": HELPER_UUID,
            "version": 26,
        },
    )
    def test_detects_current_helper(self, _mock_ping):
        assert HelperClient.active_uuid() == HELPER_UUID

    @patch(
        "helper_client.HelperClient.ping_info",
        return_value={"helper": "layout-switcher", "version": 25},
    )
    def test_detects_legacy_helper_without_uuid_field(self, _mock_ping):
        assert HelperClient.active_uuid() == LEGACY_HELPER_UUID


class TestEnsureAvailable:
    @patch("helper_client.HelperClient.ensure_enabled", return_value=(True, True, ""))
    @patch("helper_client.HelperClient.is_available", side_effect=[False, True])
    def test_repairs_and_waits_for_helper(self, mock_available, mock_ensure):
        ok, info = HelperClient.ensure_available(timeout_ms=1000)

        assert ok is True
        assert info == ""
        assert mock_available.call_args_list == [call(timeout_ms=800), call(timeout_ms=800)]
        mock_ensure.assert_called_once_with()

    @patch(
        "helper_client.HelperClient.ensure_enabled",
        return_value=(False, False, "helper missing"),
    )
    @patch("helper_client.HelperClient.is_available", return_value=False)
    def test_returns_repair_error(self, _mock_available, _mock_ensure):
        ok, info = HelperClient.ensure_available(timeout_ms=1000)

        assert ok is False
        assert info == "helper missing"

    @patch("helper_client.HelperClient._call", return_value="something else")
    def test_unavailable_wrong_reply(self, _mock):
        assert HelperClient.is_available() is False


class TestApplyLayout:
    @patch("helper_client.HelperClient._call")
    def test_ok_returns_steps(self, mock_call):
        mock_call.return_value = '{"ok":true,"steps":["disable a","enable b"],"error":""}'
        ok, msg = HelperClient.apply_layout(["b@x"], reload=["b@x"])
        assert ok is True
        assert "disable a" in msg and "enable b" in msg

    @patch("helper_client.HelperClient._call")
    def test_helper_reported_error(self, mock_call):
        mock_call.return_value = '{"ok":false,"steps":[],"error":"boom"}'
        ok, msg = HelperClient.apply_layout(["b@x"])
        assert ok is False
        assert msg == "boom"

    @patch("helper_client.HelperClient._call", return_value=None)
    def test_call_failed(self, _mock):
        ok, _msg = HelperClient.apply_layout(["b@x"])
        assert ok is False

    @patch("helper_client.HelperClient._call")
    def test_payload_shape(self, mock_call):
        mock_call.return_value = '{"ok":true,"steps":[],"error":""}'
        HelperClient.apply_layout(["a@x", "", "b@y"], reload=["a@x"], step_ms=200)
        # second positional arg to _call is the (s) variant carrying the JSON
        import json

        variant = mock_call.call_args.args[1]
        payload = json.loads(variant.unpack()[0])
        assert payload["enabled"] == ["a@x", "b@y"]  # blanks filtered
        assert payload["reload"] == ["a@x"]
        assert payload["step_ms"] == 200


class TestReloadExtension:
    @patch("helper_client.HelperClient._call", return_value='{"ok":true,"uuid":"kiwi@kemma"}')
    def test_returns_helper_result(self, _mock):
        assert HelperClient.reload_extension("kiwi@kemma") is True

    @patch("helper_client.HelperClient._call", return_value='{"ok":false,"error":"busy"}')
    def test_rejects_helper_error(self, _mock):
        assert HelperClient.reload_extension("kiwi@kemma") is False


class TestNotificationPosition:
    @patch("helper_client.HelperClient._call")
    def test_applies_position(self, mock_call):
        mock_call.return_value = '{"ok":true,"position":"bottom-right"}'

        ok, position = HelperClient.set_notification_position("bottom-right")

        assert ok is True
        assert position == "bottom-right"
        assert mock_call.call_args.args[0] == "SetNotificationPosition"
        assert mock_call.call_args.args[1].unpack()[0] == "bottom-right"

    @patch("helper_client.HelperClient._call")
    def test_returns_helper_error(self, mock_call):
        mock_call.return_value = '{"ok":false,"error":"busy"}'

        ok, message = HelperClient.set_notification_position("top-center")

        assert ok is False
        assert message == "busy"


def test_helper_uuid_constant():
    assert HELPER_UUID == "layout-switcher-helper@communitybig.org"
    assert LEGACY_HELPER_UUID == "layout-switcher-helper@bigcommunity.org"


def test_owned_extension_uuid_migrations():
    assert COMMUNITY_MENU_UUID == "community-menu@communitybig.org"
    assert LEGACY_COMMUNITY_MENU_UUID == "community-menu@bigcommunity.org"
    assert BIG_SHOT_UUID == "big-shot@communitybig.org"
    assert LEGACY_BIG_SHOT_UUID == "big-shot@bigcommunity.org"
    assert COMMUNITY_DOCK_UUID == "community-dock@communitybig.org"
    assert LEGACY_DASH_TO_DOCK_UUID == "dash-to-dock@micxgx.gmail.com"
    assert COMMUNITY_PANEL_UUID == "community-panel@communitybig.org"
    assert LEGACY_DASH_TO_PANEL_UUID == "dash-to-panel@jderose9.github.com"
