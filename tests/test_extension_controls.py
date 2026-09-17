# SPDX-License-Identifier: MIT
"""Extension state contracts and malformed installed metadata."""

import json
from unittest.mock import patch

import pytest

from extension_manager import ExtMgr
from shell_reloader import ShellReloader


@pytest.mark.parametrize("disabled", [False, True])
def test_global_toggle_uses_shell_key_without_reload(disabled):
    key = "/org/gnome/shell/disable-user-extensions"
    with (
        patch("extension_manager.dconf_write", return_value=(True, "")) as write,
        patch("extension_manager.dconf_read", return_value=str(disabled).lower()) as read,
        patch.object(ShellReloader, "reload_all") as reload,
    ):
        assert ExtMgr.disable_all_globally(disabled)[0]
        assert ExtMgr.all_globally_enabled() is not disabled
    write.assert_called_once_with(key, str(disabled).lower())
    assert all(call.args == (key,) for call in read.call_args_list)
    reload.assert_not_called()


def test_global_toggle_preserves_write_failure():
    with patch("extension_manager.dconf_write", return_value=(False, "locked")):
        assert ExtMgr.disable_all_globally(True) == (False, "locked")


@pytest.mark.parametrize("enable", [False, True])
@pytest.mark.parametrize("reply", ["(true,)", "( true, )"])
def test_accepted_extension_toggle_does_not_reload(enable, reply):
    with (
        patch("shell_reloader.run_cmd", return_value=(True, reply)) as command,
        patch.object(ShellReloader, "reload_extension") as reload,
        patch.object(ExtMgr, "_set_enabled_gsettings") as fallback,
    ):
        assert ShellReloader.apply_extension_state("test@example.org", enable)[0]
    assert command.call_count == 1
    assert command.call_args.args[0][-2].endswith(
        ".EnableExtension" if enable else ".DisableExtension"
    )
    reload.assert_not_called()
    fallback.assert_not_called()


@pytest.mark.parametrize("reply", ["(false,)", "()", "garbage", "(1,)", "('true',)"])
def test_rejected_or_invalid_reply_never_falls_back(reply):
    with (
        patch("shell_reloader.run_cmd", return_value=(True, reply)),
        patch.object(ExtMgr, "_set_enabled_gsettings") as fallback,
    ):
        assert not ShellReloader.enable_extension_dbus("test@example.org", True)[0]
        assert not ShellReloader.apply_extension_state("test@example.org", True)[0]
    fallback.assert_not_called()


def test_unavailable_dbus_keeps_settings_fallback_without_shell_reload():
    with (
        patch("shell_reloader.run_cmd", return_value=(False, "service unavailable")),
        patch.object(ExtMgr, "_set_enabled_gsettings", return_value=(True, "")) as fallback,
        patch.object(ShellReloader, "reload_all") as reload,
    ):
        assert ShellReloader.apply_extension_state("test@example.org", True)[0]
    fallback.assert_called_once_with("test@example.org", True)
    reload.assert_not_called()


@pytest.mark.parametrize("metadata", [None, [], True, 12, "text"])
def test_non_object_metadata_cannot_break_extension_listing(tmp_path, metadata):
    uuid = "test@example.org"
    extension = tmp_path / uuid
    extension.mkdir()
    (extension / "metadata.json").write_text(json.dumps(metadata))
    with (
        patch("extension_manager.EXT_USER_DIR", tmp_path),
        patch("extension_manager.EXT_SYS_DIR", tmp_path / "absent"),
        patch.object(ExtMgr, "enabled_list", return_value=[]),
    ):
        result = ExtMgr.list_installed()
        assert ExtMgr.installed_version(uuid) == 0
    assert len(result) == 1
    assert result[0]["uuid"] == uuid
    assert result[0]["name"] == uuid


def test_metadata_cannot_redirect_identity_or_publish_non_text_fields(tmp_path):
    uuid = "test@example.org"
    extension = tmp_path / uuid
    extension.mkdir()
    (extension / "metadata.json").write_text(json.dumps({
        "uuid": "different@example.org", "name": [], "description": {},
        "url": 4, "version": [],
    }))
    (tmp_path / ".test@example.org.staging").mkdir()
    with (
        patch("extension_manager.EXT_USER_DIR", tmp_path),
        patch("extension_manager.EXT_SYS_DIR", tmp_path / "absent"),
        patch.object(ExtMgr, "enabled_list", return_value=[uuid]),
    ):
        result = ExtMgr.list_installed()
    assert len(result) == 1
    assert result[0] == {
        "uuid": uuid, "name": uuid, "description": "", "url": "", "version": "",
        "enabled": True, "user": True, "has_prefs": False,
    }
