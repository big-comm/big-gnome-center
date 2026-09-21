// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import vm from 'node:vm';

const root = process.env.BGC_RUNTIME_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_RUNTIME_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/', import.meta.url);
const source = fs.readFileSync(new URL('dockRuntime.js', root), 'utf8')
    .replace(/^import .*;$/gm, '').replaceAll('export ', '');
const args = [{layout: 'BigGnome'}, 'dot', 'default', 1, 70, 65, 48,
    'always-visible', 'left', false];
const setters = ['_applyProfile', '_applyIndicator', '_applyHover', '_applyOpacity',
    '_applyPanelOpacity', '_applyIconSize', 'visibility', '_applyMenuSide'];

function harness() {
    const events = [], failures = new Map(), hooks = new Map(), warnings = [];
    const step = name => {
        events.push(name);
        hooks.get(name)?.();
        if (failures.has(name)) throw failures.get(name);
    };
    const resource = name => class {
        constructor() { step(`${name}.new`); }
        destroy() { step(`${name}.destroy`); }
        releaseAll() { step(`${name}.release`); }
        apply() { step(name); }
    };
    class Manager {
        static current = null;
        static getDefault() { return this.current; }
        constructor(host) {
            step('manager.before');
            if (Manager.current) throw new Error('Manager already owned');
            Manager.current = this;
            this.extension = host;
            this._allDocks = [];
            step('manager.after');
        }
        destroy() {
            step('manager.destroy');
            assert.equal(Manager.current, this);
            Manager.current = null;
        }
    }
    const sandbox = {
        console: {warn: message => warnings.push(message)},
        DockSurfaceManager: Manager,
        ComponentHost: class {
            getSettings() { return {run_dispose() { step('settings.dispose'); }}; }
            loadStylesheet() { step('stylesheet.load'); }
            unloadStylesheet() { step('stylesheet.unload'); }
        },
    };
    for (const name of ['DockActorFactory', 'DockAppActions', 'DockAppMenuFactory',
        'DockAppMenuActions', 'DockAppModel', 'DockNotificationBadges', 'DockPlacement'])
        sandbox[name] = class {};
    Object.assign(sandbox, {
        DockNotificationMonitor: resource('notifications'),
        DockHoverEffects: resource('hover'),
        DockVisibilityModes: resource('visibility'),
        DockRunningIndicators: resource('indicators'),
        PanelController: resource('panel'),
    });
    const Runtime = vm.runInNewContext(`${source}\nDockRuntime`, sandbox);
    for (const name of setters.filter(name => name !== 'visibility'))
        Runtime.prototype[name] = () => step(name);
    const runtime = new Runtime({});
    events.length = 0;
    return {runtime, Runtime, Manager, events, failures, hooks, warnings};
}

let cases = 0;
function test(name, callback) {
    if (process.env.BGC_TEST_CASE && process.env.BGC_TEST_CASE !== name) return;
    try {
        callback();
        cases++;
    } catch (error) {
        error.message = `${name}: ${error.message}`;
        throw error;
    }
}
const assertReleased = runtime => {
    assert.equal(Boolean(runtime._active), false);
    for (const key of ['_manager', '_panelController', '_indicatorController', '_profile'])
        assert.equal(runtime[key] ?? null, null, key);
    for (const key of ['notificationsMonitor', 'runningIndicators', 'layout', 'menuSide', 'skipStartupOverview'])
        assert.equal(runtime._host[key], undefined, key);
};

test('foreign manager survives rejected activation', () => {
    const h = harness();
    const foreign = new h.Manager({});
    h.events.length = 0;
    assert.throws(() => h.runtime.activate(...args));
    h.runtime.deactivate();
    assert.equal(h.Manager.current, foreign);
    assert.deepEqual(h.events, [], 'Rejected acquisition must not alter shared styles or settings');
});

test('active updates reuse the manager', () => {
    const h = harness();
    h.runtime.activate(...args);
    const manager = h.Manager.current;
    h.events.length = 0;
    h.runtime.activate(...args);
    assert.equal(h.Manager.current, manager);
    assert.equal(h.runtime._managerGeneration, 1);
    assert.deepEqual(h.events, setters.slice(1));
    h.runtime.deactivate();
    assertReleased(h.runtime);
});

test('repeated deactivate is inert', () => {
    const h = harness();
    h.runtime.deactivate();
    assert.deepEqual(h.events, []);
    for (let i = 1; i <= 4; i++) {
        h.runtime.activate(...args);
        assert.equal(h.runtime._managerGeneration, i);
        h.runtime.deactivate();
        assertReleased(h.runtime);
        const count = h.events.length;
        h.runtime.deactivate();
        assert.equal(h.events.length, count);
    }
});

for (const point of [...setters, 'notifications.new', 'stylesheet.load',
    'manager.before', 'manager.after', 'indicators.new', 'panel.new']) {
    test(`activation failure at ${point}`, () => {
        const h = harness();
        const error = new Error(point);
        h.failures.set(point, error);
        assert.throws(() => h.runtime.activate(...args), value => value === error);
        assertReleased(h.runtime);
        assert.equal(h.Manager.current, null);
        h.failures.clear();
        h.runtime.activate(...args);
        assert.equal(h.runtime._active, true);
        h.runtime.deactivate();
        assertReleased(h.runtime);
    });
}

const cleanup = ['hover.release', 'panel.destroy', 'indicators.destroy',
    'manager.destroy', 'stylesheet.unload', 'notifications.destroy'];
for (const point of cleanup) {
    test(`cleanup failure at ${point}`, () => {
        const h = harness();
        h.runtime.activate(...args);
        const manager = h.Manager.current;
        h.events.length = 0;
        h.failures.set(point, new Error(point));
        h.runtime.deactivate();
        assertReleased(h.runtime);
        assert.deepEqual(h.events, cleanup);
        assert.equal(h.warnings.length, 1);
        h.failures.clear();
        if (point === 'manager.destroy') {
            // A manager failing before its own release is still owned externally.
            assert.equal(h.Manager.current, manager);
            assert.throws(() => h.runtime.activate(...args));
            manager.destroy();
        }
        h.runtime.activate(...args);
        h.runtime.deactivate();
    });
}

test('activation error survives multiple cleanup failures', () => {
    const h = harness();
    const error = new Error('panel construction');
    h.failures.set('panel.new', error);
    for (const point of cleanup.filter(name => name !== 'panel.destroy'))
        h.failures.set(point, new Error(point));
    assert.throws(() => h.runtime.activate(...args), value => value === error);
    assertReleased(h.runtime);
    assert.equal(h.warnings.length, 5);
});

for (const point of cleanup) {
    test(`reentrant cleanup at ${point}`, () => {
        const h = harness();
        h.runtime.activate(...args);
        h.events.length = 0;
        h.hooks.set(point, () => {
            h.runtime.deactivate();
            assert.throws(() => h.runtime.activate(...args), /already pending/);
            assert.equal(h.runtime._manager, null);
        });
        h.runtime.deactivate();
        assert.deepEqual(h.events, cleanup);
        assertReleased(h.runtime);
    });
}

for (const point of ['_applyProfile', 'manager.after', 'panel.new']) {
    test(`deactivate during construction at ${point}`, () => {
        const h = harness();
        h.hooks.set(point, () => {
            h.runtime.deactivate();
            assert.throws(() => h.runtime.activate(...args), /already pending/);
        });
        h.runtime.activate(...args);
        assertReleased(h.runtime);
        assert.equal(h.Manager.current, null);
        h.hooks.clear();
        h.runtime.activate(...args);
        assert.equal(h.runtime._active, true);
        h.runtime.deactivate();
    });
}

test('settings survive deactivation and release once after destruction', () => {
    const h = harness();
    const settings = h.runtime._settings;
    for (let i = 0; i < 20; i++) {
        h.runtime.activate(...args);
        h.runtime.deactivate();
        assert.equal(h.runtime._settings, settings);
    }
    assert.ok(!h.events.includes('settings.dispose'));
    h.runtime.destroy(); h.runtime.destroy();
    assert.equal(h.events.filter(e => e === 'settings.dispose').length, 1);
    assert.throws(() => h.runtime.activate(...args), /destroyed/);
});
for (const point of ['manager.after', 'panel.destroy']) {
    test(`settings disposal waits for ${point}`, () => {
        const h = harness();
        h.hooks.set(point, () => {
            h.runtime.destroy();
            assert.ok(!h.events.includes('settings.dispose'));
        });
        h.runtime.activate(...args);
        h.runtime.destroy();
        assert.equal(h.events.at(-1), 'settings.dispose');
        assert.equal(h.Manager.current, null);
    });
}
console.log(`${cases} dock lifecycle scenarios passed`);
