# SPDX-License-Identifier: MIT
"""The persistence journal must enclose every live application route."""

import pytest

import layout_applier as module
import layout_persistence
from tests.test_layout_persistence_recovery import DATA, OLD
from tests.test_layout_persistence_recovery import session as persistence_session

session = persistence_session
refresh_sync_monitor = module.LayoutApplier._refresh_sync_monitor


def test_missing_protocol_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(layout_persistence, 'PROTOCOL_MODULE', tmp_path / 'missing')
    with pytest.raises(OSError, match='Update comm-gnome-config'):
        layout_persistence.open_store(tmp_path / 'settings.gnome')


@pytest.mark.parametrize('success', [True, False])
def test_journal_encloses_helper_and_finalizes_under_lock(session, success):
    store = module.open_store.return_value

    def begin(*args, **kwargs):
        store.begin.assert_called_once()
        assert module._SYNC_LOCK_PATH.exists()
        return success, 'begin failed'

    session['begin_switch'].side_effect = begin
    result = module.LayoutApplier.load_dconf_safely(DATA)
    assert result[0] == success
    if success:
        store.publish.assert_called_once()
        store.abort.assert_not_called()
    else:
        store.abort.assert_called_once()
        store.publish.assert_not_called()
        assert module.SETTINGS_GNOME.read_text() == OLD


def test_journal_write_failure_prevents_teardown(session):
    module.open_store.return_value.begin.side_effect = OSError('disk full')
    with pytest.raises(OSError, match='disk full'):
        module.LayoutApplier.load_dconf_safely(DATA)
    session['begin_switch'].assert_not_called()
    assert module.SETTINGS_GNOME.read_text() == OLD


def test_failed_commit_reports_failure_and_restores_files(session):
    session['begin_switch'].return_value = True, ''
    module.open_store.return_value.publish.side_effect = OSError('cannot commit')
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok and 'cannot commit' in message
    assert module.SETTINGS_GNOME.read_text() == OLD


@pytest.mark.parametrize('key', ['disabled-extensions', 'enabled-extensions'])
def test_failed_final_extension_write_cannot_commit(session, key):
    session['begin_switch'].return_value = True, ''

    def command(argv, **kwargs):
        if argv[:3] == ['dconf', 'write', '/org/gnome/shell/' + key]:
            return False, 'final write failed'
        return True, ''

    session['run_cmd'].side_effect = command
    ok, message = module.LayoutApplier.load_dconf_safely(DATA)
    assert not ok and 'final write failed' in message
    module.open_store.return_value.publish.assert_not_called()
    module.open_store.return_value.abort.assert_called_once()
    assert module.SETTINGS_GNOME.read_text() == OLD


def test_monitor_restart_failure_prevents_teardown_and_file_writes(session, monkeypatch):
    monkeypatch.setattr(module.LayoutApplier, '_refresh_sync_monitor', refresh_sync_monitor)
    session['run_cmd'].return_value = False, 'restart denied'
    with pytest.raises(OSError, match='cannot refresh dconf synchronization'):
        module.LayoutApplier.load_dconf_safely(DATA)
    session['begin_switch'].assert_not_called()
    module.open_store.assert_not_called()
    assert module.SETTINGS_GNOME.read_text() == OLD
