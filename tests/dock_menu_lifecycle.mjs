// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const code = fs.readFileSync(new URL('dockAppIconMenu.js', root), 'utf8')
    .replace(/^import[\s\S]*?;\n/gm, '')
    .replace('await DBusMenuUtils.haveDBusMenu()', 'false').replaceAll('export ', '');

function harness(previews = true) {
    const allocated = [], events = [], workspace = {}, windows = [];
    class Item {
        constructor(label) {
            this.label = {set_text() {}}; this.text = label; this.signals = new Map();
            this.actor = this; this.visible = true; this.sensitive = true;
            allocated.push(this);
        }
        connect(name, callback) {
            const id = this.signals.size + 1; this.signals.set(id, {name, callback}); return id;
        }
        emit(name, ...args) {
            for (const signal of [...this.signals.values()])
                if (signal.name === name) signal.callback(this, ...args);
        }
        show() { assert.ok(!this.destroyed); this.visible = true; }
        hide() { this.visible = false; }
        setSensitive(value) { assert.ok(!this.destroyed); this.sensitive = value; }
        destroy() {
            assert.ok(!this.destroyed, 'double destruction');
            this.emit('destroy'); this.menu?.destroy(); this.destroyed = true;
            if (this.parent) this.parent.items.splice(this.parent.items.indexOf(this), 1);
            this.signals.clear();
        }
        add_style_class_name() {}
    }
    class Menu extends Item {
        constructor(source) { super(); this.sourceActor = source; this.items = []; }
        addMenuItem(item) { this.items.push(item); item.parent = this; }
        _getMenuItems() { return this.items; }
        removeAll() { for (const item of [...this.items]) item.destroy(); }
        destroy() { this.removeAll(); super.destroy(); }
        _updateSeparatorVisibility() {}
        open() { this.opened = true; }
        close() {}
    }
    class SubMenu extends Item {
        constructor(label) { super(label); this.menu = new Menu(); }
    }
    class Preview extends Item {
        constructor(window) { super(); this._window = window; }
    }
    const settings = {showWindowsPreview: previews, defaultWindowsPreviewToOpen: false};
    const cls = vm.runInNewContext(`${code}\nDockAppIconMenu`, {
        St: {Side: {LEFT: 0}}, Extension: {gettext: s => s, ngettext: a => a}, _: s => s,
        Main: {uiGroup: {add_child() {}}}, BoxPointer: {PopupAnimation: {FULL: 1}},
        Docking: {DockSurfaceManager: {settings, getDefault: () => ({})}},
        Utils: {getPosition: () => 0, GlobalSignalsHandler: class { add() {} }},
        PopupMenu: {PopupMenu: Menu, PopupMenuItem: Item, PopupSeparatorMenuItem: Item,
            PopupMenuSection: Menu, PopupSubMenuMenuItem: SubMenu},
        WindowPreview: {WindowPreviewMenuItem: Preview},
        Shell: {AppSystem: {get_default: () => ({lookup_app: () => null})}},
        global: {settings: {is_writable: () => false},
            workspace_manager: {get_active_workspace: () => workspace}},
    });
    const source = new Item();
    source.app = {is_window_backed: () => true, get_name: () => 'Test'};
    source.name = 'Test'; source.windowsCount = 0; source.getInterestingWindows = () => windows;
    const menu = new cls(source);
    menu.connect('activate-window', (_, window) => events.push(window));
    const window = (otherWorkspace = false) => ({title: 'Window',
        get_workspace: () => otherWorkspace ? null : workspace});
    const rebuild = () => menu._rebuildMenu();
    const callbacks = item => [...item.signals.values()].map(s => () => s.callback(item));
    const clean = () => {
        menu.destroy(); source.destroy();
        assert.ok(allocated.every(item => item.destroyed), 'orphaned menu item');
    };
    return {menu, source, settings, windows, window, rebuild, callbacks, clean, events};
}
let count = 0;
function test(name, run) {
    if (process.env.BGC_TEST_CASE && process.env.BGC_TEST_CASE !== name) return;
    try { run(); count++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
}
test('empty preview submenu belongs to its menu', () => {
    const h = harness(); h.rebuild();
    assert.ok(h.menu._getMenuItems().includes(h.menu._allWindowsMenuItem));
    assert.equal(h.menu._allWindowsMenuItem.visible, false); h.clean();
});
test('first window appears without rebuilding the menu', () => {
    const h = harness(); h.rebuild(); const sub = h.menu._allWindowsMenuItem;
    h.windows.push(h.window()); h.menu.update();
    assert.ok(h.menu._getMenuItems().includes(sub)); assert.equal(sub.visible, true);
    assert.equal(sub.menu._getMenuItems()[0]._window, h.windows[0]); h.clean();
});
test('repeated empty rebuilds release every submenu', () => {
    const h = harness(); for (let i = 0; i < 25; i++) h.rebuild(); h.clean();
});
test('live preview activates its window', () => {
    const h = harness(); h.windows.push(h.window()); h.rebuild();
    h.menu._allWindowsMenuItem.menu._getMenuItems()[0].emit('activate');
    assert.equal(h.events[0], h.windows[0]); h.clean();
});
test('last live preview disables submenu', () => {
    const h = harness(); h.windows.push(h.window()); h.rebuild();
    const sub = h.menu._allWindowsMenuItem; sub.menu._getMenuItems()[0].destroy();
    assert.equal(sub.sensitive, false); h.clean();
});
test('retired previews cannot act on replacement submenu', () => {
    const h = harness(); h.windows.push(h.window()); h.rebuild();
    const callbacks = h.callbacks(h.menu._allWindowsMenuItem.menu._getMenuItems()[0]);
    h.rebuild(); const sub = h.menu._allWindowsMenuItem;
    for (const callback of callbacks) callback();
    assert.equal(sub.sensitive, true); assert.equal(h.events.length, 0); h.clean();
});
test('retired previews cannot act on repopulated same submenu', () => {
    const h = harness(); h.windows.push(h.window()); h.rebuild();
    const sub = h.menu._allWindowsMenuItem, callbacks = h.callbacks(sub.menu._getMenuItems()[0]);
    h.menu._populateAllWindowMenu(h.windows);
    for (const callback of callbacks) callback();
    assert.equal(sub.sensitive, true); assert.equal(h.events.length, 0); h.clean();
});
test('retired preview callbacks are inert after destruction', () => {
    const h = harness(); h.windows.push(h.window()); h.rebuild();
    const callbacks = h.callbacks(h.menu._allWindowsMenuItem.menu._getMenuItems()[0]);
    h.clean(); for (const callback of callbacks) callback(); assert.equal(h.events.length, 0);
});
test('update before first popup is harmless', () => {
    const h = harness(); h.menu.update(); h.clean();
});
test('update during removal does not use retired children', () => {
    const h = harness(); h.windows.push(h.window()); h.rebuild();
    h.menu._allWindowsMenuItem.connect('destroy', () => h.menu.update());
    h.menu.removeAll(); h.clean();
});
test('update and population after destruction are harmless', () => {
    const h = harness(); h.rebuild(); h.clean(); h.menu.update(); h.menu._populateAllWindowMenu([]);
});
test('preview preference changes before rebuilding are safe', () => {
    const h = harness(false); h.windows.push(h.window()); h.rebuild();
    h.settings.showWindowsPreview = true; h.menu.update(); h.clean();
});
test('reentrant submenu retirement stops population', () => {
    const h = harness(); h.windows.push(h.window()); h.rebuild();
    const sub = h.menu._allWindowsMenuItem;
    sub.menu._getMenuItems()[0].connect('destroy', () => {
        delete h.menu._allWindowsMenuItem; delete h.menu._windowPreviewGeneration;
    });
    h.windows.push(h.window());
    h.menu.update();
    assert.equal(sub.menu._getMenuItems().length, 0); h.clean();
});
test('workspace separator and auto-open preference are preserved', () => {
    const h = harness(); h.windows.push(h.window(), h.window(true));
    h.settings.defaultWindowsPreviewToOpen = true; h.rebuild();
    const sub = h.menu._allWindowsMenuItem;
    assert.equal(sub.menu._getMenuItems().length, 3); assert.equal(sub.menu.opened, true); h.clean();
});
console.log(`${count} dock menu lifecycle scenarios passed`);
