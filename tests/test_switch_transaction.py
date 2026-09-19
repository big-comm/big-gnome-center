# SPDX-License-Identifier: MIT
"""Owned helper switching and compatibility recovery."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

import helper_client
import layout_applier


def test_switch_transaction_scenarios():
    result = subprocess.run(
        ["node", str(Path(__file__).with_name("switch_transaction.mjs"))],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "32 switch transaction scenarios passed" in result.stdout


@pytest.mark.parametrize("success", [True, False])
def test_owned_helper_is_the_only_settings_writer(monkeypatch, success):
    client = layout_applier.HelperClient
    monkeypatch.setattr(client, "ping_info", lambda: {
        "ownedSwitch": True, "uuid": helper_client.HELPER_UUID,
    })
    monkeypatch.setattr(layout_applier.LayoutApplier, "_enabled_extensions", lambda: [])
    monkeypatch.setattr(
        layout_applier.LayoutApplier, "_managed_extension_subdirs", lambda _: ["owned"]
    )
    call = Mock(return_value=(success, "result"))
    monkeypatch.setattr(client, "apply_switch", call)
    legacy = Mock(side_effect=AssertionError("legacy path entered"))
    monkeypatch.setattr(client, "begin_switch", legacy)
    monkeypatch.setattr(layout_applier, "run_cmd", legacy)
    finish = Mock(return_value=(True, "result"))
    monkeypatch.setattr(layout_applier.LayoutApplier, "_finish_cleanroom", finish)
    data = "[org/gnome/shell]\nenabled-extensions=['app']\ndisabled-extensions=[]\n"
    result = layout_applier.LayoutApplier._apply_via_helper_v7(data, layout_label="Desk UX")
    assert result == (success, "result")
    payload = call.call_args.args[0]
    assert payload["enabled"] == [helper_client.HELPER_UUID, "app"]
    assert payload["branches"] == ["/org/gnome/shell/extensions/owned/"]
    assert payload["label"] == "Desk UX"
    assert "enabled-extensions=" not in payload["settings"]
    assert finish.call_count == int(success)


@pytest.mark.parametrize("reply", [
    None, "garbage", "[]", '{"ok":"yes"}', '{"ok":true,"steps":null}',
    '{"ok":true,"steps":[1]}',
])
def test_ambiguous_reply_requests_owned_recovery(monkeypatch, reply):
    monkeypatch.setattr(helper_client.HelperClient, "_call", Mock(return_value=reply))
    abort = Mock(return_value=True)
    monkeypatch.setattr(helper_client.HelperClient, "abort_switch", abort)
    ok, message = helper_client.HelperClient.apply_switch({"settings": ""})
    assert not ok and "recovery requested" in message
    abort.assert_called_once_with(timeout_ms=150000)


@pytest.mark.parametrize("ok", [True, False])
def test_owned_reply_preserves_failure(monkeypatch, ok):
    call = Mock(return_value=json.dumps({
        "ok": ok, "steps": ["done"], "error": "recovery incomplete",
    }))
    monkeypatch.setattr(helper_client.HelperClient, "_call", call)
    abort = Mock(side_effect=AssertionError("second recovery would race"))
    monkeypatch.setattr(helper_client.HelperClient, "abort_switch", abort)
    success, message = helper_client.HelperClient.apply_switch({"settings": ""})
    assert success is ok
    assert message == ("done" if ok else "recovery incomplete")
    assert call.call_args.args[0] == "ApplySwitch"
    assert call.call_args.args[2] == 330000
