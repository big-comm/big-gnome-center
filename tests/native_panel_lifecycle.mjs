// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const code = fs.readFileSync(new URL('nativePanelOpacityIntegration.js', root), 'utf8')
    .replace(/^import .*;$/gm, '').replaceAll('export ', '');

function harness() {
    const failures = new Map(), hooks = new Map(), events = [], emitters = [], timers = new Map();
    const zones = [], autohides = [], shortcuts = [], chrome = new Set();
    let id = 0;
    const step = name => {
        events.push(name);
        hooks.get(name)?.();
        if (failures.has(name)) throw failures.get(name);
    };
    class Emitter {
        constructor(name) { this.name = name; this.signals = new Map(); this.history = []; emitters.push(this); }
        connect(signal, callback) {
            step(`${this.name}.connect.${signal}`);
            this.signals.set(++id, {signal, callback}); this.history.push(callback); return id;
        }
        disconnect(key) { step(`${this.name}.disconnect`); this.signals.delete(key); }
        emit(signal) { for (const s of [...this.signals.values()]) if (s.signal === signal) s.callback(); }
    }
    const panel = Object.assign(new Emitter('panel'), {
        style: 'color: red;', reactive: false, track_hover: false, hover: false, height: 32,
        statusArea: {}, menuManager: {}, contains: () => false,
        get_style() { step('panel.get'); return this.style; },
        set_style(value) { step('panel.set'); this.style = value; this.emit('notify::style'); },
        get_theme_node() { return {get_background_color() { step('background'); return {red: 10, green: 20, blue: 30}; }}; },
    });
    const box = Object.assign(new Emitter('box'), {
        visible: true, height: 32,
        show() { step('box.show'); this.visible = true; }, hide() { step('box.hide'); this.visible = false; },
    });
    const tracking = {affectsStruts: true, trackFullscreen: true};
    const display = Object.assign(new Emitter('display'), {focus_window: null});
    const layout = Object.assign(new Emitter('layout'), {
        panelBox: box, primaryIndex: 0, primaryMonitor: {index: 0, x: 0, y: 0, width: 1280},
        _trackedActors: [tracking], _findActor: () => 0,
        addTopChrome(zone) { step('chrome.add'); chrome.add(zone); },
        removeChrome(zone) { step('chrome.remove'); chrome.delete(zone); },
        _queueUpdateRegions() { step('regions'); }, getWorkAreaForMonitor: () => ({y: 32}),
    });
    const overview = Object.assign(new Emitter('overview'), {visible: false, visibleTarget: false});
    const Controller = vm.runInNewContext(`${code}\nNativePanelOpacityIntegration`, {
        console: {warn() {}}, Main: {panel, layoutManager: layout, overview},
        global: {display, workspace_manager: new Emitter('workspace'), stage: {get_grab_actor: () => null}},
        GLib: {PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
            timeout_add(priority, delay, callback) { timers.set(++id, {delay, callback}); return id; },
            Source: {remove(key) { step('source.remove'); timers.delete(key); }}},
        St: {Widget: class extends Emitter {
            constructor() { super('zone'); step('zone.new'); zones.push(this); }
            set_position() { step('zone.position'); } set_size() { step('zone.size'); }
            destroy() { step('zone.destroy'); this.destroyed = true; chrome.delete(this); }
        }},
        PanelAutohide: class {
            constructor(actor, zone, reveal) { step('autohide.new'); this.reveal = reveal; autohides.push(this); }
            destroy() { step('autohide.destroy'); this.destroyed = true; }
            setEnabled(value) { step('autohide.enabled'); this.enabled = value; }
            setVisible(value) { step('autohide.visible'); box.visible = value; }
            reposition() { step('autohide.position'); }
            pointerInside() { return false; }
        },
        PanelMenuShortcuts: class {
            constructor(actor, reveal) { step('shortcuts.new'); this.reveal = reveal; shortcuts.push(this); }
            destroy() { step('shortcuts.destroy'); this.destroyed = true; }
        },
    });
    const window = name => Object.assign(new Emitter(name), {
        get_monitor: () => 0, showing_on_its_workspace: () => true,
        get_frame_rect: () => ({x: 0, y: 0, width: 1280, height: 800}),
    });
    return {failures, hooks, events, timers, emitters, zones, autohides, shortcuts, chrome,
        panel, box, tracking, display, layout, overview, window, create: () => new Controller()};
}
let count = 0;
function test(name, run) {
    if (process.env.BGC_TEST_CASE && name !== process.env.BGC_TEST_CASE) return;
    try { run(); count++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
}
function released(h, owner) {
    assert.equal(owner._panel, null);
    assert.equal(h.chrome.size, 0);
    assert.equal(h.timers.size, 0);
    assert.ok(h.emitters.every(e => e.signals.size === 0));
    assert.ok(h.autohides.every(a => a.destroyed));
    assert.ok(h.shortcuts.every(a => a.destroyed));
    assert.ok(h.zones.every(a => a.destroyed));
    assert.equal(h.panel.reactive, false); assert.equal(h.panel.track_hover, false);
    assert.equal(h.box.visible, true);
    assert.deepEqual(h.tracking, {affectsStruts: true, trackFullscreen: true});
}
for (const point of ['panel.get', 'background', 'zone.new', 'chrome.add', 'zone.position',
    'zone.size', 'autohide.new', 'shortcuts.new', 'panel.connect.notify::style',
    'panel.set', 'autohide.enabled', 'autohide.visible']) {
    test(`activation rollback: ${point}`, () => {
        const h = harness(), owner = h.create(), error = new Error(point);
        h.failures.set(point, error);
        assert.throws(() => owner.activate(65, 'always-hidden'), e => e === error);
        released(h, owner);
        assert.equal(h.panel.style, 'color: red;');
        h.failures.clear();
        owner.activate(65, 'always-hidden'); owner.deactivate();
        released(h, owner);
    });
}
test('old signals cannot alter reactivated panel', () => {
    const h = harness(), owner = h.create();
    owner.activate(65, 'always-hidden');
    const callbacks = h.emitters.flatMap(e => e.history);
    const reveal = h.autohides[0].reveal, shortcut = h.shortcuts[0].reveal;
    owner.deactivate(); owner.activate(80, 'always-visible');
    h.events.length = 0;
    callbacks.forEach(cb => cb()); reveal(); shortcut();
    assert.deepEqual(h.events, []);
    assert.equal(h.timers.size, 0);
    assert.ok(h.panel.style.endsWith('0.80);'));
    owner.deactivate(); released(h, owner);
});
test('retired window callbacks cannot follow new focus', () => {
    const h = harness(), owner = h.create();
    h.display.focus_window = h.window('old');
    owner.activate(65, 'intelligent');
    const callbacks = [...h.display.focus_window.history];
    h.display.focus_window = h.window('new'); h.display.emit('notify::focus-window');
    h.events.length = 0; callbacks.forEach(cb => cb());
    assert.deepEqual(h.events, []);
    owner.deactivate(); released(h, owner);
});
test('old timer cannot clear replacement hide timer', () => {
    const h = harness(), owner = h.create();
    owner.activate(65, 'always-hidden'); owner._queueHide();
    const old = h.timers.get(owner._hideTimeout).callback;
    owner._queueHide(); const current = owner._hideTimeout;
    old(); assert.equal(owner._hideTimeout, current);
    assert.equal(h.timers.get(current).delay, 500);
    owner.deactivate(); released(h, owner);
});
for (const point of ['shortcuts.destroy', 'autohide.destroy', 'panel.disconnect',
    'chrome.remove', 'zone.destroy', 'panel.set', 'regions', 'box.show', 'source.remove']) {
    test(`independent cleanup after ${point}`, () => {
        const h = harness(), owner = h.create();
        owner.activate(65, 'always-hidden'); owner._queueHide();
        const callbacks = [...h.emitters.flatMap(e => e.history), ...[...h.timers.values()].map(t => t.callback)];
        h.failures.set(point, new Error(point));
        h.events.length = 0;
        owner.deactivate();
        assert.equal(owner._panel, null);
        assert.equal(owner._hideTimeout, 0);
        for (const expected of ['shortcuts.destroy', 'autohide.destroy', 'chrome.remove', 'zone.destroy', 'panel.set', 'regions', 'box.show'])
            assert.ok(h.events.includes(expected), expected);
        assert.equal(h.panel.reactive, false); assert.equal(h.panel.track_hover, false);
        h.failures.clear(); h.events.length = 0;
        callbacks.forEach(cb => cb()); owner.deactivate();
        assert.deepEqual(h.events, []);
    });
}
test('original activation failure survives failed child cleanup', () => {
    const h = harness(), owner = h.create(), error = new Error('activate');
    h.failures.set('panel.connect.notify::style', error);
    h.failures.set('shortcuts.destroy', new Error('cleanup'));
    assert.throws(() => owner.activate(65, 'intelligent'), e => e === error);
    assert.equal(h.autohides[0].destroyed, true);
    assert.equal(h.zones[0].destroyed, true);
});
test('external style survives retirement', () => {
    const h = harness(), owner = h.create();
    owner.activate(65, 'always-visible');
    h.panel.set_style('color: blue;');
    assert.ok(h.panel.style.startsWith('color: blue;'));
    owner.deactivate();
    assert.equal(h.panel.style, 'color: blue;');
    released(h, owner);
});
test('silent external style is not overwritten', () => {
    const h = harness(), owner = h.create();
    owner.activate(65, 'always-visible'); h.panel.style = 'color: blue;';
    owner.deactivate();
    assert.equal(h.panel.style, 'color: blue;');
    assert.equal(owner._restoreConflicts, 1);
    released(h, owner);
});
for (const point of ['chrome.add', 'panel.set']) {
    test(`destroy during activation: ${point}`, () => {
        const h = harness(), owner = h.create();
        h.hooks.set(point, () => owner.destroy());
        owner.activate(65, 'always-hidden');
        released(h, owner);
        h.events.length = 0; owner.activate(80, 'always-visible');
        assert.deepEqual(h.events, []);
    });
}
test('reentrant teardown cannot reactivate owner', () => {
    const h = harness(), owner = h.create(); owner.activate(65, 'always-hidden');
    h.hooks.set('shortcuts.destroy', () => { owner.deactivate(); owner.activate(80, 'always-visible'); });
    owner.deactivate(); released(h, owner);
    assert.equal(h.shortcuts.length, 1);
});
console.log(`${count} native panel lifecycle scenarios passed`);
