// SPDX-License-Identifier: MIT
// Always run with GSETTINGS_BACKEND=memory and the bundled schemas.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {MenuPins} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/menuPins.js';

if (GLib.getenv('GSETTINGS_BACKEND') !== 'memory')
    throw new Error('Refusing to test against persistent settings');
function equal(actual, expected, message) {
    if (JSON.stringify(actual) !== JSON.stringify(expected))
        throw new Error(message);
}
const shell = new Gio.Settings({schema_id: 'org.gnome.shell'});
const settings = new Gio.Settings({schema_id: 'org.gnome.shell.extensions.community-menu.pins'});
const initial = ['a.desktop', 'hidden.desktop', 'b.desktop'];
shell.set_strv('favorite-apps', initial);
let changes = 0;
let pins = new MenuPins(() => changes++, settings, shell);
equal(pins.ids(), initial, 'Copy existing order, including unavailable apps');
shell.set_strv('favorite-apps', ['dock-only.desktop']);
equal(changes, 0, 'Dock changes do not refresh menu pins');
equal(pins.ids(), initial, 'Dock changes do not change menu pins');
pins.add(['menu-only.desktop', 'a.desktop']);
equal(pins.ids(), [...initial, 'menu-only.desktop'], 'Deduplicate without reordering existing pins');
equal(shell.get_strv('favorite-apps'), ['dock-only.desktop'], 'Pinning leaves dock untouched');
pins.move('menu-only.desktop', 'b.desktop');
equal(pins.ids(), ['a.desktop', 'hidden.desktop', 'menu-only.desktop', 'b.desktop'], 'Move before target, retaining hidden IDs');
pins.move('a.desktop');
equal(pins.ids(), ['hidden.desktop', 'menu-only.desktop', 'b.desktop', 'a.desktop'], 'Drop on section appends');
pins.remove('b.desktop');
equal(shell.get_strv('favorite-apps'), ['dock-only.desktop'], 'Removing and reordering leave dock untouched');
const saved = pins.ids();
pins.destroy();
pins = new MenuPins(() => {}, settings, shell);
equal(pins.ids(), saved, 'Recreation preserves independent order');
for (const id of pins.ids())
    pins.remove(id);
pins.destroy();
pins = new MenuPins(() => {}, settings, shell);
equal(pins.ids(), [], 'Empty menu stays empty after recreation');
equal(settings.get_user_value('apps') !== null, true, 'Empty menu records completed migration');
pins.destroy();

for (const mode of ['locked', 'rejected']) {
    settings.set_strv('apps', saved);
    const wrapper = new Proxy(settings, {get(target, prop) {
        if (prop === 'is_writable')
            return () => mode !== 'locked';
        if (prop === 'set_strv')
            return () => false;
        const value = target[prop];
        return typeof value === 'function' ? value.bind(target) : value;
    }});
    pins = new MenuPins(() => {}, wrapper, shell);
    equal(pins.add(['new.desktop', 'another.desktop']), false, `${mode}: reject bulk pin`);
    equal(pins.remove(saved[0]), false, `${mode}: reject removal`);
    equal(pins.move(saved[0]), false, `${mode}: reject reorder`);
    equal(pins.ids(), saved, `${mode}: preserve entire list`);
    pins.destroy();
    settings.reset('apps');
    pins = new MenuPins(() => {}, wrapper, shell);
    equal(settings.get_user_value('apps'), null, `${mode}: failed migration stays unset`);
    equal(shell.get_strv('favorite-apps'), ['dock-only.desktop'], `${mode}: preserve dock`);
    pins.destroy();
}
settings.reset('apps');
pins = new MenuPins(() => changes++, settings, shell);
pins.destroy();
const before = changes;
settings.set_strv('apps', ['external.desktop']);
equal(changes, before, 'Destroy disconnects notifications');
print('Independent menu pins, migration, empty state, locks, and failed writes passed');
