"""Exercise real GTK and GVfs metadata in a disposable guest directory."""

import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/usr/share/big-gnome-center")
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Nautilus", "4.1")
from gi.repository import Adw, Gio, GLib, Gtk

from folder_accent import BASES, build_theme
from folder_icon_picker import FolderIconWindow
from folder_icons import CUSTOM_NAME, CUSTOM_URI, read_metadata


def pump(seconds=0.2):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


def check(condition, label):
    assert condition, label
    print("PASS", label, flush=True)


directory = Path(tempfile.mkdtemp(prefix=".bgc-folder-picker-test-", dir=Path.home()))
folder_path = directory / "Projetos com espaços e acentuação"
folder_path.mkdir()
folder = Gio.File.new_for_path(str(folder_path))
Gtk.init()
app = Adw.Application(
    application_id="org.communitybig.FolderPickerTest", flags=Gio.ApplicationFlags.NON_UNIQUE
)
app.register(None)
settings = Gtk.Settings.get_default()
settings.set_property("gtk-icon-theme-name", BASES[1])
original = read_metadata(folder)
check(not any(original.values()), "clean folder")
window = FolderIconWindow(app, folder)
window.present()
pump()
check(len(window.choices) > 50, "GTK catalog contains custom designs")
check(not window.apply.get_sensitive(), "no implicit selection on opening")
check(not window.restore.get_sensitive(), "default folder does not need restoration")
window.close()
pump()
check(read_metadata(folder) == original, "cancel does not write metadata")

source = Path("/usr/share/icons") / BASES[1] / "scalable/places/folder-git.svg"
folder.set_attribute_string(CUSTOM_URI, source.as_uri(), Gio.FileQueryInfoFlags.NONE, None)
window = FolderIconWindow(app, folder)
window.present()
pump()
check(window._selected == "folder-git", "legacy SVG recognized")
check(window.apply.get_sensitive(), "legacy conversion can be applied")
window.apply.emit("clicked")
pump(0.8)
check(
    read_metadata(folder) == {CUSTOM_URI: None, CUSTOM_NAME: "folder-git"},
    "Apply converts actual GVfs metadata to a themed name",
)

output = directory / "icons"
icon_theme = Gtk.IconTheme.get_for_display(window.get_display())
icon_theme.add_search_path(str(output))
for accent in ("orange", "green", "blue"):
    result = build_theme(BASES[1], accent, [Path("/usr/share/icons")], output)
    settings.set_property("gtk-icon-theme-name", result["theme"])
    window = FolderIconWindow(app, folder)
    window.present()
    pump()
    check(window._selected == "folder-git", accent + " retains design selection")
    paintable = icon_theme.lookup_icon("folder-git", None, 64, 1, Gtk.TextDirection.NONE, 0)
    resolved = Path(paintable.get_file().get_path())
    if accent != "blue":
        check(
            resolved.is_relative_to(output / result["theme"]), accent + " resolves accent overlay"
        )
    check(read_metadata(folder)[CUSTOM_NAME] == "folder-git", accent + " does not rewrite metadata")
    window.close()
    pump()

settings.set_property("gtk-icon-theme-name", BASES[1])
personal = directory / "folder-git.svg"
personal.write_text(source.read_text())
folder.set_attribute_string(CUSTOM_URI, personal.as_uri(), Gio.FileQueryInfoFlags.NONE, None)
window = FolderIconWindow(app, folder)
window.present()
pump()
check(window._selected is None, "personal SVG is not treated as installed icon")
window.close()
pump()
check(read_metadata(folder)[CUSTOM_URI] == personal.as_uri(), "cancel preserves personal SVG")
window = FolderIconWindow(app, folder)
window.present()
pump()
window.restore.emit("clicked")
pump(0.8)
check(not any(read_metadata(folder).values()), "Restore Default clears both GVfs overrides")

window = FolderIconWindow(app, folder)
window.present()
pump()
child = window.grid.get_first_child()
while child:
    if child.icon_name == "folder-git":
        window.grid.select_child(child)
        break
    child = child.get_next_sibling()
window.search.set_text("nuvem")
pump(0.5)
check(
    window._selected is None and not window.apply.get_sensitive(),
    "search cannot apply a hidden selection",
)
visible = []
child = window.grid.get_first_child()
while child:
    if child.get_child_visible():
        visible.append(child.icon_name)
    child = child.get_next_sibling()
check(
    "folder-cloud" in visible and len(visible) < len(window.choices),
    "localized search filters designs",
)
settings.set_property("gtk-icon-theme-name", "Adwaita")
pump()
check(not window.apply.get_sensitive() and not window.choices, "unsupported theme disables Apply")
window.close()
pump()

extension_path = "/usr/share/nautilus-python/extensions/big_gnome_center_folder_icons.py"
spec = importlib.util.spec_from_file_location("bgc_folder_extension", extension_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
provider = module.BigGnomeCenterFolderIcons()


class FileInfo:
    def is_gone(self):
        return False

    def is_directory(self):
        return True

    def get_uri_scheme(self):
        return "file"

    def get_uri(self):
        return folder.get_uri()


info = FileInfo()
items = provider.get_file_items([info])
check(
    len(items) == 1 and items[0].props.label == "Personalizar ícone da pasta…",
    "Nautilus provider exposes translated menu item",
)
check(provider.get_file_items([]) == [], "empty selection is ignored")
check(provider.get_file_items([info, info]) == [], "multiple selection is ignored")
background = provider.get_background_items(info)
check(len(background) == 1, "folder background menu is supported")
check(items[0].props.name != background[0].props.name, "context action names are distinct")
print(json.dumps({"status": "passed", "directory": str(directory)}), flush=True)
