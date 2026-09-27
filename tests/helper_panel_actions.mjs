// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/extension.js', import.meta.url), 'utf8');
const methods = ['_usesMenuSessionActions', '_findQuickSettingsShutdownItem',
    '_syncQuickSettingsShutdownItem', '_setupQuickSettingsShutdownItem',
    '_teardownQuickSettingsShutdownItem'];
const menu = {};
const callbacks = new Map();
const shutdown = {
    menu, visible: true, allowed: true,
    connect(name, callback) { callbacks.set(name, callback); return name; },
    disconnect(id) { callbacks.delete(id); },
    hide() { this.visible = false; callbacks.get('notify::visible')?.(); },
    show() { this.visible = true; callbacks.get('notify::visible')?.(); },
    _sync() { if (this.allowed) this.show(); else this.hide(); },
};
let layout = 0;
const Main = {panel: {statusArea: {quickSettings: {_system: {_systemItem: {
    menu, child: {get_children: () => [{menu: {}}, shutdown]},
}}}}}};
const Helper = vm.runInNewContext(`class Helper {${methods.map(name => {
    const start = source.indexOf(`    ${name}(`);
    return source.slice(start, source.indexOf('\n    }', start) + 6);
}).join('\n')}}; Helper`, {
    Main, Gio: {Settings: class {get_enum() { return layout; }}},
    COMMUNITY_MENU_UUID: 'menu', CLASSIC_MENU_LAYOUT: 1,
    DESK_UX_MENU_LAYOUT: 3, HYBRID_MENU_LAYOUT: 4, logHelper() {},
});
const helper = new Helper();
helper._panelWillRun = () => true;
helper._extensionWillRun = () => true;
for (layout of [1, 3, 4, 0, 4, 0]) {
    helper._setupQuickSettingsShutdownItem();
    assert.equal(shutdown.visible, layout === 0);
    shutdown._sync(); // Shell policy refresh, e.g. a theme/session update.
    assert.equal(shutdown.visible, layout === 0);
    assert.equal(callbacks.size, 1);
}
layout = 1;
helper._setupQuickSettingsShutdownItem();
helper._extensionWillRun = () => false;
helper._syncQuickSettingsShutdownItem();
assert.equal(shutdown.visible, true, 'retain power action without Community Menu');
helper._extensionWillRun = () => true;
helper._setupQuickSettingsShutdownItem();
shutdown.allowed = false;
helper._teardownQuickSettingsShutdownItem();
assert.equal(shutdown.visible, false, 'restore Shell policy, not unconditional visibility');
assert.equal(callbacks.size, 0);
shutdown.allowed = true;
helper._setupQuickSettingsShutdownItem();
helper._teardownQuickSettingsShutdownItem();
assert.equal(shutdown.visible, true);
assert.equal(callbacks.size, 0);
console.log('Helper panel actions passed');
