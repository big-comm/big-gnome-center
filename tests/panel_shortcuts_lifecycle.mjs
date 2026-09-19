// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const code = fs.readFileSync(new URL('panelMenuShortcuts.js', root), 'utf8').replaceAll('export ', '');
const Shortcuts = vm.runInNewContext(`${code}\nPanelMenuShortcuts`, {});
let count = 0;
function test(name, run) {
    if (process.env.BGC_TEST_CASE && name !== process.env.BGC_TEST_CASE) return;
    try { run(); count++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
}
function harness(own = false) {
    const calls = [], events = [];
    const native = function (indicator) { events.push('native'); calls.push([this, indicator]); return indicator; };
    const panel = Object.create({_toggleMenu: native});
    if (own) Object.defineProperty(panel, '_toggleMenu', {
        value: native, writable: true, configurable: true, enumerable: false,
    });
    panel.statusArea = {dateMenu: {reactive: true, menu: {}}, quickSettings: {reactive: true, menu: {}}};
    return {panel, native, calls, events, create: () => new Shortcuts(panel, () => events.push('reveal'))};
}
for (const name of ['dateMenu', 'quickSettings']) {
    test(`active reveal precedes native menu: ${name}`, () => {
        const h = harness(), hook = h.create(), indicator = h.panel.statusArea[name];
        assert.equal(h.panel._toggleMenu(indicator), indicator);
        assert.deepEqual(h.events, ['reveal', 'native']);
        assert.equal(h.calls[0][0], h.panel);
        hook.destroy();
    });
}
for (const indicator of [null, {reactive: false, menu: {}}, {reactive: true}, {reactive: true, menu: {}}]) {
    test(`unsupported indicator delegates unchanged: ${JSON.stringify(indicator)}`, () => {
        const h = harness(), hook = h.create();
        assert.equal(h.panel._toggleMenu(indicator), indicator);
        assert.deepEqual(h.events, ['native']);
        hook.destroy();
    });
}
for (const own of [false, true]) {
    test(`retired captured hook only delegates: ${own}`, () => {
        const h = harness(own), hook = h.create(), captured = h.panel._toggleMenu;
        hook.destroy(); hook.destroy();
        const receiver = {};
        captured.call(receiver, h.panel.statusArea.dateMenu);
        assert.deepEqual(h.events, ['native']);
        assert.equal(h.calls[0][0], receiver);
        assert.equal(h.panel._toggleMenu, h.native);
        assert.equal(Object.hasOwn(h.panel, '_toggleMenu'), own);
        if (own) assert.equal(Object.getOwnPropertyDescriptor(h.panel, '_toggleMenu').enumerable, false);
    });
}
test('external wrapper retains native behavior without old reveal', () => {
    const h = harness(), hook = h.create(), captured = h.panel._toggleMenu;
    const external = function (indicator) { h.events.push('external'); return captured.call(this, indicator); };
    h.panel._toggleMenu = external;
    hook.destroy(); hook.destroy();
    h.panel._toggleMenu(h.panel.statusArea.quickSettings);
    assert.equal(h.panel._toggleMenu, external);
    assert.deepEqual(h.events, ['external', 'native']);
});
test('out-of-order retirement preserves only current reveal', () => {
    const h = harness(), old = h.create(), current = h.create();
    old.destroy();
    h.panel._toggleMenu(h.panel.statusArea.dateMenu);
    assert.deepEqual(h.events, ['reveal', 'native']);
    current.destroy();
    h.events.length = 0;
    h.panel._toggleMenu(h.panel.statusArea.dateMenu);
    assert.deepEqual(h.events, ['native']);
});
test('retired callback cannot change replacement owner', () => {
    const h = harness(), old = h.create(), captured = h.panel._toggleMenu;
    old.destroy();
    const current = h.create(), replacement = h.panel._toggleMenu;
    captured.call(h.panel, h.panel.statusArea.dateMenu);
    old.destroy();
    assert.equal(h.panel._toggleMenu, replacement);
    assert.deepEqual(h.events, ['native']);
    h.panel._toggleMenu(h.panel.statusArea.quickSettings);
    assert.deepEqual(h.events, ['native', 'reveal', 'native']);
    current.destroy();
});
test('native exception is preserved after retirement', () => {
    const h = harness(), error = new Error('native');
    h.panel._toggleMenu = () => { throw error; };
    const hook = h.create(), captured = h.panel._toggleMenu;
    hook.destroy();
    assert.throws(() => captured(h.panel.statusArea.dateMenu), e => e === error);
    assert.deepEqual(h.events, []);
});
test('destroy during reveal still forwards the current native action once', () => {
    const h = harness();
    const hook = new Shortcuts(h.panel, () => { h.events.push('reveal'); hook.destroy(); });
    h.panel._toggleMenu(h.panel.statusArea.dateMenu);
    assert.deepEqual(h.events, ['reveal', 'native']);
    assert.equal(h.panel._toggleMenu, h.native);
});
console.log(`${count} panel shortcut lifecycle scenarios passed`);
