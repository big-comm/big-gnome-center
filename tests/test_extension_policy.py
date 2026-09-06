# SPDX-License-Identifier: MIT
"""Bundled extension removal guards and UI controls."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from constants import tr
from extension_manager import ExtMgr
from extension_policy import BUNDLED_EXTENSION_UUIDS, BUNDLED_REMOVAL_ERROR
from helper_client import HELPER_UUID
from system_extension_remover import remove_extension
from ui.page_extensions import ExtensionsPage

ROOT = Path(__file__).resolve().parents[1]


def test_policy_matches_every_shipped_extension():
    extensions = ROOT / 'usr/share/gnome-shell/extensions'
    assert BUNDLED_EXTENSION_UUIDS == {
        metadata.parent.name for metadata in extensions.glob('*/metadata.json')
    }


@pytest.mark.parametrize('uuid', sorted(BUNDLED_EXTENSION_UUIDS))
@pytest.mark.parametrize('location', ['user', 'system'])
def test_manager_refuses_bundled_removal_without_side_effects(tmp_path, uuid, location):
    target = tmp_path / location / uuid
    target.mkdir(parents=True)
    marker = target / 'metadata.json'
    marker.write_text('{}')
    with (
        patch('extension_manager.EXT_USER_DIR', tmp_path / 'user'),
        patch('extension_manager.EXT_SYS_DIR', tmp_path / 'system'),
        patch('extension_manager.run_cmd') as command,
        patch('shell_reloader.ShellReloader.apply_extension_state') as toggle,
        patch('shell_reloader.ShellReloader.reload_all') as reload,
    ):
        assert not ExtMgr.can_remove(uuid)
        assert ExtMgr.remove(uuid) == (False, BUNDLED_REMOVAL_ERROR)
        command.assert_not_called()
        toggle.assert_not_called()
        reload.assert_not_called()
    assert marker.read_text() == '{}'


@pytest.mark.parametrize('uuid', sorted(BUNDLED_EXTENSION_UUIDS))
@pytest.mark.parametrize('symlink', [False, True])
def test_privileged_remover_preserves_bundled_targets(tmp_path, uuid, symlink):
    target = tmp_path / uuid
    if symlink:
        outside = tmp_path / 'outside'
        outside.mkdir()
        target.symlink_to(outside, target_is_directory=True)
    else:
        target.mkdir()
    marker = target / 'metadata.json'
    marker.write_text('{}')
    with pytest.raises(ValueError, match=BUNDLED_REMOVAL_ERROR):
        remove_extension(uuid, tmp_path)
    assert marker.read_text() == '{}'
    assert target.is_symlink() == symlink


@pytest.mark.parametrize('uuid', [
    'big-shot@communitybig.org', 'example@test.org', 'copyous@boerdereinar.dev',
])
def test_separate_extensions_remain_removable(uuid):
    assert ExtMgr.can_remove(uuid)


@pytest.mark.parametrize('uuid', sorted(BUNDLED_EXTENSION_UUIDS) + ['example@test.org'])
def test_installed_row_hides_only_bundled_trash_buttons(uuid):
    page = SimpleNamespace(_updates={})
    extension = {'uuid': uuid, 'name': uuid, 'enabled': True}
    with patch('ui.page_extensions.Gtk') as gtk:
        ExtensionsPage._make_installed_row(page, extension)
        trash = [call for call in gtk.Button.call_args_list
                 if call.kwargs.get('icon_name') == 'user-trash-symbolic']
        assert len(trash) == int(uuid not in BUNDLED_EXTENSION_UUIDS)
        gtk.Switch.assert_called_once()
        if uuid == HELPER_UUID:
            gtk.Switch.return_value.set_sensitive.assert_called_once_with(False)
        else:
            gtk.Switch.return_value.set_sensitive.assert_not_called()
            gtk.Switch.return_value.connect.assert_called_once()


@pytest.mark.parametrize('uuid', sorted(BUNDLED_EXTENSION_UUIDS) + ['example@test.org'])
def test_featured_cards_hide_bundled_removal(uuid):
    extension = {'uuid': uuid, 'name': uuid}
    with patch('ui.page_extensions.Gtk') as gtk:
        ExtensionsPage._build_feat_installed(
            SimpleNamespace(), MagicMock(), extension, MagicMock(), True,
        )
        remove = [call for call in gtk.Button.call_args_list
                  if call.kwargs.get('label') == tr('Remove')]
        assert len(remove) == int(uuid not in BUNDLED_EXTENSION_UUIDS)


@pytest.mark.parametrize('uuid', sorted(BUNDLED_EXTENSION_UUIDS))
def test_bundled_removal_cannot_open_confirmation(uuid):
    with patch('ui.page_extensions.Adw.AlertDialog') as dialog:
        ExtensionsPage._confirm_remove(SimpleNamespace(), uuid, uuid)
        dialog.assert_not_called()
