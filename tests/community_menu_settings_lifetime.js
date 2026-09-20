// SPDX-License-Identifier: MIT
// Persistent runs require a private configuration directory and supervisor.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import System from 'system';
import {AppFolders} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/appFolders.js';
import {MenuPins} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/menuPins.js';
import {FolderColors} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/folderColors.js';

const memory = GLib.getenv('GSETTINGS_BACKEND') === 'memory';
const privateDir = GLib.getenv('BGC_STRESS_DIRECTORY');
if (!memory && (!privateDir || !GLib.get_user_config_dir().startsWith(`${privateDir}/`)))
    throw new Error('Private settings required');
const check = (value, message) => { if (!value) throw new Error(message); };
const apps = [{id: 'a.desktop', categories: []}, {id: 'b.desktop', categories: []}];
const make = id => new Gio.Settings(id === null
    ? {schema_id: 'org.gnome.desktop.app-folders'}
    : {schema_id: 'org.gnome.desktop.app-folders.folder',
        path: `/org/gnome/desktop/app-folders/folders/${id}/`});
const root = make(null);
root.set_strv('folder-children', []);
const nativeDispose = Gio.Settings.prototype.run_dispose;
let disposed = 0;
Gio.Settings.prototype.run_dispose = function () {
    check(!this._testDisposed, 'Settings disposed twice');
    this._testDisposed = true;
    disposed++;
    nativeDispose.call(this);
};

// Injected settings remain usable after their consumers are destroyed.
const borrowed = new Map([[null, root]]);
const factory = id => {
    if (!borrowed.has(id)) borrowed.set(id, make(id));
    return borrowed.get(id);
};
const pinsSettings = new Gio.Settings({schema_id: 'org.gnome.shell.extensions.community-menu.pins'});
const colorsSettings = new Gio.Settings({schema_id: 'org.gnome.shell.extensions.community-menu.folders'});
pinsSettings.set_strv('apps', []);
const borrowedStore = new AppFolders(() => {}, () => apps, factory);
const borrowedId = borrowedStore.edit({type: 'create', name: 'Borrowed', apps: apps.map(a => a.id)});
const borrowedPins = new MenuPins(() => {}, pinsSettings);
const borrowedColors = new FolderColors(() => {}, colorsSettings);
borrowedStore.destroy(); borrowedStore.destroy();
borrowedPins.destroy(); borrowedPins.destroy();
borrowedColors.destroy(); borrowedColors.destroy();
check(disposed === 0, 'Consumer disposed borrowed settings');
check(factory(borrowedId).get_string('name') === 'Borrowed', 'Borrowed folder lost');
check(pinsSettings.set_strv('apps', ['borrowed.desktop']), 'Borrowed pins unusable');
check(colorsSettings.get_value('colors') !== null, 'Borrowed colors unusable');
root.set_strv('folder-children', []);
for (const settings of borrowed.values()) settings.run_dispose();
pinsSettings.run_dispose(); colorsSettings.run_dispose();

for (const mode of ['locked', 'rejected']) {
    const before = disposed;
    const store = new AppFolders(() => {}, () => apps);
    const method = mode === 'locked' ? 'is_writable' : 'set_value';
    const original = store._root[method];
    store._root[method] = () => false;
    let rejected = false;
    try {
        store.edit({type: 'create', name: 'Rejected', apps: apps.map(a => a.id)});
    } catch { rejected = true; }
    store._root[method] = original;
    check(rejected, `${mode}: write accepted`);
    check(store.snapshot().length === 0, `${mode}: partial folder survived`);
    store.destroy();
    check(disposed - before === 2, `${mode}: temporary settings not disposed`);
}

const rounds = Number(GLib.getenv('BGC_STRESS_ROUNDS') ?? 200);
const loop = new GLib.MainLoop(null, false);
let round = 0, lastId, error;
GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1, () => {
    try {
        const before = disposed;
        let callbacks = 0;
        const store = new AppFolders(() => callbacks++, () => apps);
        const pins = new MenuPins(() => callbacks++);
        const colors = new FolderColors(() => callbacks++);
        lastId = store.edit({type: 'create', name: 'Owned', apps: apps.map(a => a.id)});
        store.edit({type: 'rename', folder: lastId, name: 'Saved'});
        check(pins.add(['saved.desktop']), 'Pin write rejected');
        check(colors.set(lastId, 'orange'), 'Color write rejected');
        // Keep only the final folder; exercise removed settings and queued signals.
        if (round + 1 < rounds) {
            store.edit({type: 'ungroup', apps: apps.map(a => a.id)});
            colors.set(lastId, null);
        }
        store.destroy(); pins.destroy(); colors.destroy();
        store.destroy(); pins.destroy(); colors.destroy();
        check(disposed - before === 5, 'Owned settings not disposed exactly once');
        const stopped = callbacks;
        while (GLib.MainContext.default().pending()) GLib.MainContext.default().iteration(false);
        check(callbacks === stopped, 'Callback after destruction');
        if (++round % 10 === 0) System.gc();
        if (round < rounds) return GLib.SOURCE_CONTINUE;
    } catch (caught) { error = caught; }
    loop.quit();
    return GLib.SOURCE_REMOVE;
});
loop.run();
if (error) throw error;
Gio.Settings.sync();
// A second process verifies dconf persistence after disposal, without cached reads.
if (!memory) {
    const read = key => {
        const process = Gio.Subprocess.new(['dconf', 'read', key], Gio.SubprocessFlags.STDOUT_PIPE);
        const [, output] = process.communicate_utf8(null, null);
        check(process.get_successful(), 'dconf read failed');
        return output;
    };
    check(read(`/org/gnome/desktop/app-folders/folders/${lastId}/name`).includes('Saved'), 'Folder write lost');
    check(read('/org/communitybig/community-menu/pins/apps').includes('saved.desktop'), 'Pin write lost');
    check(read('/org/communitybig/community-menu/folders/colors').includes('orange'), 'Color write lost');
}
print(JSON.stringify({passed: true, rounds, disposed, persistent: !memory}));
