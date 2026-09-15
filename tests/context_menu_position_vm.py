"""Check full-size context popovers near monitor edges on native Wayland."""

import importlib.util
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

spec = importlib.util.spec_from_file_location(
    "provider",
    "/usr/share/nautilus-python/extensions/big_gnome_center_folder_icons.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def pump(seconds=0.4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


def find_scroll(widget):
    if isinstance(widget, Gtk.ScrolledWindow):
        return widget
    child = widget.get_first_child()
    while child is not None:
        match = find_scroll(child)
        if match is not None:
            return match
        child = child.get_next_sibling()
    return None


Gtk.init()
app = Adw.Application(
    application_id="org.communitybig.ContextPositionTest",
    flags=Gio.ApplicationFlags.NON_UNIQUE,
)
app.register(None)
window = Adw.ApplicationWindow(application=app, default_width=1000, default_height=700)
box = Gtk.Box()
window.set_content(box)
model = Gio.Menu()
for number in range(16):
    model.append(f"Context action {number}", None)
popover = Gtk.PopoverMenu.new_from_model(model)
popover.set_has_arrow(False)
popover.set_halign(Gtk.Align.START)
popover.set_parent(box)
window.present()
window.maximize()
pump()
scroll = find_scroll(popover)
rect = Gdk.Rectangle()
rect.x = box.get_width() // 2
rect.y = box.get_height() // 2
popover.set_pointing_to(rect)
popover.popup()
pump()
adjustment = scroll.get_vadjustment()
print("Baseline top/bottom:", adjustment.get_upper(), adjustment.get_page_size(), flush=True)
popover.popdown()
pump()
children = box.observe_children()
module.position_context_menus(children, 0, 0, children.get_n_items())
try:
    for name, x, y in (
        ("middle", box.get_width() // 2, box.get_height() // 2),
        ("top-left", 8, 8),
        ("bottom-left", 8, box.get_height() - 8),
        ("top-right", box.get_width() - 8, 8),
        ("bottom-right", box.get_width() - 8, box.get_height() - 8),
    ):
        rect.x, rect.y = x, y
        popover.set_pointing_to(rect)
        popover.popup()
        pump()
        upper, page = adjustment.get_upper(), adjustment.get_page_size()
        assert upper <= page + 1, (name, upper, page)
        print("PASS all 16 full-size rows visible:", name, upper, page, flush=True)
        popover.popdown()
        pump()
finally:
    popover.unparent()
    window.close()
