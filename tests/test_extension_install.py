# SPDX-License-Identifier: MIT
"""Remote UUIDs use the validated downloader, never the local bundle CLI."""

from unittest.mock import Mock

import pytest

import extension_manager as manager


@pytest.mark.parametrize("ego_id", [0, 42])
@pytest.mark.parametrize("cli_available", [False, True])
def test_remote_install_uses_download_even_without_ego_id(monkeypatch, ego_id, cli_available):
    download = Mock(return_value=(True, "download-url"))
    command = Mock(return_value=(True, "unexpected CLI success"))
    monkeypatch.setattr(manager.ExtMgr, "_install_from_ego", download)
    monkeypatch.setattr(manager, "run_cmd", command)
    monkeypatch.setattr(
        manager.shutil, "which", lambda name: "/usr/bin/" + name if cli_available else None
    )
    assert manager.ExtMgr.install("remote@example.org", ego_id) == (True, "ego-download")
    download.assert_called_once_with("remote@example.org", ego_id)
    command.assert_not_called()


@pytest.mark.parametrize(
    "error", ["network unavailable", "incompatible metadata", "invalid schema"]
)
def test_rejected_download_does_not_fall_back_to_unvalidated_cli(monkeypatch, error):
    monkeypatch.setattr(manager.ExtMgr, "_install_from_ego", lambda *args: (False, error))
    monkeypatch.setattr(manager.shutil, "which", lambda name: "/usr/bin/" + name)
    command = Mock(return_value=(True, "unexpected success"))
    monkeypatch.setattr(manager, "run_cmd", command)
    assert manager.ExtMgr.install("remote@example.org", 0) == (False, error)
    command.assert_not_called()
