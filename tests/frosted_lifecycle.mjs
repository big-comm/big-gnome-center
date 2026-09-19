// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import vm from 'node:vm';

const root = process.env.BGC_FROSTED_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_FROSTED_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/', import.meta.url);
const source = fs.readFileSync(new URL('extension.js', root), 'utf8')
    .replace(/^import .*;$/gm, '').replace('export default ', '')
    .replaceAll("import('./", "loadModule('./");
const deferred = () => {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return {promise, resolve, reject};
};
async function flush() { for (let i = 0; i < 12; i++) await Promise.resolve(); }

function harness(major = 51) {
    const events = [], failures = new Set(), callbacks = [], timers = new Map();
    const errors = [], warnings = [], gates = new Map(), powers = [], surfaces = [];
    let nextId = 0;
    const record = name => {
        events.push(name);
        if (failures.has(name)) throw new Error(name);
    };
    class Settings {
        constructor() { this.settings_schema = {has_key: () => true}; }
        get_string(key) { return key === 'blur-mode' ? 'dynamic' : 'prefer-dark'; }
        get_boolean() { return true; }
        get_int(key) { return key === 'blur-strength' ? 30 : 37; }
        get_enum() { return 3; }
    }
    class Resource {
        constructor(name) { this.name = name; }
        enable() { record(`${this.name}.enable`); }
        destroy() { record(`${this.name}.destroy`); }
        refresh() { record(`${this.name}.refresh`); }
    }
    class ShellSurfaces extends Resource {
        constructor() { super('surfaces'); surfaces.push(this); record('surfaces.new'); }
    }
    const compositor = {
        value: [11, 1, 0.1],
        get_background_blur_params() { return [...this.value]; },
        set_background_blur_params(...values) { this.value = values; record('native.set'); },
    };
    const Extension = vm.runInNewContext(`${source}\nFrostedGlassExtension`, {
        Gio: {Settings}, Config: {PACKAGE_VERSION: `${major}.0`},
        Extension: class {getSettings() { return new Settings(); }},
        console: {warn: x => warnings.push(x), error: x => errors.push(x), debug() {}},
        Main: {extensionManager: {lookup: () => null}},
        global: {settings: new Settings(), compositor, context: {get_wayland_compositor: () => ({})}},
        GLib: {
            PRIORITY_DEFAULT_IDLE: 0, SOURCE_REMOVE: false,
            build_filenamev: parts => parts.join('/'),
            source_remove(id) { record('timer.remove'); timers.delete(id); },
            idle_add(priority, callback) { timers.set(++nextId, callback); return nextId; },
        },
        ConnectionManager: class {
            connect(object, name, callback) { callbacks.push(callback); }
            disconnectAll() { record('connections.disconnect'); }
        },
        OverviewController: class extends Resource { constructor() { super('overview'); } },
        PowerMonitor: class extends Resource {
            constructor(callback) { super('power'); this.callback = callback; powers.push(this); }
        },
        WindowStyles: class extends Resource { constructor() { super('styles'); } },
        async loadModule(name) {
            const gate = gates.get(name);
            if (gate) await gate.promise;
            record(`import:${name}`);
            return name === './roundedBackend.js'
                ? {prepareRoundedBackend: async () => {
                    const prepare = gates.get('prepare');
                    if (prepare) await prepare.promise;
                    record('prepare');
                }} : {ShellSurfaces};
        },
    });
    const extension = new Extension();
    extension.path = '/test/frosted';
    return {extension, events, failures, callbacks, timers, errors, warnings, gates,
        powers, surfaces, compositor};
}
let checks = 0;
async function test(name, run) {
    if (process.env.BGC_TEST_CASE && name !== process.env.BGC_TEST_CASE)
        return;
    try { await run(); checks++; } catch (error) { throw new Error(name, {cause: error}); }
}

for (const major of [50, 51]) {
    await test(`normal enable/disable and coalescing: ${major}`, async () => {
        const h = harness(major), e = h.extension;
        e.enable(); await flush();
        assert.equal(h.surfaces.length, major === 51 ? 1 : 0);
        const writer = e._windowStyles;
        const generation = e._generation;
        e.enable();
        assert.equal(e._generation, generation);
        h.callbacks.forEach(callback => callback());
        h.powers[0].callback();
        assert.equal(h.timers.size, 1);
        const id = e._refreshId;
        h.timers.get(id)(); h.timers.delete(id);
        assert.equal(e._refreshId, 0);
        e.disable();
        assert.deepEqual(h.compositor.value, [11, 1, 0.1]);
        assert.equal(e._settings, null);
        e._queueRefresh();
        assert.equal(h.timers.size, 0);
        e.enable(); await flush();
        assert.equal(e._windowStyles, writer, 'window-style writer must span generations');
        e.disable();
    });
    await test(`retired signals and idle callback: ${major}`, async () => {
        const h = harness(major), e = h.extension;
        e.enable(); await flush();
        const retired = [...h.callbacks, h.powers[0].callback];
        e._queueRefresh();
        const staleIdle = h.timers.get(e._refreshId);
        h.failures.add('timer.remove');
        e.disable();
        h.failures.clear();
        e.enable(); await flush();
        e._queueRefresh();
        const current = e._refreshId, before = h.events.length;
        retired.forEach(callback => callback());
        staleIdle();
        assert.equal(e._refreshId, current);
        assert.equal(h.events.length, before);
        h.timers.get(current)();
        assert.ok(h.events.length > before);
        e.disable();
    });
}

for (const phase of ['./roundedBackend.js', 'prepare', './shellSurfaces.js']) {
    for (const reenable of [false, true]) {
        for (const reject of [false, true]) {
            await test(`late ${phase}: reenable=${reenable}, reject=${reject}`, async () => {
                const h = harness(), e = h.extension, gate = deferred();
                h.gates.set(phase, gate);
                e.enable(); await flush();
                assert.equal(e._surfaces, null);
                e.disable();
                h.gates.delete(phase);
                if (reenable) { e.enable(); await flush(); }
                const current = e._surfaces, before = h.events.length;
                if (reject) gate.reject(new Error('retired import failure'));
                else gate.resolve();
                await flush();
                assert.equal(e._surfaces, current);
                const extra = h.events.slice(before);
                assert.ok(!extra.includes('surfaces.destroy'));
                assert.ok(!extra.includes('surfaces.new'));
                assert.ok(!extra.includes('native.set'));
                if (phase === './roundedBackend.js') assert.ok(!extra.includes('prepare'));
                assert.equal(h.errors.length, Number(reject));
                e.disable();
            });
        }
    }
}

for (const cleanupFails of [false, true]) {
    await test(`backend failure cleans its own surfaces: ${cleanupFails}`, async () => {
        const h = harness(), e = h.extension;
        h.failures.add('surfaces.enable');
        if (cleanupFails) h.failures.add('surfaces.destroy');
        e.enable(); await flush();
        assert.equal(e._surfaces, null);
        assert.ok(h.events.includes('surfaces.destroy'));
        assert.equal(h.errors.length, 1);
        assert.equal(h.warnings.length, Number(cleanupFails));
        h.failures.clear();
        e.disable(); e.enable(); await flush();
        assert.ok(e._surfaces);
        e.disable();
    });
}

for (const failure of ['timer.remove', 'connections.disconnect', 'styles.destroy',
    'surfaces.destroy', 'overview.destroy', 'power.destroy']) {
    await test(`independent disable cleanup: ${failure}`, async () => {
        const h = harness(), e = h.extension;
        e.enable(); await flush();
        e._queueRefresh();
        h.events.length = 0;
        h.failures.add(failure);
        e.disable();
        for (const step of ['timer.remove', 'connections.disconnect', 'styles.destroy',
            'surfaces.destroy', 'overview.destroy', 'power.destroy', 'native.set'])
            assert.ok(h.events.includes(step), step);
        assert.equal(e._settings, null);
        assert.equal(e._surfaces, null);
        assert.equal(e._disabling, false);
        assert.deepEqual(h.compositor.value, [11, 1, 0.1]);
        h.failures.clear();
        e.enable(); await flush();
        assert.ok(e._surfaces);
        e.disable();
    });
}
console.log(`${checks} Frosted lifecycle scenarios passed`);
