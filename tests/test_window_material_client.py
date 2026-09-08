"""Live material lifetime without restarting cooperating windows."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import window_material as material
import window_material_client as client


@pytest.fixture
def live(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(client, "gtk_supports_blur", lambda: True)
    provider = Mock()
    style = Mock()
    monkeypatch.setattr(client, "Gtk", SimpleNamespace(
        CssProvider=lambda: provider, StyleContext=style,
        STYLE_PROVIDER_PRIORITY_USER=800,
    ))
    monkeypatch.setattr(client.WindowMaterialClient, "_watch", lambda self: None)
    window = Mock()
    instance = client.WindowMaterialClient(window, "big-gnome-center")
    yield instance, window, provider, style, tmp_path
    instance.close()


def test_live_enable_disable_enable_reuses_window(live):
    instance, window, provider, style, config = live
    for enabled, opacity in [(True, 37), (False, 37), (True, 80), (False, 80)]:
        window.reset_mock()
        material.sync_styles(config, enabled, opacity)
        instance._refresh()
        window.remove_css_class.assert_called_once_with("big-gnome-center")
        if enabled:
            window.add_css_class.assert_called_once_with("big-gnome-center")
            provider.load_from_string.assert_called_with(material.render_css(opacity).decode())
        else:
            window.add_css_class.assert_not_called()
            provider.load_from_string.assert_called_with("")
    assert style.add_provider_for_display.call_count == 1


@pytest.mark.parametrize("content", [b"unowned", b"\xff", material.OWNER])
def test_empty_invalid_or_unowned_sheet_removes_material(live, content):
    instance, window, provider, style, config = live
    instance._path.parent.mkdir()
    instance._path.write_bytes(content)
    window.reset_mock()
    instance._refresh()
    window.add_css_class.assert_not_called()
    provider.load_from_string.assert_called_with("")


def test_destroy_cancels_pending_reload(live, monkeypatch):
    instance, window, provider, style, config = live
    idle = Mock(return_value=12)
    remove = Mock()
    monkeypatch.setattr(client.GLib, "idle_add", idle)
    monkeypatch.setattr(client.GLib, "source_remove", remove)
    instance._monitor = Mock()
    instance._changed(None, None, None, None)
    instance._changed(None, None, None, None)
    idle.assert_called_once()
    instance.close()
    remove.assert_called_once_with(12)
    style.remove_provider_for_display.assert_called_once()
    instance._changed(None, None, None, None)
    assert idle.call_count == 1


def test_old_gtk_does_not_install_live_provider(monkeypatch):
    monkeypatch.setattr(client, "gtk_supports_blur", lambda: False)
    provider = Mock()
    monkeypatch.setattr(client, "Gtk", SimpleNamespace(CssProvider=provider))
    instance = client.WindowMaterialClient(Mock(), "big-gnome-center")
    provider.assert_not_called()
    instance.close()


def test_public_attachment_releases_client_when_window_is_destroyed(monkeypatch):
    controller = Mock()
    factory = Mock(return_value=controller)
    monkeypatch.setattr(client, "WindowMaterialClient", factory)
    window = Mock()
    assert client.attach_window_material(window, "example") is controller
    factory.assert_called_once_with(window, "example")
    signal, callback = window.connect.call_args.args
    assert signal == "destroy"
    callback(window)
    controller.close.assert_called_once_with(remove_class=False)


def test_destroy_cleanup_does_not_access_disposed_window(live):
    instance, window, provider, style, config = live
    window.get_display.side_effect = RuntimeError("disposed window")
    window.remove_css_class.side_effect = RuntimeError("disposed window")
    instance.close(remove_class=False)
    style.remove_provider_for_display.assert_called_once()
    instance.close()
