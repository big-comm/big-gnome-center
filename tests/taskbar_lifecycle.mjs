// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import vm from 'node:vm';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const code = name => fs.readFileSync(new URL(name, root), 'utf8')
    .replace(/^import .*;$/gm, '').replaceAll('export ', '');
const deferred = () => {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return {promise, resolve, reject};
};
const profile = {layout: 'Desk UX'};
function harness() {
    const events = [], failures = new Set(), warnings = [], timers = new Map();
    let timerId = 0, disabled = [];
    const record = name => {
        events.push(name);
        if (failures.has(name)) throw new Error(name);
    };
    const resource = name => class {
        constructor() { record(`${name}.new`); }
        destroy() { record(`${name}.destroy`); }
        restore() { record(`${name}.restore`); }
        releaseAll() { record(`${name}.releaseAll`); }
        bind() { record(`${name}.bind`); }
        adoptPreviewMenu() {}
    };
    const Context = {
        DTP_EXTENSION: null, SETTINGS: null,
        initializeRuntimeContext(host, owner) {
            if (this.DTP_EXTENSION) throw new Error('Context already owned');
            this.DTP_EXTENSION = owner;
            this.SETTINGS = {get_int: () => 1};
            record('initialize');
        },
        clearRuntimeContext(owner) {
            if (this.DTP_EXTENSION === owner) {
                record('clearContext');
                this.DTP_EXTENSION = null;
                this.SETTINGS = null;
            }
        },
    };
    const PanelSettings = {
        pending: null,
        init() { record('init'); return this.pending?.promise; },
        adjustMonitorSettings() { record('adjust'); },
        setPanelSize() { record('size'); },
        clearCache() { record('cache'); },
    };
    const Main = {
        extensionManager: {_extensionOrder: []},
        layoutManager: {monitors: [{index: 0}], uiGroup: {
            add_style_class_name() { record('styles.add'); },
            remove_style_class_name() { record('styles.remove'); },
        }},
    };
    const sharedGlobal = {settings: {
        get_strv: () => disabled,
        set_strv: (key, value) => { disabled = value; },
    }};
    const sandbox = {
        Context, PanelSettings, Main, global: sharedGlobal,
        console: {warn: error => warnings.push(error)},
        GLib: {
            PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
            timeout_add(priority, delay, callback) { timers.set(++timerId, callback); return timerId; },
            Source: {remove(id) { record('timer.remove'); timers.delete(id); }},
        },
        EventEmitter: resource('emitter'), TaskbarAppActions: resource('actions'),
        TaskbarInteractions: resource('interactions'), TaskbarIndicatorRenderer: resource('indicators'),
        TaskbarMonitorHost: resource('monitors'), TaskbarPanelHost: resource('panels'),
        TaskbarServiceHost: resource('services'), TaskbarShellHooks: resource('hooks'),
        TaskbarStatusAreaHost: resource('status'),
        TaskbarStatusFullscreenIntegration: resource('fullscreen'),
        PanelManager: {PanelManager: class {
            constructor() {
                record('manager.new');
                this.allPanels = [{monitor: {index: 0}, taskbar: {previewMenu: {}}}];
            }
            enable() { record('manager.enable'); }
            disable() { record('manager.disable'); }
        }},
        ComponentHost: class {
            getSettings() { return {run_dispose() { record('settings.dispose'); }}; }
            loadStylesheet() { record('stylesheet.load'); }
            unloadStylesheet() { record('stylesheet.unload'); }
        },
        TaskbarVisibilityModes: class { apply() { record('visibility'); } },
    };
    const {Runtime, Surface} = vm.runInNewContext(
        `${code('taskbarSurface.js')}\n${code('taskbarRuntime.js')}
        ({Runtime: TaskbarRuntime, Surface: TaskbarSurfaceManager})`, sandbox);
    for (const name of ['_applyIndicator', '_applyHover', '_applyOpacity'])
        Runtime.prototype[name] = () => record(name);
    return {Runtime, Surface, Context, PanelSettings, Main, sharedGlobal, timers,
        events, failures, warnings, resetDisabled: () => { disabled = []; }};
}

let checks = 0;
async function test(name, run) {
    try { await run(); checks++; }
    catch (error) { throw new Error(name, {cause: error}); }
}
const activate = runtime => runtime.activate(profile, 'desk-ux', 'default', 70, 'always-visible', 40);

for (const reuse of [false, true]) {
    for (const reject of [false, true]) {
        await test(`late init completion: reuse=${reuse}, reject=${reject}`, async () => {
            const h = harness(), old = new h.Runtime({});
            const pending = h.PanelSettings.pending = deferred();
            const oldResult = activate(old).catch(error => error);
            old.deactivate();
            h.PanelSettings.pending = null;
            const replacement = reuse ? old : new h.Runtime({});
            await activate(replacement);
            const manager = replacement._surface._manager;
            const published = h.sharedGlobal.dashToPanel;
            const before = h.events.length;
            if (reject) pending.reject(new Error('retired init'));
            else pending.resolve();
            const result = await oldResult;
            assert.equal(Boolean(result), reject);
            assert.equal(h.events.length, before);
            assert.equal(replacement._active, true);
            assert.equal(replacement._surface._manager, manager);
            assert.equal(h.sharedGlobal.dashToPanel, published);
            assert.equal(h.Context.DTP_EXTENSION, replacement._surface);
            replacement.deactivate();
            assert.equal(h.Context.DTP_EXTENSION, null);
            assert.equal(h.sharedGlobal.dashToPanel, undefined);
        });
    }
}

await test('overlapping activation preserves the pending owner', async () => {
    const h = harness(), runtime = new h.Runtime({});
    h.PanelSettings.pending = deferred();
    const pending = activate(runtime);
    const generation = runtime._activationGeneration;
    await assert.rejects(activate(runtime), /already pending/);
    await assert.rejects(runtime._surface.enable(40), /already pending/);
    assert.equal(runtime._activationGeneration, generation);
    h.PanelSettings.pending.resolve();
    await pending;
    assert.equal(runtime._active, true);
    runtime.deactivate();
});

await test('another surface cannot clean an existing owner', async () => {
    const h = harness(), first = new h.Surface({}), second = new h.Surface({});
    await first.enable(40);
    const manager = first._manager;
    await assert.rejects(second.enable(40), /already owned/);
    second.destroy();
    assert.equal(h.Context.DTP_EXTENSION, first);
    assert.equal(first._manager, manager);
    first.destroy();
});

for (const failure of ['_applyIndicator', '_applyHover', '_applyOpacity', 'visibility',
    'stylesheet.load', 'initialize', 'fullscreen.new', 'panels.new', 'actions.new',
    'interactions.new', 'indicators.new', 'emitter.new', 'init', 'adjust', 'size',
    'styles.add', 'manager.new', 'manager.enable', 'monitors.bind']) {
    await test(`partial activation failure: ${failure}`, async () => {
        const h = harness(), runtime = new h.Runtime({});
        h.failures.add(failure);
        await assert.rejects(activate(runtime), error => error.message === failure);
        assert.equal(runtime._active, false);
        assert.equal(runtime._activating, false);
        assert.equal(runtime._profile, null);
        assert.equal(h.Context.DTP_EXTENSION, null);
        assert.equal(h.sharedGlobal.dashToPanel, undefined);
        assert.ok(h.events.includes('stylesheet.unload'));
        h.failures.clear();
        await activate(runtime);
        assert.equal(runtime._active, true);
        runtime.deactivate();
    });
}

const cleanupSteps = ['monitors.destroy', 'manager.disable', 'services.destroy', 'hooks.destroy',
    'panels.releaseAll', 'fullscreen.destroy', 'status.restore', 'cache', 'styles.remove',
    'actions.destroy', 'interactions.destroy', 'indicators.destroy', 'stylesheet.unload'];
for (const failure of cleanupSteps) {
    await test(`cleanup continues after ${failure}`, async () => {
        const h = harness(), runtime = new h.Runtime({});
        await activate(runtime);
        h.events.length = 0;
        h.failures.add(failure);
        runtime.deactivate();
        for (const step of cleanupSteps) assert.ok(h.events.includes(step), step);
        assert.equal(h.Context.DTP_EXTENSION, null);
        assert.equal(h.sharedGlobal.dashToPanel, undefined);
        assert.equal(runtime._surface._destroying, false);
        assert.equal(runtime._deactivating, false);
        assert.ok(h.warnings.length > 0);
        const before = h.events.length;
        runtime.deactivate();
        runtime._surface.destroy();
        assert.equal(h.events.length, before);
        h.failures.clear();
        await activate(runtime);
        runtime.deactivate();
    });
}

await test('cleanup failures do not replace the activation error', async () => {
    const h = harness(), runtime = new h.Runtime({});
    h.failures.add('manager.enable');
    h.failures.add('monitors.destroy');
    h.failures.add('stylesheet.unload');
    await assert.rejects(activate(runtime), /manager.enable/);
    assert.equal(h.Context.DTP_EXTENSION, null);
});

await test('cancelled timer cannot clear its replacement', async () => {
    const h = harness(), runtime = new h.Runtime({});
    h.Main.extensionManager._extensionOrder.push('ubuntu-dock@ubuntu.com');
    const old = activate(runtime);
    await Promise.resolve();
    const oldCallback = h.timers.get(runtime._surface._ubuntuDockDelayId);
    assert.equal(typeof oldCallback, 'function');
    h.failures.add('timer.remove');
    runtime.deactivate();
    await old;
    h.failures.clear();
    h.resetDisabled();
    const current = activate(runtime);
    await Promise.resolve();
    const id = runtime._surface._ubuntuDockDelayId;
    oldCallback();
    assert.equal(runtime._surface._ubuntuDockDelayId, id);
    h.timers.get(id)();
    await current;
    assert.equal(runtime._active, true);
    runtime.deactivate();
});

await test('active profile update keeps its surface', async () => {
    const h = harness(), runtime = new h.Runtime({});
    await activate(runtime);
    const manager = runtime._surface._manager;
    h.events.length = 0;
    await runtime.activate({layout: 'Classic'}, 'hybrid', 'lift', 65, 'intelligent', 38);
    assert.equal(runtime._surface._manager, manager);
    assert.equal(h.events.includes('manager.disable'), false);
    assert.equal(h.events.includes('stylesheet.load'), false);
    assert.ok(h.events.includes('size'));
    runtime.deactivate();
});
for (const reject of [false, true]) {
    await test(`settings release waits for pending initialization: reject=${reject}`, async () => {
        const h = harness(), runtime = new h.Runtime({});
        const pending = h.PanelSettings.pending = deferred();
        const activation = activate(runtime);
        await Promise.resolve();
        runtime.destroy();
        assert.ok(!h.events.includes('settings.dispose'));
        if (reject) pending.reject(new Error('late rejection'));
        else pending.resolve();
        await activation.catch(() => {});
        assert.ok(!h.events.includes('settings.dispose'));
        assert.equal(runtime._settings, null);
        runtime.destroy();
        assert.equal(h.events.filter(e => e === 'settings.dispose').length, 0);
        await assert.rejects(activate(runtime), /destroyed/);
    });
}
await test('settings remain live across ordinary deactivate/reactivate', async () => {
    const h = harness(), runtime = new h.Runtime({});
    const settings = runtime._settings;
    for (let i = 0; i < 20; i++) {
        await activate(runtime); runtime.deactivate();
        assert.equal(runtime._settings, settings);
    }
    assert.ok(!h.events.includes('settings.dispose'));
    runtime.destroy();
    assert.ok(!h.events.includes('settings.dispose'));
    assert.equal(runtime._settings, null);
});
for (const reverse of [false, true]) {
    await test(`destroy waits for both retired activations: reverse=${reverse}`, async () => {
        const h = harness(), runtime = new h.Runtime({});
        const first = h.PanelSettings.pending = deferred();
        const firstWork = activate(runtime);
        runtime.deactivate();
        const second = h.PanelSettings.pending = deferred();
        const secondWork = activate(runtime);
        runtime.destroy();
        const ordered = reverse ? [[second, secondWork], [first, firstWork]]
            : [[first, firstWork], [second, secondWork]];
        ordered[0][0].resolve(); await ordered[0][1];
        assert.ok(!h.events.includes('settings.dispose'));
        ordered[1][0].resolve(); await ordered[1][1];
        assert.equal(h.events.filter(event => event === 'settings.dispose').length, 0);
        assert.equal(runtime._settings, null);
        assert.equal(h.Context.DTP_EXTENSION, null);
    });
}
console.log(`${checks} taskbar lifecycle scenarios passed`);
