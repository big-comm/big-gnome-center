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
    assert "33 switch transaction scenarios passed" in result.stdout


def test_success_path_never_rewrites_shell_membership():
    source = (
        Path(__file__).parents[1]
        / "usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org"
        / "switchTransaction.js"
    ).read_text()
    success = source.split("const completion = await host.complete(request);", 1)[1]
    success = success.split("} catch (error) {", 1)[0]

    assert "dconf', 'write" not in success
    assert "this._verifyLive(request.enabled" in success


def test_owned_switch_batches_each_dconf_mutation_phase():
    helper = (
        Path(__file__).parents[1]
        / "usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org"
        / "extension.js"
    ).read_text()
    transaction = (
        Path(__file__).parents[1]
        / "usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org"
        / "switchTransaction.js"
    ).read_text()

    assert "dconf_batch.py" in helper
    assert "GLib.spawn_async(" in helper
    assert "GLib.child_watch_add(" in helper
    assert "Gio.Subprocess.new" not in helper
    assert "mutate: (branches, input) => this._runDconfBatch" in helper
    assert "restoreValues: (paths, input) => this._runDconfBatch" in helper
    assert "await host.mutate(request.branches, request.settings)" in transaction
    assert "await this.host.restoreValues(reset, serialize(saved))" in transaction
    assert "host.run(['dconf', 'reset'" not in transaction


def test_python_ignores_in_shell_writer_advertisement(monkeypatch):
    client = layout_applier.HelperClient
    monkeypatch.setattr(client, "ping_info", lambda: {
        "ownedSwitch": True, "allowInShellDconf": True,
        "uuid": helper_client.HELPER_UUID,
    })
    monkeypatch.setattr(layout_applier.LayoutApplier, "_enabled_extensions", lambda: [])
    monkeypatch.setattr(
        layout_applier.LayoutApplier, "_managed_extension_subdirs", lambda _: ["owned"]
    )
    call = Mock(side_effect=AssertionError("in-Shell writer used"))
    monkeypatch.setattr(client, "apply_switch", call)
    begin = Mock(return_value=(True, ""))
    complete = Mock(return_value=(True, "done"))
    monkeypatch.setattr(client, "begin_switch", begin)
    monkeypatch.setattr(client, "complete_switch", complete)
    monkeypatch.setattr(client, "reload_extension", Mock(return_value=True))
    monkeypatch.setattr(layout_applier.ShellReloader, "list_extensions_state", lambda: {})
    command = Mock(return_value=(True, ""))
    monkeypatch.setattr(layout_applier, "run_cmd", command)
    data = (
        "[org/gnome/shell]\nenabled-extensions=['app']\ndisabled-extensions=[]\n\n"
        "[org/example]\nvalue=true\n"
    )
    result = layout_applier.LayoutApplier._apply_via_helper_v7(data, layout_label="Desk UX")
    assert result == (True, "done")
    call.assert_not_called()
    begin.assert_called_once()
    complete.assert_called_once_with([helper_client.HELPER_UUID, "app"])
    assert any(
        len(c.args[0]) > 1 and c.args[0][1].endswith("dconf_batch.py")
        for c in command.call_args_list
    )
    assert not any(c.args[0][:2] == ["dconf", "load"] for c in command.call_args_list)


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
