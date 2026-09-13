// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const directory = '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/';
const source = fs.readFileSync(new URL(`${directory}widgets/secondaryMenu.js`, import.meta.url), 'utf8');
const appMenu = source.slice(source.indexOf('export const AppItemMenu'), source.indexOf('export const ButtonMenu'))
    .replace('export const AppItemMenu =', 'const AppItemMenu =');
class SignalItem {
    constructor(label, state) { this.label = {text: label}; this.state = state; }
    connect(signal, callback) { this[signal] = callback; }
    setToggleState(state) { this.state = state; }
    setSensitive(value) { this.sensitive = value; }
}
class NativeMenu {
    constructor() {
        for (const name of ['_newWindowItem', '_onGpuMenuItem', '_detailsItem', '_windowSection', '_actionSection'])
            this[name] = new SignalItem();
        this.actor = {connect() {}, get_parent() {}};
    }
    setApp(app) { this._app = app; this.nativePinVisible = this._enableFavorites; }
    addMenuItem() {}
    destroy() { this.setApp(null); }
}
let layout = 3;
let writable = true;
let accepted = true;
let destroyed = 0;
const pins = new Set();
class Pins {
    get writable() { return writable; }
    has(id) { return pins.has(id); }
    add(ids) { if (writable && accepted) ids.forEach(id => pins.add(id)); }
    remove(id) { if (writable && accepted) pins.delete(id); }
    destroy() { destroyed++; }
}
const ContextMenu = vm.runInNewContext(`${appMenu}; AppItemMenu`, {
    AppMenu: {AppMenu: NativeMenu}, MenuPins: Pins,
    SETTINGS: {get_enum: () => layout}, LAYOUTS: {APP_GRID: 3},
    St: {Side: {TOP: 0}}, _: text => text,
    PopupMenu: {PopupMenuItem: SignalItem, PopupSwitchMenuItem: SignalItem, PopupSeparatorMenuItem: SignalItem},
    Main: {uiGroup: {add_child() {}}},
    GLib: {UserDirectory: {DIRECTORY_DESKTOP: 0}, get_user_special_dir() {}, build_filenamev() {}},
    Gio: {File: {new_for_path: () => ({query_exists: () => false})}},
});
// The same context class serves tiles and native search results.
for (const contextSource of [{app: {get_id: () => 'tile.desktop'}, owner: {}},
    {app: {get_id: () => 'search.desktop'}}]) {
    const menu = new ContextMenu(contextSource);
    assert.equal(menu.nativePinVisible, false, 'Desk UX never exposes the native dock toggle');
    assert.equal(menu._menuPinItem.state, false);
    menu._menuPinItem.toggled(null, true);
    assert.equal(pins.has(contextSource.app.get_id()), true, 'Context toggle pins in menu');
    assert.equal(menu._menuPinItem.state, true);
    accepted = false;
    menu._menuPinItem.toggled(null, false);
    assert.equal(menu._menuPinItem.state, true, 'Rejected write restores switch state');
    accepted = true;
    menu._menuPinItem.toggled(null, false);
    assert.equal(pins.has(contextSource.app.get_id()), false, 'Context toggle unpins from menu');
    writable = false;
    menu._syncMenuPin();
    assert.equal(menu._menuPinItem.sensitive, false, 'Locked pins disable the switch');
    writable = true;
    menu.destroy();
}
assert.equal(destroyed, 2, 'Context stores disconnect on destruction');
for (layout of [1, 4]) {
    const menu = new ContextMenu({app: {get_id: () => 'other.desktop'}});
    assert.equal(menu.nativePinVisible, true, 'Other styles retain existing actions');
    assert.equal(menu._menuPinItem, undefined);
    menu.destroy();
}

const widgets = fs.readFileSync(new URL(`${directory}widgets/deskUxApps.js`, import.meta.url), 'utf8');
const dropMethods = widgets.slice(widgets.indexOf('    _canDrop('), widgets.lastIndexOf('\n});'));
const Drop = vm.runInNewContext(`class Drop {${dropMethods}}; Drop`);
const screen = new Drop();
const from = {owner: screen, app: {get_id: () => 'new.desktop'}};
const target = {favorite: true, app: {get_id: () => 'target.desktop'}};
let move;
screen._pins = {move: (...args) => {move = args; return accepted;}};
assert.equal(screen.drop(target, from), true);
assert.deepEqual(Array.from(move), ['new.desktop', 'target.desktop']);
screen.drop({kind: 'pin'}, from);
assert.deepEqual(Array.from(move), ['new.desktop', null]);
accepted = false;
assert.equal(screen.drop(target, from), false, 'Failed writes reject the drop');
assert.equal(screen.drop(target, {...from, owner: {}}), false, 'Foreign drag sources are rejected');
console.log('Menu/search context pinning, independent drag order, and rejected writes passed');
