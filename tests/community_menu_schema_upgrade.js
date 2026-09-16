// SPDX-License-Identifier: MIT
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {createMenuSettings} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/settings.js';
import {MenuPins} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/menuPins.js';
import {FolderColors} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/folderColors.js';

if (GLib.getenv('GSETTINGS_BACKEND') !== 'memory')
    throw new Error('Refusing to test persistent settings');
function check(value, message) {
    if (!value)
        throw new Error(message);
}
const id = 'org.gnome.shell.extensions.community-menu.pins';
const cached = Gio.SettingsSchemaSource.get_default();
check(!cached.lookup(id, true), 'Start with a catalog without pins');
let missing = false;
try {
    createMenuSettings(id);
} catch (error) {
    missing = error.message.includes('schema not installed');
}
check(missing, 'A genuinely missing schema remains an explicit installation error');
const [source, directory] = ARGV;
Gio.File.new_for_path(source).copy(
    Gio.File.new_for_path(`${directory}/community-menu.gschema.xml`),
    Gio.FileCopyFlags.OVERWRITE, null, null);
const [, , , status] = GLib.spawn_sync(null, ['glib-compile-schemas', '--strict', directory],
    null, GLib.SpawnFlags.SEARCH_PATH, null);
check(status === 0, 'Compile the upgraded catalog');
check(!cached.lookup(id, true), 'The running process still holds the old catalog');
const pins = new MenuPins(() => {}, null, {get_strv: () => ['existing.desktop']});
check(pins.has('existing.desktop'), 'Migration works after an in-session package upgrade');
check(pins.add(['new.desktop']), 'New pins remain writable');
const colors = new FolderColors(() => {});
check(colors.set('test-folder', 'green'), 'Folder colors load from the upgraded catalog');
check(colors.get('test-folder') === 'green', 'Folder colors persist');
pins.destroy();
colors.destroy();
const reopened = new MenuPins();
check(reopened.has('new.desktop'), 'Reopening retains independent pins');
reopened.destroy();
print('Stale schema catalog, upgraded pins/colors, and missing-package checks passed');
