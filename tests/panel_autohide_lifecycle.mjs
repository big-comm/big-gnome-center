// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const code = fs.readFileSync(new URL('panelAutohide.js', root), 'utf8')
    .replace(/^import .*;$/gm, '').replaceAll('export ', '');

function harness(barriers = true) {
    const events = [], failures = new Map(), hooks = new Map(), timers = new Map();
    const pressures = [], edges = [], history = [];
    let nextId = 0, holds = 0, reveals = 0;
    const step = name => {
        events.push(name);
        hooks.get(name)?.();
        if (failures.has(name)) throw failures.get(name);
    };
    class Signals {
        constructor(name) { this.name = name; this.callbacks = new Map(); }
        connect(signal, callback) {
            step(`${this.name}.connect.${signal}`);
            this.callbacks.set(++nextId, callback);
            history.push(callback);
            return nextId;
        }
        disconnect(id) { step(`${this.name}.disconnect.${id}`); this.callbacks.delete(id); }
        destroy() { step(`${this.name}.destroy`); this.destroyed = true; this.callbacks.clear(); }
    }
    const actor = {
        translation_y: 7, height: 32, visible: true, transition: null, animations: [],
        get_transition() { return this.transition; },
        remove_transition() { step('actor.remove'); this.transition = null; },
        show() { this.visible = true; },
        ease(options) { this.transition = options; this.animations.push(options); },
    };
    const zone = new Signals('zone');
    zone.hover = true;
    const Panel = vm.runInNewContext(`${code}\nPanelAutohide`, {
        console: {warn() {}}, Clutter: {AnimationMode: {EASE_OUT_QUAD: 1}},
        GLib: {PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
            timeout_add(priority, delay, callback) { timers.set(++nextId, {delay, callback}); return nextId; },
            Source: {remove(id) { step('source.remove'); timers.delete(id); }},
        },
        Meta: {BackendCapabilities: {BARRIERS: 1}, BarrierDirection: {POSITIVE_Y: 1},
            Barrier: class extends Signals {
                constructor() { super('barrier'); step('barrier.new'); edges.push(this); }
            }},
        Shell: {ActionMode: {NORMAL: 1}},
        Layout: {PressureBarrier: class extends Signals {
            constructor() { super('pressure'); step('pressure.new'); pressures.push(this); }
            addBarrier() { step('pressure.add'); }
        }},
        Main: {layoutManager: {primaryMonitor: {x: 0, y: 0, width: 1280},
            _queueUpdateRegions() { step('regions'); }}},
        global: {backend: {capabilities: barriers ? 1 : 0}, get_pointer: () => [100, 0],
            compositor: {disable_unredirect() { holds++; }, enable_unredirect() { holds--; }}},
    });
    return {actor, zone, events, failures, hooks, timers, pressures, edges, history,
        get holds() { return holds; }, get reveals() { return reveals; },
        create: () => new Panel(actor, zone, () => reveals++)};
}
let count = 0;
function test(name, run) {
    if (process.env.BGC_TEST_CASE && name !== process.env.BGC_TEST_CASE) return;
    try { run(); count++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
}
const released = h => {
    assert.equal(h.zone.callbacks.size, 0);
    assert.equal(h.holds, 0);
    assert.equal(h.timers.size, 0);
    assert.equal(h.actor.translation_y, 7);
};

for (const signal of ['enter-event', 'leave-event']) {
    test(`constructor failure at ${signal}`, () => {
        const h = harness(), error = new Error(signal);
        h.failures.set(`zone.connect.${signal}`, error);
        assert.throws(h.create, e => e === error);
        released(h);
    });
}
for (const point of ['pressure.new', 'barrier.new', 'pressure.add', 'pressure.connect.trigger']) {
    test(`barrier construction failure at ${point}`, () => {
        const h = harness(), panel = h.create(), error = new Error(point);
        h.failures.set(point, error);
        assert.throws(() => panel.setEnabled(true), e => e === error);
        assert.ok(h.pressures.every(p => p.destroyed));
        assert.ok(h.edges.every(b => b.destroyed));
        assert.equal(panel._pressure, null);
        assert.equal(panel._barrier, null);
        h.failures.clear();
        panel.reposition();
        assert.ok(panel._pressure);
        panel.destroy();
        released(h);
    });
}
test('stale animation cannot hide replacement panel', () => {
    const h = harness(), old = h.create();
    old.setVisible(false);
    const finish = h.actor.transition.onComplete;
    old.destroy();
    const current = h.create();
    current.setVisible(true, true);
    finish();
    assert.equal(h.actor.visible, true);
    assert.equal(h.holds, 1);
    current.destroy();
    released(h);
});
test('reversed animation cannot release current compositing hold', () => {
    const h = harness(), panel = h.create();
    panel.setVisible(false);
    const hide = h.actor.transition.onComplete;
    panel.setVisible(true);
    hide();
    assert.equal(h.actor.visible, true);
    assert.equal(h.holds, 1);
    panel.destroy();
    released(h);
});
for (const point of ['pressure.destroy', 'barrier.destroy', 'zone.disconnect.1', 'zone.disconnect.2', 'actor.remove']) {
    test(`cleanup continues after ${point}`, () => {
        const h = harness(), panel = h.create();
        panel.setEnabled(true);
        panel.setVisible(true, true);
        h.failures.set(point, new Error(point));
        panel.destroy();
        assert.equal(h.holds, 0);
        assert.equal(h.timers.size, 0);
        assert.equal(h.actor.translation_y, 7);
        assert.ok(h.events.includes('barrier.destroy'));
        assert.ok(h.events.includes('zone.disconnect.2'));
        h.failures.clear();
        h.events.length = 0;
        for (const callback of h.history) callback();
        panel.setEnabled(true); panel.setVisible(true); panel.reposition(); panel.destroy();
        assert.equal(panel.pointerInside(), false);
        assert.deepEqual(h.events, []);
    });
}
test('pressure callback from replaced barrier is inert', () => {
    const h = harness(), panel = h.create();
    panel.setEnabled(true);
    const old = [...panel._pressure.callbacks.values()][0];
    panel.reposition();
    old();
    assert.equal(h.reveals, 0);
    [...panel._pressure.callbacks.values()][0]();
    assert.equal(h.reveals, 1);
    panel.destroy();
    released(h);
});
test('cancelled barrier release cannot destroy replacement barrier', () => {
    const h = harness(), panel = h.create();
    panel.setEnabled(true); panel.setVisible(true, true);
    const old = h.timers.get(panel._barrierRelease).callback;
    panel.setVisible(false, true);
    const current = panel._barrier;
    old();
    assert.equal(panel._barrier, current);
    assert.ok(!current.destroyed);
    panel.destroy();
    released(h);
});
test('cancelled dwell cannot clear or reveal a newer dwell', () => {
    const h = harness(false), panel = h.create();
    panel.setEnabled(true); panel._enter();
    const old = h.timers.get(panel._dwell).callback;
    panel._cancelDwell(); panel._enter();
    const current = panel._dwell;
    old();
    assert.equal(panel._dwell, current);
    assert.equal(h.reveals, 0);
    assert.equal(h.timers.get(current).delay, 250);
    h.timers.get(current).callback(); h.timers.delete(current);
    assert.equal(h.reveals, 1);
    panel.destroy();
    released(h);
});
for (const barriers of [false, true]) {
    test(`failed timer cancellation remains inert: ${barriers}`, () => {
        const h = harness(barriers), panel = h.create();
        panel.setEnabled(true);
        if (barriers) panel.setVisible(true, true); else panel._enter();
        h.failures.set('source.remove', new Error('remove'));
        panel.destroy();
        assert.equal(h.holds, 0);
        assert.equal(h.zone.callbacks.size, 0);
        h.failures.clear();
        h.events.length = 0;
        for (const {callback} of h.timers.values()) assert.equal(callback(), false);
        assert.equal(h.reveals, 0);
        assert.deepEqual(h.events, []);
    });
}
test('reentrant cleanup releases each resource once', () => {
    const h = harness(), panel = h.create();
    panel.setEnabled(true); panel.setVisible(true, true);
    h.hooks.set('pressure.destroy', () => panel.destroy());
    panel.destroy(); panel.destroy();
    assert.equal(h.events.filter(e => e === 'pressure.destroy').length, 1);
    assert.equal(h.events.filter(e => e === 'barrier.destroy').length, 1);
    released(h);
});
test('original barrier error survives cleanup failure', () => {
    const h = harness(), panel = h.create(), error = new Error('create');
    h.failures.set('pressure.add', error);
    h.failures.set('pressure.destroy', new Error('cleanup'));
    assert.throws(() => panel.setEnabled(true), e => e === error);
    assert.equal(h.edges[0].destroyed, true);
    h.failures.clear();
    panel.destroy();
    released(h);
});
console.log(`${count} panel autohide lifecycle scenarios passed`);
