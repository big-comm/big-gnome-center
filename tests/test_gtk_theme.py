# SPDX-License-Identifier: MIT
"""Exercise GTK3 following with real GSettings and isolated theme files."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from layout_applier import LayoutApplier

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org"
LEGACY_UUID = "legacyschemeautoswitcher@joshimukul29.gmail.com"


def test_gtk_theme_follower(tmp_path):
    if not shutil.which("gjs"):
        pytest.skip("gjs is required for GTK3 follower tests")
    for directory, theme, version in (
        ("data/themes", "BgcTest", "3.0"),
        ("data/themes", "BgcTest-dark", "3.0"),
        (".themes", "BgcLegacy-dark", "3.0"),
        ("system/themes", "BgcSystem-dark", "3.24"),
    ):
        css = tmp_path / directory / theme / f"gtk-{version}" / "gtk.css"
        css.parent.mkdir(parents=True)
        css.write_text("/* Test theme. */")
    (tmp_path / "data/themes/BgcEmpty-dark/gtk-3.0/gtk.css").mkdir(parents=True)
    script = tmp_path / "check.mjs"
    script.write_text(
        "import {resolveGtkTheme, gtkThemeExists, GtkThemeFollower} from "
        f"'{(HELPER / 'gtkTheme.js').as_uri()}';\n" + r"""
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
function equal(actual, expected) {
    if (actual !== expected)
        throw new Error(`Expected ${expected}, got ${actual}`);
}
const exists = name => ['Theme', 'Theme-dark', 'Pair-light', 'Pair-dark'].includes(name);
for (const [current, scheme, expected] of [
    ['Theme', 'prefer-dark', 'Theme-dark'],
    ['Theme-dark', 'prefer-light', 'Theme'],
    ['Theme-dark', 'default', 'Theme'],
    ['Theme-dark', 'prefer-dark', 'Theme-dark'],
    ['Pair-light', 'prefer-dark', 'Pair-dark'],
    ['Pair-dark', 'prefer-light', 'Pair-light'],
    ['Custom', 'prefer-dark', 'Custom'],
    ['Custom-dark', 'prefer-light', 'Custom-dark'],
    ['Theme', 'unexpected', 'Theme'],
    ['../Theme', 'prefer-dark', '../Theme'],
    ['', 'prefer-dark', ''],
    ['-dark', 'prefer-light', '-dark'],
]) equal(resolveGtkTheme(current, scheme, exists), expected);
for (const name of ['BgcTest', 'BgcTest-dark', 'BgcLegacy-dark', 'BgcSystem-dark'])
    equal(gtkThemeExists(name), true);
for (const name of ['BgcEmpty-dark', 'BgcMissing-dark', '../themes', '/tmp', ''])
    equal(gtkThemeExists(name), false);

const settings = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
settings.set_string('gtk-theme', 'BgcTest');
settings.set_string('color-scheme', 'prefer-dark');
let busy = true;
let writes = 0;
settings.connect('changed::gtk-theme', () => writes++);
const follower = new GtkThemeFollower(settings, () => busy, error => { throw error; });
function wait() {
    const loop = new GLib.MainLoop(null, false);
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 400, () => {
        loop.quit();
        return GLib.SOURCE_REMOVE;
    });
    loop.run();
}
wait();
equal(settings.get_string('gtk-theme'), 'BgcTest');
busy = false;
wait();
equal(settings.get_string('gtk-theme'), 'BgcTest-dark');
equal(writes, 1);
wait();
equal(writes, 1);
settings.set_string('color-scheme', 'prefer-light');
wait();
equal(settings.get_string('gtk-theme'), 'BgcTest');
settings.set_string('color-scheme', 'prefer-dark');
settings.set_string('gtk-theme', 'BgcMissing');
wait();
equal(settings.get_string('gtk-theme'), 'BgcMissing');
settings.set_string('gtk-theme', 'BgcTest');
wait();
equal(settings.get_string('gtk-theme'), 'BgcTest-dark');
settings.set_string('color-scheme', 'prefer-light');
follower.destroy();
follower.destroy();
wait();
equal(settings.get_string('gtk-theme'), 'BgcTest-dark');
const locked = new GtkThemeFollower({
    connect: () => 1, disconnect() {}, is_writable: () => false,
    get_string() { throw new Error('Read-only settings must be untouched'); },
}, () => false, error => { throw error; });
locked.sync();
locked.destroy();
print('GTK3 variants, paths, busy retry, live changes, and teardown passed');
""",
    )
    env = dict(os.environ, HOME=str(tmp_path), XDG_DATA_HOME=str(tmp_path / "data"),
               XDG_DATA_DIRS=f"{tmp_path / 'system'}:/usr/share", GSETTINGS_BACKEND="memory")
    result = subprocess.run(
        ["gjs", "-m", str(script)], env=env, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_old_layout_retires_gtk_switcher():
    data = (
        "[org/gnome/shell]\n"
        f"enabled-extensions=['{LEGACY_UUID}', 'keep@test.org']\n"
        "disabled-extensions=[]\n"
    )
    for dark in (True, False, None):
        rewritten = LayoutApplier._rewrite_shell_theme_mode(data, prefer_dark=dark)
        values = LayoutApplier._section_key_values(rewritten, "/org/gnome/shell")
        assert LEGACY_UUID not in LayoutApplier._string_list(values['enabled-extensions'])
        assert 'keep@test.org' in LayoutApplier._string_list(values['enabled-extensions'])
        assert LEGACY_UUID in LayoutApplier._string_list(values['disabled-extensions'])


def test_original_layouts_and_package_retire_gtk_switcher():
    for path in (ROOT / 'usr/share/big-gnome-center/layouts').glob('*.txt'):
        values = LayoutApplier._section_key_values(path.read_text(), '/org/gnome/shell')
        assert LEGACY_UUID not in LayoutApplier._string_list(values['enabled-extensions'])
        assert LEGACY_UUID in LayoutApplier._string_list(values['disabled-extensions'])
    assert 'gnome-shell-extension-legacy-theme-auto-switcher' not in (
        ROOT / 'pkgbuild/PKGBUILD'
    ).read_text()


def test_helper_owns_gtk_follower_lifecycle():
    source = (HELPER / 'extension.js').read_text()
    assert "import {GtkThemeFollower} from './gtkTheme.js'" in source
    assert 'this._gtkThemeFollower = new GtkThemeFollower(' in source
    assert 'this._gtkThemeFollower?.destroy()' in source
    assert '[LEGACY_USER_THEME_UUID, LEGACY_LIGHT_STYLE_UUID, LEGACY_GTK_THEME_UUID]' in source
    complete = source.split('async _completeSwitch(payload)', 1)[1].split(
        'AbortSwitchAsync', 1,
    )[0]
    assert complete.index('this._gtkThemeFollower?.sync()') < complete.index(
        'this._switching = false',
    )
