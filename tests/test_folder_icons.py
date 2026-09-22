# SPDX-License-Identifier: MIT
"""Native folder metadata and accent-aware icon selection."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from gi.repository import Gio

import folder_icons as model
from folder_accent import BASES, build_theme

SVG = "<svg><style>.ColorScheme-Highlight {color:#3584e4;}</style></svg>"


@pytest.fixture
def catalog(tmp_path):
    root = tmp_path / "icons"
    places = root / BASES[0] / "scalable/places"
    places.mkdir(parents=True)
    for name in ("folder", "folder-git", "folder-cloud", "folder-open", "folder-drag-accept"):
        (places / f"{name}.svg").write_text(SVG)
    (places / "folder-projects.svg").symlink_to("folder-git.svg")
    (places / "folder-broken.svg").symlink_to("missing.svg")
    (places / "folder-red.svg").write_text('<svg fill="#ff0000"/>')
    (places / "user-trash.svg").write_text(SVG)
    (places.parent.parent / "index.theme").write_text(
        "[Icon Theme]\nDirectories=scalable/places\n"
        "[scalable/places]\nContext=Places\nType=Scalable\nSize=48\n"
    )
    return root, model.available_icons(BASES[0], [root])


def test_catalog_follows_accents_without_duplicate_or_fixed_artwork(catalog, tmp_path):
    root, choices = catalog
    assert {icon.name for icon in choices} == {"folder", "folder-git", "folder-cloud"}
    git = next(icon for icon in choices if icon.name == "folder-git")
    assert set(git.aliases) == {"folder-git", "folder-projects"}
    (root / BASES[0] / "scalable/places/folder-broken.svg").unlink()
    overlay = build_theme(BASES[0], "orange", [root], tmp_path / "output")
    assert model.available_icons(overlay["theme"], [root]) == choices
    assert model.available_icons("OtherTheme", [root]) == []


def test_catalog_honors_user_icon_precedence(catalog, tmp_path):
    root, choices = catalog
    user_root = tmp_path / "user-icons"
    places = user_root / BASES[0] / "scalable/places"
    places.mkdir(parents=True)
    (places / "folder-cloud.svg").write_text("<svg/>")
    assert "folder-cloud" not in {
        icon.name for icon in model.available_icons(BASES[0], [user_root, root])
    }


@pytest.mark.parametrize("alias", ["folder-git", "folder-projects"])
def test_recognizes_names_and_installed_svg_aliases(catalog, alias):
    root, choices = catalog
    metadata = {model.CUSTOM_URI: None, model.CUSTOM_NAME: alias}
    assert model.selected_icon(metadata, choices, [root]) == "folder-git"
    path = root / BASES[0] / "scalable/places" / f"{alias}.svg"
    metadata[model.CUSTOM_URI] = path.as_uri()
    metadata[model.CUSTOM_NAME] = "folder-cloud"
    assert model.selected_icon(metadata, choices, [root]) == "folder-git"


def test_personal_image_takes_precedence_and_is_not_matched_by_filename(catalog, tmp_path):
    root, choices = catalog
    personal = tmp_path / "folder-git.svg"
    personal.write_text(SVG)
    metadata = {model.CUSTOM_URI: personal.as_uri(), model.CUSTOM_NAME: "folder-cloud"}
    assert model.selected_icon(metadata, choices, [root]) is None
    metadata[model.CUSTOM_URI] = "https://example.com/folder-git.svg"
    assert model.selected_icon(metadata, choices, [root]) is None


class Folder:
    def __init__(self, metadata=None, failures=()):
        self.metadata = {key: None for key in model.ATTRIBUTES}
        self.metadata.update(metadata or {})
        self.failures = failures
        self.writes = []

    def is_native(self):
        return True

    def query_info(self, *args):
        info = Gio.FileInfo()
        info.set_file_type(Gio.FileType.DIRECTORY)
        for key, value in self.metadata.items():
            if value is not None:
                info.set_attribute_string(key, value)
        return info

    def set_attribute_string(self, key, value, *args):
        self.writes.append((key, value))
        if len(self.writes) in self.failures:
            return False
        self.metadata[key] = value
        return True

    def set_attribute(self, key, kind, value, *args):
        assert kind == Gio.FileAttributeType.INVALID and value is None
        return self.set_attribute_string(key, value)


def test_apply_converts_file_icon_without_touching_other_metadata():
    folder = Folder({model.CUSTOM_URI: "file:///icons/folder-git.svg", "metadata::emblems": "star"})
    model.save_icon(folder, "folder-git", model.read_metadata(folder))
    assert folder.metadata == {
        model.CUSTOM_NAME: "folder-git",
        model.CUSTOM_URI: None,
        "metadata::emblems": "star",
    }
    assert folder.writes[0] == (model.CUSTOM_NAME, "folder-git")


def test_restore_removes_both_overrides():
    folder = Folder({model.CUSTOM_URI: "file:///personal.svg", model.CUSTOM_NAME: "folder-git"})
    model.save_icon(folder, None, model.read_metadata(folder))
    assert all(value is None for value in folder.metadata.values())


@pytest.mark.parametrize("name", [None, "folder-git"])
@pytest.mark.parametrize("failed_write", [1, 2])
def test_write_failure_restores_original_metadata(name, failed_write):
    original = {model.CUSTOM_URI: "file:///personal.svg", model.CUSTOM_NAME: "folder-cloud"}
    folder = Folder(original, failures=(failed_write,))
    with pytest.raises(OSError):
        model.save_icon(folder, name, model.read_metadata(folder))
    assert folder.metadata == original


def test_rollback_failure_is_reported():
    folder = Folder({model.CUSTOM_URI: "file:///personal.svg"}, failures=(2, 3))
    with pytest.raises(OSError) as caught:
        model.save_icon(folder, "folder-git", model.read_metadata(folder))
    assert str(caught.value) == model.tr("Could not restore the previous folder icon.")


def test_external_change_rejects_stale_dialog_without_writing():
    folder = Folder()
    original = model.read_metadata(folder)
    folder.metadata[model.CUSTOM_URI] = "file:///new-personal.svg"
    with pytest.raises(ValueError) as caught:
        model.save_icon(folder, "folder-git", original)
    assert str(caught.value) == model.tr(
        "The folder icon changed. Close this window and try again."
    )
    assert folder.writes == []


def test_only_local_directories_are_supported(tmp_path):
    info = model.read_metadata(Gio.File.new_for_path(str(tmp_path)))
    assert info == dict.fromkeys(model.ATTRIBUTES)
    file = tmp_path / "file"
    file.touch()
    for target in (Gio.File.new_for_path(str(file)), Gio.File.new_for_uri("sftp://host/folder")):
        with pytest.raises(ValueError):
            model.read_metadata(target)


def test_launcher_and_packaging():
    root = Path(__file__).resolve().parents[1]
    launcher = root / "usr/bin/big-gnome-center-folder-icon"
    assert launcher.stat().st_mode & 0o111
    assert "'nautilus-python'" in (root / "pkgbuild/PKGBUILD").read_text()


@pytest.fixture
def provider(monkeypatch):
    """Exercise the extension contract without loading libnautilus into pytest."""

    class MenuItem:
        def __init__(self, **kwargs):
            self.props = SimpleNamespace(**kwargs)

        def connect(self, signal, callback, folder):
            self.activate = lambda: callback(self, folder)

    class Process:
        def wait_async(self, *args):
            pass

    launches = []
    reloads = []
    class Application:
        def get_active_window(self):
            return SimpleNamespace(
                activate_action=lambda name, value: reloads.append((name, value))
            )

    application = Application()

    def launch(argv, flags):
        launches.append(argv)
        return Process()

    gi = ModuleType("gi")
    gi.require_version = lambda *args: None
    repository = ModuleType("gi.repository")
    repository.Gio = SimpleNamespace(
        Subprocess=SimpleNamespace(new=launch), SubprocessFlags=SimpleNamespace(NONE=0),
        Application=SimpleNamespace(get_default=lambda: application),
    )
    repository.GLib = SimpleNamespace(Error=RuntimeError)
    repository.GObject = SimpleNamespace(GObject=type("GObject", (), {}))
    repository.Gtk = SimpleNamespace(Application=Application)
    repository.Nautilus = SimpleNamespace(
        MenuProvider=type("MenuProvider", (), {}), MenuItem=MenuItem
    )
    monkeypatch.setitem(sys.modules, "gi", gi)
    monkeypatch.setitem(sys.modules, "gi.repository", repository)
    path = Path(__file__).resolve().parents[1] / (
        "usr/share/nautilus-python/extensions/big_gnome_center_folder_icons.py"
    )
    spec = importlib.util.spec_from_file_location("folder_icon_provider_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    extension = module.BigGnomeCenterFolderIcons()
    extension._test_module = module
    extension._test_reloads = reloads
    return extension, launches


class FileInfo:
    def __init__(self, uri, directory=True, gone=False):
        self.uri, self.directory, self.gone = uri, directory, gone

    def is_gone(self):
        return self.gone

    def is_directory(self):
        return self.directory

    def get_uri_scheme(self):
        return self.uri.split(":", 1)[0]

    def get_uri(self):
        return self.uri


def test_context_actions_keep_selected_folder_separate_from_background(provider):
    extension, launches = provider
    selected = FileInfo("file:///home/test/Projects%20%26%20Notes")
    parent = FileInfo("file:///home/test")
    item = extension.get_file_items([selected])[0]
    background = extension.get_background_items(parent)[0]
    actions = {action.props.name: action for action in (item, background)}
    assert len(actions) == 2
    actions[item.props.name].activate()
    assert launches[-1] == ["/usr/bin/big-gnome-center-folder-icon", selected.uri]
    actions[background.props.name].activate()
    assert launches[-1][1] == parent.uri


@pytest.mark.parametrize(
    "files",
    [
        [],
        [FileInfo("file:///a"), FileInfo("file:///b")],
        [FileInfo("sftp://host/folder")],
        [FileInfo("file:///a", directory=False)],
        [FileInfo("file:///a", gone=True)],
    ],
)
def test_context_menu_ignores_unsupported_selections(provider, files):
    extension, launches = provider
    assert extension.get_file_items(files) == []
    assert launches == []


def test_nautilus_extension_uses_only_public_file_info_api(provider):
    extension, _ = provider
    module = extension._test_module
    source = Path(module.__file__).read_text()
    assert "observe_children" not in source
    assert "get_windows" not in source
    assert "query_info" not in source


@pytest.mark.parametrize("gone", [False, True])
def test_picker_exit_invalidates_live_folder_without_view_traversal(provider, gone):
    extension, _ = provider
    invalidations = []
    folder = SimpleNamespace(
        is_gone=lambda: gone,
        invalidate_extension_info=lambda: invalidations.append(True),
    )
    process = SimpleNamespace(wait_finish=lambda result: True)
    extension._finished(process, None, folder)
    assert invalidations == ([] if gone else [True])
    assert extension._test_reloads == ([] if gone else [("slot.reload", None)])


def test_picker_exit_tolerates_missing_active_window(provider):
    extension, _ = provider
    extension._test_module.Gio.Application.get_default = lambda: None
    folder = SimpleNamespace(is_gone=lambda: False, invalidate_extension_info=lambda: None)
    process = SimpleNamespace(wait_finish=lambda result: True)
    extension._finished(process, None, folder)


def test_folder_picker_messages_are_translated_in_every_compiled_catalog():
    import ast
    import gettext

    root = Path(__file__).resolve().parents[1]
    sources = [
        root / "usr/share/big-gnome-center/folder_icons.py",
        root / "usr/share/big-gnome-center/folder_icon_picker.py",
        root / "usr/share/nautilus-python/extensions/big_gnome_center_folder_icons.py",
    ]
    messages = set()
    for source in sources:
        for node in ast.walk(ast.parse(source.read_text())):
            if (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "tr" and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                messages.add(node.args[0].value)
    for po in (root / "usr/share/locale").glob("*.po"):
        locale = po.stem.replace("-", "_")
        translation = gettext.translation("big-gnome-center", po.parent, [locale])
        for message in messages:
            assert translation._catalog.get(message), (locale, message)
