// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const code = fs.readFileSync(new URL('dockHoverEffects.js', root), 'utf8')
    .replace(/^import .*;$/gm, '').replaceAll('export ', '');

function harness(scaleFactor = 1) {
    const events = [], failures = new Map(), hooks = new Map(), timers = new Map();
    const emitters = [], clones = [], chrome = new Set();
    let id = 0;
    const step = name => {
        events.push(name); hooks.get(name)?.();
        if (failures.has(name)) throw failures.get(name);
    };
    class Actor {
        constructor(name) {
            this.name = name; this.signals = new Map(); this.history = [];
            this.visible = true; this.opacity = 220; this.mapped = false; emitters.push(this);
        }
        connect(signal, callback) {
            step(`${this.name}.connect.${signal}`);
            this.signals.set(++id, {signal, callback}); this.history.push(callback); return id;
        }
        disconnect(key) { step(`${this.name}.disconnect`); this.signals.delete(key); }
        emit(signal) { for (const s of [...this.signals.values()]) if (s.signal === signal) s.callback(); }
        set_size(w, h) { step(`${this.name}.size`); this.size = [w, h]; }
        set_position() { step(`${this.name}.position`); }
        set_pivot_point() {}
        get_transformed_position() { return [0, 0]; }
        get_transformed_size() { return [48, 48]; }
        get_paint_visibility() { return true; }
        hide() { step(`${this.name}.hide`); this.visible = false; }
        show() { step(`${this.name}.show`); this.visible = true; }
        destroy() { step(`${this.name}.destroy`); this.emit('destroy'); this.signals.clear(); this.destroyed = true; chrome.delete(this); }
        remove_style_class_name() {}
        add_style_class_name() {}
    }
    const Effects = vm.runInNewContext(`${code}\nDockHoverEffects`, {
        console: {warn() {}}, global: {stage: {}, get_pointer: () => [24, 24]},
        Clutter: {Clone: class extends Actor {
            constructor() { super('clone'); step('clone.new'); clones.push(this); }
        }},
        Main: {uiGroup: {add_child(actor) { step('chrome.add'); chrome.add(actor); }}},
        GLib: {PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false, SOURCE_CONTINUE: true,
            timeout_add(priority, delay, callback) { step('source.new'); timers.set(++id, {delay, callback}); return id; },
            source_remove(key) { step('source.remove'); timers.delete(key); }},
        St: {Side: {TOP: 0, BOTTOM: 1, LEFT: 2, RIGHT: 3},
            ThemeContext: {get_for_stage: () => ({scale_factor: scaleFactor})}},
    });
    const fx = new Effects(); fx.setEffect('magnify', 40);
    const child = () => new Actor('child');
    function dock() {
        const bin = new Actor('bin'), actor = new Actor('actor'), dash = new Actor('dash');
        bin.child = child();
        const requests = [];
        const original = function (size, marker) { requests.push([this, size, marker]); return size; };
        const icon = {iconSize: 48, _iconBin: bin, createIcon: original, get_stage: () => true,
            _createIconTexture(size) { step('texture'); this.createIcon(size); }};
        actor.icon = icon;
        dash._position = 1; dash.iconSize = 48; dash._box = {get_children: () => [{child: actor}]};
        return {dash, actor, bin, icon, original, requests};
    }
    function attach(d = dock()) {
        fx.applyStyle(d.dash);
        const record = fx._records.get(d.dash);
        fx._tick(d.dash, record);
        return {...d, record, state: record.states.get(d.actor)};
    }
    return {fx, dock, attach, child, events, failures, hooks, timers, emitters, clones, chrome};
}
function clean(h) {
    assert.equal(h.fx._records.size, 0);
    assert.equal(h.timers.size, 0);
    assert.equal(h.chrome.size, 0);
    assert.ok(h.clones.every(c => c.destroyed));
    assert.ok(h.emitters.every(e => e.signals.size === 0));
}
let count = 0;
function test(name, run) {
    if (process.env.BGC_TEST_CASE && name !== process.env.BGC_TEST_CASE) return;
    try { run(); count++; } catch (error) { error.message = `${name}: ${error.message}`; throw error; }
}
test('pending icon mapping is disconnected on release', () => {
    const h = harness(), d = h.attach(), callback = d.bin.child.history[0];
    assert.equal(d.bin.child.signals.size, 1);
    h.fx.releaseAll(); clean(h);
    d.bin.child.mapped = true; h.events.length = 0; callback();
    assert.deepEqual(h.events, []);
    assert.equal(d.icon.createIcon, d.original);
    assert.equal(d.actor.opacity, 220);
});
test('repeated constraint requests own one mapping signal', () => {
    const h = harness(), d = h.attach();
    for (let i = 0; i < 8; i++) d.bin.emit('child-added');
    assert.equal(d.bin.child.signals.size, 1);
    h.fx.releaseAll(); clean(h);
});
test('replaced icon mapping cannot resize the retired child', () => {
    const h = harness(), d = h.attach(), old = d.bin.child;
    const callback = old.history[0];
    d.bin.child = h.child(); d.bin.emit('child-added');
    assert.equal(old.signals.size, 0);
    old.mapped = true; h.events.length = 0; callback(); assert.deepEqual(h.events, []);
    d.bin.child.mapped = true; d.bin.child.emit('notify::mapped');
    assert.deepEqual(d.bin.child.size, [48, 48]);
    h.fx.releaseAll(); clean(h);
});
for (const scale of [1, 2]) {
    test(`mapped source size at scale ${scale}`, () => {
        const h = harness(scale), d = h.attach();
        assert.equal(d.requests[0][1], 68);
        d.bin.child.mapped = true; d.bin.child.emit('notify::mapped');
        assert.deepEqual(d.bin.child.size, [48 * scale, 48 * scale]);
        assert.equal(d.bin.child.signals.size, 0);
        h.fx.releaseAll(); clean(h);
    });
}
test('retained wrapper delegates without magnifying after release', () => {
    const h = harness(), d = h.attach(), wrapper = d.icon.createIcon, receiver = {};
    assert.equal(wrapper.call(receiver, 10, 'active'), 14);
    h.fx.releaseAll();
    assert.equal(wrapper.call(receiver, 10, 'retired'), 10);
    assert.deepEqual(d.requests.at(-1), [receiver, 10, 'retired']); clean(h);
});
test('external wrapper survives release', () => {
    const h = harness(), d = h.attach(), captured = d.icon.createIcon;
    const external = function (size) { return captured.call(this, size); };
    d.icon.createIcon = external; h.fx.releaseAll();
    assert.equal(d.icon.createIcon, external);
    assert.equal(d.icon.createIcon(12), 12); clean(h);
});
test('retired timer and destroy callbacks cannot detach reattached dock', () => {
    const h = harness(), d = h.attach(), callback = h.timers.get(d.record.sourceId).callback;
    const destroy = d.dash.history[0];
    h.fx.releaseAll(); const replacement = h.attach(d);
    h.events.length = 0;
    assert.equal(callback(), false); destroy();
    assert.deepEqual(h.events, []);
    assert.equal(h.fx._records.get(d.dash), replacement.record);
    h.fx.releaseAll(); clean(h);
});
test('tick failure cannot detach a replacement record', () => {
    const h = harness(), d = h.attach(), callback = h.timers.get(d.record.sourceId).callback;
    h.fx._tick = () => { h.fx.releaseAll(); h.fx.applyStyle(d.dash); throw new Error('old tick'); };
    assert.equal(callback(), false);
    assert.ok(h.fx._records.has(d.dash));
    h.fx.releaseAll(); clean(h);
});
test('retired tick cannot publish a new icon state', () => {
    const h = harness(), d = h.attach();
    h.fx._isDockShown = () => { h.fx.releaseAll(); h.fx.applyStyle(d.dash); return true; };
    h.fx._tick(d.dash, d.record);
    assert.equal(d.record.states.size, 0);
    assert.equal(h.chrome.size, 0);
    h.fx.releaseAll(); clean(h);
});
for (const point of ['dash.connect.destroy', 'source.new']) {
    test(`attach failure: ${point}`, () => {
        const h = harness(), d = h.dock(), error = new Error(point);
        h.failures.set(point, error);
        assert.throws(() => h.fx.applyStyle(d.dash), e => e === error);
        clean(h);
    });
}
for (const point of ['clone.hide', 'chrome.add', 'bin.connect.child-added', 'texture',
    'child.connect.notify::mapped', 'actor.connect.destroy']) {
    test(`state creation failure: ${point}`, () => {
        const h = harness(), d = h.dock(), error = new Error(point);
        h.fx.applyStyle(d.dash); const record = h.fx._records.get(d.dash);
        h.failures.set(point, error);
        assert.throws(() => h.fx._tick(d.dash, record), e => e === error);
        assert.equal(record.states.size, 0);
        assert.equal(d.icon.createIcon, d.original);
        h.failures.clear(); h.fx.releaseAll(); clean(h);
    });
}
for (const point of ['source.remove', 'dash.disconnect', 'actor.disconnect',
    'child.disconnect', 'bin.disconnect', 'texture', 'clone.destroy']) {
    test(`independent cleanup: ${point}`, () => {
        const h = harness(), first = h.attach(), second = h.attach();
        const callbacks = [...h.emitters.flatMap(e => e.history), ...[...h.timers.values()].map(t => t.callback)];
        h.failures.set(point, new Error(point)); h.events.length = 0;
        h.fx.releaseAll();
        assert.equal(h.fx._records.size, 0);
        assert.equal(first.state.retired, true); assert.equal(second.state.retired, true);
        assert.equal(first.icon.createIcon, first.original); assert.equal(second.icon.createIcon, second.original);
        assert.equal(h.events.filter(e => e === 'clone.destroy').length, 2);
        assert.equal(first.actor.opacity, 220); assert.equal(second.actor.opacity, 220);
        h.failures.clear(); h.events.length = 0; callbacks.forEach(cb => cb());
        h.fx.releaseAll(); assert.deepEqual(h.events, []);
    });
}
test('actor destruction releases hooks without recreating textures', () => {
    const h = harness(), d = h.attach(); h.events.length = 0;
    d.actor.destroy();
    assert.equal(d.record.states.size, 0);
    assert.equal(d.icon.createIcon, d.original);
    assert.equal(d.bin.signals.size, 0); assert.equal(d.bin.child.signals.size, 0);
    assert.equal(h.events.includes('texture'), false);
    h.fx.releaseAll(); clean(h);
});
test('external opacity survives release', () => {
    const h = harness(), d = h.attach(); d.actor.opacity = 150;
    h.fx.releaseAll(); assert.equal(d.actor.opacity, 150); clean(h);
});
test('release during texture creation cannot publish retired state', () => {
    const h = harness(), d = h.dock();
    h.hooks.set('texture', () => h.fx.releaseAll());
    h.attach(d); clean(h);
});
test('intensity replacement retires old icon hooks', () => {
    const h = harness(), d = h.attach(), wrapper = d.icon.createIcon;
    h.fx.setEffect('magnify', 60); h.attach(d);
    assert.equal(wrapper.call(d.icon, 10), 10);
    assert.equal(d.icon.createIcon(10), 16);
    h.fx.releaseAll(); clean(h);
});
test('release cannot detach a dock replaced during another cleanup', () => {
    const h = harness(); h.attach(); const second = h.attach();
    let replace = true;
    h.hooks.set('texture', () => {
        if (!replace) return;
        replace = false;
        h.fx._detach(second.dash, true);
        h.fx.applyStyle(second.dash);
    });
    h.fx.releaseAll();
    assert.ok(h.fx._records.has(second.dash));
    assert.notEqual(h.fx._records.get(second.dash), second.record);
    h.fx.releaseAll(); clean(h);
});
console.log(`${count} dock hover lifecycle scenarios passed`);
