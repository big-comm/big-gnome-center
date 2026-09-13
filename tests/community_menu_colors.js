// SPDX-License-Identifier: MIT
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {FolderColors} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/folderColors.js';
import {FOLDER_COLORS} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/deskUxModel.js';

if (GLib.getenv('GSETTINGS_BACKEND') !== 'memory')
    throw new Error('Refusing to test against persistent settings');
function assert(value, message) {
    if (!value)
        throw new Error(message);
}
const settings = new Gio.Settings({schema_id: 'org.gnome.shell.extensions.community-menu.folders'});
const native = new Gio.Settings({schema_id: 'org.gnome.desktop.app-folders'});
native.set_strv('folder-children', ['folder-a', 'folder-b']);
let changed = 0;
let colors = new FolderColors(() => changed++, settings);
assert(colors.get('folder-a') === null, 'Unset folders retain their existing default tint');
for (const [color] of FOLDER_COLORS) {
    assert(colors.set('folder-a', color), `Save ${color}`);
    assert(colors.get('folder-a') === color, `Read ${color}`);
}
assert(changed > 0, 'Notify live views');
colors.set('folder-b', 'blue');
colors.set('hidden-folder', 'pink');
colors.set('__proto__', 'teal');
assert(colors.get('__proto__') === 'teal', 'Treat folder IDs as data');
colors.destroy();
colors = new FolderColors(() => changed++, settings);
assert(colors.get('folder-a') === 'maia', 'Persist across view recreation');
colors.set('folder-a', null);
assert(colors.get('folder-a') === null, 'Restore original tint');
assert(colors.get('folder-b') === 'blue', 'Leave other folders unchanged');
assert(colors.get('hidden-folder') === 'pink', 'Retain metadata for invisible folders');
assert(!colors.set('folder-a', 'invalid'), 'Reject unsupported colors');
assert(!colors.set('../invalid', 'red'), 'Reject invalid IDs');
assert(native.get_strv('folder-children').join(',') === 'folder-a,folder-b', 'Native organization remains untouched');
colors.destroy();
for (const mode of ['locked', 'rejected']) {
    const wrapped = new Proxy(settings, {get(target, prop) {
        if (prop === 'is_writable')
            return () => mode !== 'locked';
        if (prop === 'set_value')
            return () => false;
        const value = target[prop];
        return typeof value === 'function' ? value.bind(target) : value;
    }});
    colors = new FolderColors(() => changed++, wrapped);
    assert(!colors.set('folder-b', 'red'), `${mode}: reject change`);
    assert(!colors.set('folder-b', null), `${mode}: reject reset`);
    assert(colors.get('folder-b') === 'blue', `${mode}: preserve saved color`);
    colors.destroy();
}
const before = changed;
settings.reset('colors');
assert(changed === before, 'Disconnect signals on destruction');
print('Folder palette persistence, defaults, isolation, locks, and failed writes passed');
