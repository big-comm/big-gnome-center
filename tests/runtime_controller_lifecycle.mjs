// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import vm from 'node:vm';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const source = fs.readFileSync(new URL('runtimeController.js', root), 'utf8')
    .replace(/^import .*;$/gm, '').replaceAll('export ', '');
const profiles = fs.readFileSync(new URL('layoutProfiles.js', root), 'utf8')
    .replaceAll('export ', '');
const layouts = ['BigGnome', 'G-Unity', 'Hybrid', 'Desk UX', 'Classic', 'Minimal'];
const deferred = () => {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return {promise, resolve, reject};
};

function harness(layout = 'BigGnome') {
    const errors = [], warnings = [], components = [], settings = [];
    class Settings {
        constructor() {
            this.layout = layout;
            this.signals = new Map();
            this.history = [];
            this.disconnected = [];
            settings.push(this);
        }
        get_string() { return this.layout; }
        get_value() { return {deep_unpack: () => ({})}; }
        connect(key, callback) {
            const id = this.history.push(callback);
            this.signals.set(id, callback);
            return id;
        }
        disconnect(id) {
            this.disconnected.push(id);
            this.signals.delete(id);
            if (this.failDisconnect === id)
                throw new Error('injected signal failure');
        }
    }
    const component = name => class {
        constructor() {
            this.name = name;
            this.activations = [];
            this.cleanups = 0;
            components.push(this);
        }
        enable() {}
        apply() {}
        activate(profile) {
            this.activations.push(profile?.layout);
            if (this.failActivation)
                throw new Error('injected activation failure');
            return this.pending?.promise;
        }
        deactivate() {
            this.cleanups++;
            this.onCleanup?.();
            if (this.failCleanup)
                throw new Error('injected component failure');
        }
        destroy() { this.deactivate(); }
    };
    const Controller = vm.runInNewContext(`${profiles}\n${source}\nRuntimeController`, {
        Gio: {Settings, SettingsSchemaSource: {get_default: () => ({lookup: () => ({})})}},
        DockRuntime: component('dock'), TaskbarRuntime: component('taskbar'),
        NativePanelOpacityIntegration: component('native'),
        ShellPopoverThemeIntegration: component('popover'),
        StartupOverviewIntegration: component('overview'),
        console: {info() {}, error: error => errors.push(error), warn: error => warnings.push(error)},
    });
    const controller = new Controller({});
    controller.enable();
    return {controller, errors, warnings, components, settings};
}

let checks = 0;
async function test(name, run) {
    try {
        await run();
        checks++;
    } catch (error) {
        throw new Error(name, {cause: error});
    }
}

for (const initial of layouts) {
    for (const target of layouts) {
        await test(`${initial} -> ${target}`, async () => {
            const {controller: c, errors} = harness(initial);
            await c._syncPromise;
            assert.equal(c._activeProfile.layout, initial);
            const taskbar = c._taskbar, dock = c._dock;
            const beforeTaskbar = taskbar.cleanups, beforeDock = dock.cleanups;
            c._settings.layout = target;
            c._queueSync();
            await c._syncPromise;
            assert.equal(c._activeProfile.layout, target);
            if (['Hybrid', 'Desk UX', 'Classic'].includes(initial) &&
                ['Hybrid', 'Desk UX', 'Classic'].includes(target))
                assert.equal(taskbar.cleanups, beforeTaskbar);
            if (initial === target && ['BigGnome', 'G-Unity'].includes(initial))
                assert.equal(dock.cleanups, beforeDock);
            assert.deepEqual(errors, []);
            c.disable();
        });
    }
}

await test('queued obsolete generations never activate', async () => {
    const {controller: c} = harness();
    for (const layout of layouts) {
        c._settings.layout = layout;
        c._queueSync();
    }
    await c._syncPromise;
    assert.equal(c._activeProfile.layout, 'Minimal');
    assert.equal(c._dock.activations.length, 0);
    assert.equal(c._taskbar.activations.length, 0);
    assert.equal(c._nativePanelOpacity.activations.length, 1);
    c.disable();
});

for (const reenable of [false, true]) {
    for (const reject of [false, true]) {
        await test(`pending activation retired: reenable=${reenable}, reject=${reject}`, async () => {
            const {controller: c, errors, settings} = harness('Desk UX');
            const oldTaskbar = c._taskbar;
            const pending = oldTaskbar.pending = deferred();
            const oldPromise = c._syncPromise;
            await Promise.resolve();
            assert.equal(c._activeProfile, null);
            c.disable();
            if (reenable) {
                c.enable();
                await c._syncPromise;
                assert.equal(c._activeProfile.layout, 'Desk UX');
            }
            const newTaskbar = c._taskbar;
            const before = newTaskbar?.cleanups;
            const generation = c._syncGeneration;
            for (const callback of settings[0].history)
                callback();
            assert.equal(c._syncGeneration, generation);
            if (reject)
                pending.reject(new Error('injected late failure'));
            else
                pending.resolve();
            await oldPromise;
            assert.equal(newTaskbar?.cleanups, before);
            assert.equal(c._activeProfile?.layout ?? null, reenable ? 'Desk UX' : null);
            assert.equal(errors.length, Number(reject));
            c.disable();
        });
    }
}

await test('old queued work cannot enter a new enable cycle', async () => {
    const {controller: c} = harness('Desk UX');
    const oldPromise = c._syncPromise;
    c.disable();
    c.enable();
    const taskbar = c._taskbar;
    await oldPromise;
    await c._syncPromise;
    assert.equal(taskbar.activations.length, 1);
    assert.equal(taskbar.cleanups, 0);
    c.disable();
});

await test('superseded pending taskbar retires before the next profile', async () => {
    const {controller: c, errors} = harness('Desk UX');
    const taskbar = c._taskbar, pending = taskbar.pending = deferred();
    await Promise.resolve();
    c._settings.layout = 'BigGnome';
    c._queueSync();
    pending.resolve();
    await c._syncPromise;
    assert.equal(c._activeProfile.layout, 'BigGnome');
    assert.ok(taskbar.cleanups > 0);
    assert.equal(c._dock.activations.length, 1);
    assert.deepEqual(errors, []);
    c.disable();
});

for (const layout of ['BigGnome', 'Desk UX', 'Minimal']) {
    await test(`failed activation is not published: ${layout}`, async () => {
        const {controller: c, errors} = harness(layout);
        const component = layout === 'BigGnome' ? c._dock :
            layout === 'Desk UX' ? c._taskbar : c._nativePanelOpacity;
        component.failActivation = true;
        await c._syncPromise;
        assert.equal(c._activeProfile, null);
        assert.equal(errors.length, 1);
        component.failActivation = false;
        c._queueSync();
        await c._syncPromise;
        assert.equal(c._activeProfile.layout, layout);
        c.disable();
    });
}

for (const failing of ['dock', 'taskbar', 'native', 'popover', 'overview', 'signal']) {
    await test(`disable continues after ${failing} failure`, async () => {
        const {controller: c, components, settings, warnings} = harness();
        await c._syncPromise;
        const before = components.map(item => item.cleanups);
        if (failing === 'signal')
            settings[0].failDisconnect = 1;
        else
            components.find(item => item.name === failing).failCleanup = true;
        c.disable();
        assert.equal(settings[0].disconnected.length, settings[0].history.length);
        components.forEach((item, index) => assert.equal(item.cleanups, before[index] + 1));
        assert.equal(c._settings, null);
        assert.equal(c._activeProfile, null);
        assert.equal(c._syncPromise, null);
        assert.equal(warnings.length, 1);
        c.disable();
        c._queueSync();
        components.forEach((item, index) => assert.equal(item.cleanups, before[index] + 1));
        c.enable();
        await c._syncPromise;
        assert.equal(c._activeProfile.layout, 'BigGnome');
        c.disable();
    });
}

await test('cleanup cannot erase a replacement registered reentrantly', async () => {
    const {controller: c} = harness();
    await c._syncPromise;
    c._dock.onCleanup = () => c.enable();
    c.disable();
    await c._syncPromise;
    assert.equal(c._enabled, true);
    assert.equal(c._activeProfile.layout, 'BigGnome');
    c.disable();
});

console.log(`${checks} runtime controller lifecycle scenarios passed`);
