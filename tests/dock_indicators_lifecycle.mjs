// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const code = fs.readFileSync(new URL('dockRunningIndicators.js', root), 'utf8')
    .replace(/^import .*;$/gm, '').replaceAll('export ', '');
const classes = ['community-indicator-dot', 'community-indicator-hybrid', 'community-indicator-desk-ux'];

function harness() {
    const events = [], failures = new Map(), hooks = new Map(), warnings = [];
    const step = name => {
        events.push(name);
        hooks.get(name)?.();
        if (failures.has(name)) throw failures.get(name);
    };
    const emitter = name => ({
        callbacks: new Map(), history: [], nextId: 0,
        connect(signal, callback) {
            step(`${name}.connect`);
            this.history.push(callback);
            this.callbacks.set(++this.nextId, callback);
            return this.nextId;
        },
        disconnect(id) { step(`${name}.disconnect`); this.callbacks.delete(id); },
        emit() { for (const callback of [...this.callbacks.values()]) callback(); },
    });
    const actor = name => ({
        classes: new Set(['unrelated']),
        remove_style_class_name(value) { step(`${name}.remove`); this.classes.delete(value); },
        add_style_class_name(value) { step(`${name}.add`); this.classes.add(value); },
        dash: {_appIcons: [0, 1].map(i => ({
            _syncCommunityIndicatorStyle() { step(`${name}.icon${i}`); },
        }))},
    });
    const settings = Object.assign(emitter('settings'), {
        value: 0,
        get_enum() { step('settings.get'); return this.value; },
        set_enum(key, value) { step('settings.set'); this.value = value; this.emit(); },
    });
    const docks = [actor('dock0'), actor('dock1')];
    const manager = Object.assign(emitter('manager'), {_allDocks: docks});
    const Controller = vm.runInNewContext(`${code}\nDockRunningIndicators`, {
        console: {warn: message => warnings.push(message)},
        St: {Side: {TOP: 0, RIGHT: 1, BOTTOM: 2, LEFT: 3}},
        Clutter: {ActorAlign: {START: 0, END: 1, CENTER: 2}},
    });
    return {events, failures, hooks, warnings, settings, manager, docks, Controller,
        create: style => new Controller(settings, manager, style)};
}

let count = 0;
function test(name, run) {
    if (process.env.BGC_TEST_CASE && name !== process.env.BGC_TEST_CASE) return;
    try { run(); count++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
}
const released = h => {
    assert.equal(h.settings.callbacks.size, 0);
    assert.equal(h.manager.callbacks.size, 0);
};

for (const point of ['settings.connect', 'manager.connect', 'settings.get', 'settings.set',
    'dock0.remove', 'dock0.add', 'dock0.icon0']) {
    test(`constructor failure at ${point}`, () => {
        const h = harness(), error = new Error(point);
        h.failures.set(point, error);
        if (point === 'settings.set') h.settings.value = 2;
        assert.throws(() => h.create(), value => value === error);
        released(h);
        h.failures.clear();
        const controller = h.create();
        controller.destroy();
        released(h);
    });
}
test('cleanup errors preserve construction error', () => {
    const h = harness(), original = new Error('construction');
    h.failures.set('dock0.add', original);
    h.failures.set('settings.disconnect', new Error('disconnect'));
    h.failures.set('dock1.remove', new Error('actor'));
    assert.throws(() => h.create(), value => value === original);
    assert.equal(h.manager.callbacks.size, 0);
    h.failures.clear();
    h.events.length = 0;
    h.settings.emit();
    assert.deepEqual(h.events, []);
});
for (const point of ['dock0.remove', 'settings.disconnect', 'manager.disconnect']) {
    test(`cleanup continues after ${point}`, () => {
        const h = harness(), controller = h.create();
        h.failures.set(point, new Error(point));
        controller.destroy();
        assert.ok(h.events.includes('settings.disconnect'));
        assert.ok(h.events.includes('manager.disconnect'));
        assert.deepEqual([...h.docks[1].classes], ['unrelated']);
        assert.equal(controller._dockManager, null);
        assert.equal(controller._dockSettings, null);
        h.failures.clear();
        h.events.length = 0;
        for (const callback of [...h.settings.history, ...h.manager.history]) callback();
        controller.destroy();
        assert.deepEqual(h.events, []);
    });
}
test('retired controller cannot repaint replacement', () => {
    const h = harness(), old = h.create();
    old.destroy();
    const current = h.create('hybrid');
    h.events.length = 0;
    h.settings.history[0](); h.manager.history[0]();
    old.setStyle('desk-ux'); old.applyIconStyle(h.docks[0]);
    old.applyAppearance({}, true, 2); old.destroy();
    assert.deepEqual(h.events, []);
    assert.deepEqual([...h.docks[0].classes], ['unrelated', classes[1]]);
    current.destroy();
    released(h);
});
test('reentrant destroy disconnects once', () => {
    const h = harness(), controller = h.create();
    h.hooks.set('settings.disconnect', () => controller.destroy());
    controller.destroy(); controller.destroy();
    assert.equal(h.events.filter(e => e === 'settings.disconnect').length, 1);
    assert.equal(h.events.filter(e => e === 'manager.disconnect').length, 1);
    released(h);
});
test('destroy during icon update stops remaining updates', () => {
    const h = harness(), controller = h.create();
    h.events.length = 0;
    h.hooks.set('dock0.icon0', () => controller.destroy());
    controller.setStyle('hybrid');
    assert.ok(!h.events.includes('dock0.icon1'));
    assert.ok(!h.events.includes('dock1.add'));
    released(h);
});
test('destroy during class clearing cannot restore a class', () => {
    const h = harness(), controller = h.create();
    h.hooks.set('dock0.remove', () => controller.destroy());
    controller.setStyle('hybrid');
    assert.deepEqual([...h.docks[0].classes], ['unrelated']);
    released(h);
});
test('settings normalization still reapplies current style', () => {
    const h = harness(), controller = h.create('desk-ux');
    h.settings.value = 2;
    h.settings.emit();
    assert.equal(h.settings.value, 0);
    assert.deepEqual([...h.docks[0].classes], ['unrelated', classes[2]]);
    h.manager.emit();
    assert.deepEqual([...h.docks[1].classes], ['unrelated', classes[2]]);
    controller.destroy();
});
for (const [style, size, radius] of [['dot', [6, 6], 99], ['hybrid', [18, 4], 2],
    ['desk-ux', [18, 3], 2], ['invalid', [6, 6], 99]]) {
    test(`appearance preserved: ${style}`, () => {
        const h = harness(), controller = h.create(style);
        for (const position of [0, 1, 2, 3]) {
            const dot = {set_size(w, v) { this.size = [w, v]; }, set_style(s) { this.css = s; }};
            controller.applyAppearance(dot, true, position);
            assert.deepEqual(dot.size, position % 2 ? [...size].reverse() : size);
            assert.ok(dot.css.includes(`border-radius: ${radius}px`));
        }
        controller.destroy();
        released(h);
    });
}
console.log(`${count} dock indicator lifecycle scenarios passed`);
