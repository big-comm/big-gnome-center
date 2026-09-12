// SPDX-License-Identifier: MIT
// Always run with GSETTINGS_BACKEND=memory.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {AppFolders} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/appFolders.js';

if (GLib.getenv('GSETTINGS_BACKEND') !== 'memory')
    throw new Error('Refusing to test against persistent settings');
function assert(value, message) {
    if (!value)
        throw new Error(message);
}
const root = new Gio.Settings({schema_id: 'org.gnome.desktop.app-folders'});
root.set_strv('folder-children', []);
const apps = [{id: 'a.desktop', categories: ['Utility']}, {id: 'b.desktop', categories: ['Utility']}];
const store = new AppFolders(() => {}, () => apps);
const id = store.edit({type: 'create', name: 'Pair', apps: apps.map(a => a.id)});
assert(store.snapshot().length === 1, 'Folder created');
assert(root.get_strv('folder-children')[0] === id, 'Uses native root');
store.edit({type: 'rename', folder: id, name: 'Renamed'});
assert(store.snapshot()[0].name === 'Renamed', 'Native rename');
store.edit({type: 'ungroup', apps: ['a.desktop']});
assert(store.snapshot()[0].apps.length === 1, 'Keep single app');
store.edit({type: 'ungroup', apps: ['b.desktop']});
assert(root.get_strv('folder-children').length === 0, 'Remove empty folder');
store.destroy();

// Lock/failure injection with real memory-backed schema values.
for (const mode of ['locked', 'rejected']) {
    const wrappers = new Map();
    const factory = folder => {
        const key = folder ?? 'root';
        if (wrappers.has(key))
            return wrappers.get(key);
        const settings = new Gio.Settings(folder === null
            ? {schema_id: 'org.gnome.desktop.app-folders'}
            : {schema_id: 'org.gnome.desktop.app-folders.folder',
                path: `/org/gnome/desktop/app-folders/folders/${folder}/`});
        const wrapper = new Proxy(settings, {get(target, prop) {
            if (prop === 'is_writable')
                return name => !(mode === 'locked' && folder === null && name === 'folder-children');
            if (prop === 'set_value')
                return (name, value) => folder === null && mode === 'rejected' ? false : target.set_value(name, value);
            const value = target[prop];
            return typeof value === 'function' ? value.bind(target) : value;
        }});
        wrappers.set(key, wrapper);
        return wrapper;
    };
    const tested = new AppFolders(() => {}, () => apps, factory);
    let rejected = false;
    try {
        tested.edit({type: 'create', name: 'Rejected', apps: apps.map(a => a.id)});
    } catch {
        rejected = true;
    }
    assert(rejected, `${mode}: reject save`);
    assert(root.get_strv('folder-children').length === 0, `${mode}: preserve root`);
    for (const [key, settings] of wrappers) {
        if (key !== 'root')
            assert(settings.get_user_value('name') === null, `${mode}: no partial folder settings`);
    }
    tested.destroy();
}
print('Native folder settings and lock/rejection recovery passed');
