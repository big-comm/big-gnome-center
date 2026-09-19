// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const code = fs.readFileSync(new URL('dockPanelController.js', root), 'utf8')
    .replace(/^import .*;$/gm, '').replaceAll('export ', '');

function harness() {
    const failures = new Map(), hooks = new Map(), events = [], emitters = [], timers = new Map();
    const actors = [];
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
        panelBox: box, primaryIndex: 0, primaryMonitor: {index: 0, x: 0, y: 0, width: 1280, height: 800, inFullscreen: true},
        _trackedActors: [tracking], _findActor: () => 0,
        addTopChrome(zone) { step('chrome.add'); chrome.add(zone); },
        removeChrome(zone) { step('chrome.remove'); chrome.delete(zone); },
        _queueUpdateRegions() { step('regions'); }, getWorkAreaForMonitor: () => ({y: 32}),
    });
    layout.monitors = [layout.primaryMonitor];
    const settings = Object.assign(new Emitter('settings'), {
        opacity: 65, visibility: 'always-hidden',
        get_uint() { step('settings.opacity'); return this.opacity; },
        get_string() { step('settings.visibility'); return this.visibility; },
    });
    const overview = Object.assign(new Emitter('overview'), {visible: false, visibleTarget: false});
    const Controller = vm.runInNewContext(`${code}\nPanelController`, {
        console: {warn() {}}, Main: {panel, layoutManager: layout, overview},
        global: {get_window_actors: () => actors, display, workspace_manager: new Emitter('workspace'), stage: {get_grab_actor: () => null}},
        GLib: {PRIORITY_DEFAULT: 0, PRIORITY_DEFAULT_IDLE: 0, SOURCE_REMOVE: false,
            idle_add(priority, callback) { timers.set(++id, {callback}); return id; },
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
        fullscreen: true,
        get_monitor: () => 0, showing_on_its_workspace: () => true,
        get_frame_rect: () => ({x: 0, y: 0, width: 1280, height: 800}),
        get_buffer_rect: () => ({x: 0, y: 0, width: 1280, height: 800}),
    });
    const child = () => Object.assign(new Emitter('child'), {
        mapped: true, get_allocation_box: () => ({x1: 0, y1: 0, x2: 1280, y2: 800}),
    });
    const surface = () => Object.assign(new Emitter('surface'), {
        constructor: {name: 'MetaSurfaceContainerActor'}, x: 3, y: 4,
        children: [child()], get_children() { return this.children; },
        set_position(x, y) { step('surface.position'); this.x = x; this.y = y; },
    });
    const actor = window => Object.assign(new Emitter('actor'), {
        meta_window: window, x: 0, y: 0, width: 1280, height: 800,
        children: [surface()], get_children() { return this.children; },
    });
    return {failures, hooks, events, timers, emitters, zones, autohides, shortcuts, chrome,
        panel, box, tracking, display, layout, overview, window, actor, surface, child, actors,
        settings, Controller, create: () => new Controller({
            getSettings() { step('settings.new'); return settings; },
        })};
}

let count = 0;
function test(name, run) {
    if (process.env.BGC_TEST_CASE && name !== process.env.BGC_TEST_CASE) return;
    try { run(); count++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
}
function released(h, owner = null) {
    if (owner) assert.equal(owner._panel, null);
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
function fullscreen(h, owner) {
    const window = h.window('window'), actor = h.actor(window);
    h.actors.splice(0, h.actors.length, actor);
    h.display.focus_window = window;
    h.display.emit('notify::focus-window');
    owner._ensureFullscreenSurface();
    return {window, actor, surface: actor.children[0], child: actor.children[0].children[0]};
}
for (const point of ['settings.new', 'panel.get', 'zone.new', 'chrome.add', 'zone.position',
    'zone.size', 'autohide.new', 'shortcuts.new', 'settings.opacity', 'settings.visibility',
    'panel.set', 'autohide.enabled', 'autohide.visible']) {
    test(`constructor rollback: ${point}`, () => {
        const h = harness(), error = new Error(point);
        h.layout.primaryMonitor.inFullscreen = false;
        h.failures.set(point, error);
        assert.throws(() => h.create(), e => e === error);
        released(h);
        assert.equal(h.panel.style, 'color: red;');
        h.failures.clear();
        const retry = h.create(); retry.destroy(); released(h, retry);
    });
}
for (const point of ['shortcuts.destroy', 'autohide.destroy', 'panel.disconnect', 'settings.disconnect',
    'window.disconnect', 'actor.disconnect', 'surface.disconnect', 'child.disconnect',
    'chrome.remove', 'zone.destroy', 'panel.set', 'regions', 'box.show', 'source.remove']) {
    test(`independent cleanup after ${point}`, () => {
        const h = harness(), owner = h.create(); fullscreen(h, owner);
        owner._queueHide(); owner._queueOpacityApply();
        const callbacks = [...h.emitters.flatMap(e => e.history), ...[...h.timers.values()].map(t => t.callback)];
        h.failures.set(point, new Error(point)); h.events.length = 0;
        owner.destroy();
        assert.equal(owner._panel, null);
        for (const field of ['_hideTimeout', '_opacityIdle', '_fullscreenSurfaceRepairIdle'])
            assert.equal(owner[field], 0);
        for (const expected of ['shortcuts.destroy', 'autohide.destroy', 'window.disconnect',
            'actor.disconnect', 'surface.disconnect', 'child.disconnect', 'chrome.remove',
            'zone.destroy', 'panel.set', 'regions', 'box.show', 'source.remove'])
            assert.ok(h.events.includes(expected), expected);
        h.failures.clear(); h.events.length = 0;
        callbacks.forEach(cb => cb()); owner.destroy();
        assert.deepEqual(h.events, []);
    });
}
test('retired callbacks cannot affect replacement controller', () => {
    const h = harness(), owner = h.create(); fullscreen(h, owner);
    owner._queueHide(); owner._queueOpacityApply();
    const callbacks = [...h.emitters.flatMap(e => e.history), ...[...h.timers.values()].map(t => t.callback),
        h.autohides[0].reveal, h.shortcuts[0].reveal];
    owner.destroy();
    h.settings.opacity = 80;
    const replacement = h.create();
    h.events.length = 0;
    callbacks.forEach(cb => cb());
    owner._queueHide(); owner._queueOpacityApply(); owner._queueFullscreenSurfaceRepair(); owner.destroy();
    assert.deepEqual(h.events, []);
    assert.ok(h.panel.style.endsWith('0.80);'));
    replacement.destroy(); released(h, replacement);
});
test('old focus callbacks cannot follow replacement window', () => {
    const h = harness(), owner = h.create(), first = fullscreen(h, owner);
    const callbacks = [...first.window.history];
    fullscreen(h, owner);
    h.events.length = 0; callbacks.forEach(cb => cb());
    assert.deepEqual(h.events, []);
    owner.destroy(); released(h, owner);
});
test('old actor callbacks cannot replace current surface', () => {
    const h = harness(), owner = h.create(), first = fullscreen(h, owner);
    const callbacks = [...first.actor.history], replacement = h.actor(first.window);
    h.actors[0] = replacement; owner._ensureFullscreenSurface();
    const surface = owner._fullscreenSurface, pending = owner._fullscreenSurfaceRepairIdle;
    h.events.length = 0; callbacks.forEach(cb => cb());
    assert.deepEqual(h.events, []);
    assert.equal(owner._fullscreenSurface, surface);
    assert.equal(owner._fullscreenSurfaceRepairIdle, pending);
    owner.destroy(); released(h, owner);
});
test('old surface callbacks cannot reconnect obsolete children', () => {
    const h = harness(), owner = h.create(), first = fullscreen(h, owner);
    const callbacks = [...first.surface.history];
    first.actor.children = [h.surface()]; first.actor.emit('child-added');
    h.events.length = 0; callbacks.forEach(cb => cb());
    assert.deepEqual(h.events, []);
    assert.equal(first.child.signals.size, 0);
    owner.destroy(); released(h, owner);
});
test('old child callbacks cannot schedule repair after rewatch', () => {
    const h = harness(), owner = h.create(), first = fullscreen(h, owner);
    const callbacks = [...first.child.history];
    first.surface.children = [h.child()]; first.surface.emit('child-added');
    owner._cancelFullscreenSurfaceRepair();
    callbacks.forEach(cb => cb());
    assert.equal(owner._fullscreenSurfaceRepairIdle, 0);
    first.surface.children[0].emit('notify::allocation');
    assert.notEqual(owner._fullscreenSurfaceRepairIdle, 0);
    owner.destroy(); released(h, owner);
});
for (const mode of ['actor missing', 'surface missing', 'fullscreen exited']) {
    test(mode, () => {
        const h = harness(), owner = h.create(), first = fullscreen(h, owner);
        if (mode === 'actor missing') h.actors.length = 0;
        else if (mode === 'surface missing') first.actor.children = [];
        else first.window.fullscreen = false;
        owner._ensureFullscreenSurface();
        assert.equal(owner._fullscreenSurface, null);
        assert.equal(owner._fullscreenSurfaceRepairIdle, 0);
        assert.equal(first.child.signals.size, 0);
        assert.equal(first.surface.signals.size, 0);
        owner.destroy(); released(h, owner);
    });
}
for (const [queue, cancel, field] of [
    ['_queueHide', '_cancelHide', '_hideTimeout'],
    ['_queueOpacityApply', '_cancelOpacityApply', '_opacityIdle'],
    ['_queueFullscreenSurfaceRepair', '_cancelFullscreenSurfaceRepair', '_fullscreenSurfaceRepairIdle'],
]) {
    test(`retired source: ${field}`, () => {
        const h = harness(), owner = h.create(); fullscreen(h, owner);
        owner[queue](); const old = h.timers.get(owner[field]).callback;
        owner[cancel](); owner[queue](); const current = owner[field];
        h.events.length = 0; old();
        assert.equal(owner[field], current); assert.deepEqual(h.events, []);
        assert.ok(h.timers.has(current));
        owner.destroy(); released(h, owner);
    });
}
test('external panel style survives destruction', () => {
    const h = harness(), owner = h.create();
    h.panel.set_style('color: blue;');
    owner.destroy();
    assert.equal(h.panel.style, 'color: blue;'); released(h, owner);
});
test('constructor error survives child cleanup failure', () => {
    const h = harness(), error = new Error('initialization');
    h.failures.set('settings.opacity', error);
    h.failures.set('shortcuts.destroy', new Error('cleanup'));
    assert.throws(() => h.create(), e => e === error);
    assert.equal(h.autohides[0].destroyed, true);
    assert.equal(h.zones[0].destroyed, true);
    assert.equal(h.panel.reactive, false);
});
test('reentrant destroy is inert', () => {
    const h = harness(), owner = h.create();
    h.hooks.set('shortcuts.destroy', () => owner.destroy());
    owner.destroy(); released(h, owner);
    h.events.length = 0; owner.destroy(); assert.deepEqual(h.events, []);
});
for (const method of ['_positionRevealZone', '_applyOpacity']) {
    test(`destroy during construction: ${method}`, () => {
        const h = harness(), original = h.Controller.prototype[method];
        h.Controller.prototype[method] = function () { original.call(this); this.destroy(); };
        const owner = h.create();
        released(h, owner);
        h.events.length = 0; owner.destroy(); assert.deepEqual(h.events, []);
    });
}
for (const method of ['_apply', '_queueOpacityApply']) {
    test(`destroy during style update: ${method}`, () => {
        const h = harness(), owner = h.create();
        h.hooks.set('panel.set', () => owner.destroy());
        owner[method]();
        released(h, owner);
    });
}
test('current fullscreen repair preserves geometry checks', () => {
    const h = harness(), owner = h.create(), first = fullscreen(h, owner);
    const run = () => {
        owner._queueFullscreenSurfaceRepair();
        const id = owner._fullscreenSurfaceRepairIdle, source = h.timers.get(id);
        h.timers.delete(id); source.callback();
    };
    first.actor.width = 100; run();
    assert.equal(first.surface.x, 3);
    first.actor.width = 1280; run();
    assert.equal(first.surface.x, 0);
    assert.equal(first.surface.y, 0);
    assert.equal(owner._fullscreenSurfaceRepairCount, 1);
    owner.destroy(); released(h, owner);
});
console.log(`${count} dock panel lifecycle scenarios passed`);
