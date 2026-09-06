// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const root = new URL('../usr/share/gnome-shell/extensions/community-menu@communitybig.org/', import.meta.url);
const constants = fs.readFileSync(new URL('constants.js', root), 'utf8');
const policy = constants.slice(constants.indexOf('export function resolveMenuLayout'),
    constants.indexOf('export const APPS_ONLY_MENU_HEIGHT')).replace('export ', '');
const LAYOUTS = {ALL: 0, APPS_ONLY: 1, SYSTEM_ONLY: 2, APP_GRID: 3, MINT: 4};
const resolveMenuLayout = vm.runInNewContext(`${policy}; resolveMenuLayout`, {LAYOUTS});
for (const desktop of ['BigGnome', 'Minimal', 'G-Unity', 'g_unity', '  minimal  ']) {
    for (const value of [0, 1, 2, 3, 4, 99])
        assert.equal(resolveMenuLayout(value, desktop), LAYOUTS.MINT);
}
for (const desktop of ['Classic', 'Desk UX', 'Hybrid', '']) {
    for (const value of [1, 3, 4])
        assert.equal(resolveMenuLayout(value, desktop), value);
    for (const value of [0, 2, 99, undefined])
        assert.equal(resolveMenuLayout(value, desktop), LAYOUTS.MINT);
}

const factory = fs.readFileSync(new URL('layouts/layouts.js', root), 'utf8')
    .replace(/^import .*;?$/gm, '').replace('export function', 'function');
const makeLayout = vm.runInNewContext(`${factory}; getLayout`, {
    Constants: {LAYOUTS, resolveMenuLayout},
    AppListLayout: {AppListLayout: class {type = 'classic';}},
    AppGridLayout: {AppGridLayout: class {type = 'grid';}},
    HybridLayout: {HybridLayout: class {type = 'hybrid';}},
});
assert.equal(makeLayout(1, {}, {desktopLayout: 'classic'}).type, 'classic');
assert.equal(makeLayout(3, {}, {desktopLayout: 'desk-ux'}).type, 'grid');
for (const value of [0, 2, 4, 99])
    assert.equal(makeLayout(value, {}, {}).type, 'hybrid');
assert.equal(makeLayout(1, {}, {desktopLayout: 'minimal'}).type, 'hybrid');

const extension = fs.readFileSync(new URL('extension.js', root), 'utf8');
const normalizer = extension.slice(extension.indexOf('    _normalizeLayout() {'),
    extension.indexOf('    _getActivePanelExtension() {'));
for (const active of ['BigGnome', 'Minimal', 'G-Unity', 'Classic', 'Desk UX', 'Hybrid', '']) {
    for (const old of [0, 1, 2, 3, 4]) {
        const values = {layout: old, 'desktop-layout': ''};
        const Controller = vm.runInNewContext(`class Controller {${normalizer}}; Controller`, {
            SETTINGS: {
                get_string: key => values[key], get_enum: key => values[key],
                is_writable: () => true,
                set_enum: (key, value) => { values[key] = value; },
                set_string: (key, value) => { values[key] = value; },
            },
            Constants: {resolveMenuLayout},
            Gio: {
                SettingsSchemaSource: {get_default: () => ({lookup: () => ({has_key: () => true})})},
                Settings: class {get_string() { return active; }},
            },
        });
        new Controller()._normalizeLayout();
        assert.equal(values.layout, resolveMenuLayout(old, active));
        assert.equal(values['desktop-layout'], active);
    }
}
console.log('Menu defaults, legacy migration, and three layout factories passed');
