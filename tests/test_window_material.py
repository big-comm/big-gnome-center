"""Preserve user CSS while managing native window backgrounds."""

from pathlib import Path

import pytest

import window_material as material


def paths(tmp_path):
    directory = tmp_path / "gtk-4.0"
    directory.mkdir()
    return directory / "gtk.css", directory / material.NAME


@pytest.mark.parametrize("original", [
    b"", b"/* User theme */\r\nlabel { color: red; }", b"\xef\xbb\xbf/* UTF-8 */",
])
def test_round_trip_preserves_user_css(tmp_path, original):
    entry, target = paths(tmp_path)
    entry.write_bytes(original)
    entry.chmod(0o640)
    material.sync_styles(tmp_path, True)
    assert entry.read_bytes().count(material.IMPORT) == 1
    assert entry.stat().st_mode & 0o777 == 0o640
    material.sync_styles(tmp_path, True, 80)
    assert entry.read_bytes().count(material.IMPORT) == 1
    material.sync_styles(tmp_path, False)
    assert entry.read_bytes() == original
    assert target.read_bytes() == material.OWNER


def test_preserves_edits_while_enabled(tmp_path):
    material.sync_styles(tmp_path, True)
    entry = tmp_path / "gtk-4.0/gtk.css"
    user = b"\nbutton { padding: 3px; }\n"
    entry.write_bytes(entry.read_bytes() + user)
    material.sync_styles(tmp_path, False)
    assert entry.read_bytes() == user


def test_does_not_rewrite_unchanged_files(tmp_path):
    material.sync_styles(tmp_path, True)
    entry = tmp_path / "gtk-4.0/gtk.css"
    before = entry.stat().st_mtime_ns
    material.sync_styles(tmp_path, True)
    assert entry.stat().st_mtime_ns == before


def test_disabled_install_leaves_missing_config_untouched(tmp_path):
    material.sync_styles(tmp_path, False)
    assert not (tmp_path / "gtk-4.0").exists()


@pytest.mark.parametrize("which", ["gtk.css", material.NAME])
def test_refuses_file_symlinks(tmp_path, which):
    paths(tmp_path)
    theme = tmp_path / "theme.css"
    theme.write_text("/* External theme */")
    (tmp_path / "gtk-4.0" / which).symlink_to(theme)
    with pytest.raises(ValueError, match="symlink"):
        material.sync_styles(tmp_path, True)
    assert theme.read_text() == "/* External theme */"


def test_refuses_directory_symlink(tmp_path):
    theme = tmp_path / "theme"
    theme.mkdir()
    (tmp_path / "gtk-4.0").symlink_to(theme)
    with pytest.raises(ValueError, match="symlink"):
        material.sync_styles(tmp_path, True)
    assert list(theme.iterdir()) == []


def test_refuses_unowned_style(tmp_path):
    entry, target = paths(tmp_path)
    target.write_text("/* User file */")
    with pytest.raises(ValueError, match="unowned"):
        material.sync_styles(tmp_path, True)
    assert not entry.exists()
    assert target.read_text() == "/* User file */"


def test_edited_import_is_preserved_but_disable_empties_owned_sheet(tmp_path):
    material.sync_styles(tmp_path, True)
    entry = tmp_path / "gtk-4.0/gtk.css"
    edited = entry.read_bytes().replace(b"END Big", b"Edited END Big")
    entry.write_bytes(edited)
    with pytest.raises(ValueError, match="edited"):
        material.sync_styles(tmp_path, True)
    material.sync_styles(tmp_path, False)
    assert entry.read_bytes() == edited
    assert (entry.parent / material.NAME).read_bytes() == material.OWNER


def test_concurrent_edit_is_not_overwritten(tmp_path):
    entry, _ = paths(tmp_path)
    entry.write_bytes(b"new user content")
    with pytest.raises(ValueError, match="changed"):
        material.replace_checked(entry, b"replacement", b"old content")
    assert entry.read_bytes() == b"new user content"
    assert not list(entry.parent.glob(".bgc-windows-*"))


def test_styles_only_target_validated_backgrounds():
    css = material.render_css(37).decode()
    assert "window.nautilus-window" in css
    assert "window.big-gnome-center" in css
    assert "window.org-gnome-TextEditor textview text" in css
    assert "backdrop-filter: blur(30px)" in css
    assert "prefers-contrast: no-preference" in css
    assert "opacity:" not in css
    assert "\n        color:" not in css
    assert "* {" not in css
    assert "@window_bg_color" in css


def test_extension_gates_styles_and_cleans_up():
    base = Path(__file__).resolve().parents[1]
    extension = base / "usr/share/gnome-shell/extensions/frosted-glass@communitybig.org"
    source = (extension / "extension.js").read_text()
    assert "FULL_BACKEND_AVAILABLE && wayland &&" in source
    assert "global.context?.get_wayland_compositor?.()" in source
    assert "config.enabled && config.windowsEnabled && config.mode === 'dynamic'" in source
    assert "this._windowStyles?.destroy()" in source
    assert "this._windowStyles ??=" in source


@pytest.mark.parametrize("window_class", [
    "big-audio-converter", "big-video-converter", "big-hardware-info",
    "big-network-info", "bigocrpdf", "bigocrimage", "bigocrpdf-editor",
    "biglinux-webapps", "biglinux-settings", "bigrecorder",
    "community-release", "biglinux-microphone",
    "big-driver-manager",
])
def test_application_profiles_use_exclusive_window_classes(window_class):
    css = material.render_css(37).decode()
    assert f"window.{window_class}" in material.SELECTORS
    assert "\n    window {" not in css
    assert "drawingarea" not in css
    assert "picture" not in css


def test_terminal_profile_preserves_its_own_palette_and_transparency():
    css = material.render_css(37).decode()
    assert "ashyterm-window" not in material.WINDOW_CLASSES
    terminal = css.split("window.ashyterm-window {", 1)[1].split("}", 1)[0]
    assert terminal.strip() == "backdrop-filter: blur(30px);"


def test_camera_profile_preserves_preview_and_opacity():
    css = material.render_css(37).decode()
    assert "bgc-bigcam" not in material.WINDOW_CLASSES
    camera = css.split("window.bgc-bigcam {", 1)[1].split("}", 1)[0]
    assert camera.strip() == "backdrop-filter: blur(30px);"
    assert "window.bigcam" not in css
    assert "preview-picture" not in css
    assert "video-bg" not in css


def test_embedded_dialogs_restore_background_palette():
    css = material.render_css(37).decode()
    for name in material.WINDOW_CLASSES:
        assert f"window.{name} dialog" in material.DIALOG_SELECTORS
    dialog = css.split(material.DIALOG_SELECTORS + " {", 1)[1].split("}", 1)[0]
    for variable in (
        "window-bg-color", "view-bg-color", "headerbar-bg-color",
        "headerbar-backdrop-color", "sidebar-bg-color", "sidebar-backdrop-color",
    ):
        assert f"--{variable}: @{variable.replace('-', '_')};" in dialog
    assert "background-color:" not in dialog
    assert "backdrop-filter:" not in dialog


def test_recorder_chrome_uses_inherited_palette():
    css = material.render_css(37).decode()
    chrome = css.split("window.bigrecorder .app-bg,", 1)[1].split("}", 1)[0]
    assert "background-color: var(--window-bg-color);" in chrome
    assert "window.bigrecorder headerbar" in chrome


def test_old_gtk_does_not_enable_styles(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["window_material.py", "--enable"])
    monkeypatch.setattr(material, "gtk_supports_blur", lambda: False)
    material.sync_styles(tmp_path, True)
    assert material.main() == 0
    assert (tmp_path / "gtk-4.0/gtk.css").read_bytes() == b""
