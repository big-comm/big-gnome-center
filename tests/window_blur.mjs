// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const base = new URL('../usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/', import.meta.url);
const source = fs.readFileSync(new URL('extension.js', base), 'utf8')
    .replace(/^import .*;\n/gm, '').replace('export default class', 'class');

for (const version of ['50.4', '51.beta']) {
    const writes = [];
    let parameters = [24, 1.25, 0.015];
    const compositor = {
        get_background_blur_params: () => parameters,
        set_background_blur_params: (...values) => writes.push(values),
    };
    const ExtensionClass = vm.runInNewContext(source + '\nFrostedGlassExtension;', {
        console, Config: {PACKAGE_VERSION: version}, Extension: class {},
        global: {compositor, get_window_actors() { assert.fail('Never modify client actors'); }},
    });
    const extension = new ExtensionClass();
    const settings = {enabled: true, windowsEnabled: false, mode: 'dynamic', radius: 55};
    extension._config = () => settings;
    extension._applyNativeParameters();
    assert.equal(writes.length, 0, 'Shell-only blur must not change native client blur');
    settings.windowsEnabled = true;
    extension._applyNativeParameters();
    if (version.startsWith('50')) {
        assert.equal(writes.length, 0, 'GNOME 50 must not use the native window API');
        continue;
    }
    assert.deepEqual(writes.at(-1), [55, 1.15, 0.008]);
    settings.mode = 'static';
    extension._applyNativeParameters();
    assert.deepEqual(writes.at(-1), [24, 1.25, 0.015]);
    const count = writes.length;
    extension._restoreNativeParameters();
    assert.equal(writes.length, count, 'Restore native parameters only once');
    settings.mode = 'dynamic';
    for (const invalid of [null, [24], [NaN, 1.25, 0.015], [24, '1.25', 0.015]]) {
        parameters = invalid;
        extension._applyNativeParameters();
        assert.equal(writes.length, count, 'Never mutate parameters that cannot be restored');
    }
    parameters = [24, 1.25, 0.015];
    for (const stop of ['windows', 'master', 'static', 'extension']) {
        Object.assign(settings, {enabled: true, windowsEnabled: true, mode: 'dynamic'});
        extension._applyNativeParameters();
        settings.radius = 80;
        extension._applyNativeParameters();
        if (stop === 'extension') {
            extension.disable();
        } else {
            if (stop === 'windows') settings.windowsEnabled = false;
            if (stop === 'master') settings.enabled = false;
            if (stop === 'static') settings.mode = 'static';
            extension._applyNativeParameters();
        }
        assert.deepEqual(writes.at(-1), [24, 1.25, 0.015], 'Restore the original native state');
        assert.equal(extension._nativeParametersChanged, false);
    }
    delete compositor.get_background_blur_params;
    const beforeMissingAPI = writes.length;
    extension._applyNativeParameters();
    assert.equal(writes.length, beforeMissingAPI, 'Missing getter must not mutate native state');
    delete compositor.set_background_blur_params;
    assert.doesNotThrow(() => extension._applyNativeParameters());
}
console.log('Native-only window blur, version gating and parameter restoration passed');

const queued = [];
const commands = [];
const stylesSource = fs.readFileSync(new URL('windowStyles.js', base), 'utf8')
    .replace(/^import .*;\n/gm, '').replace('export class', 'class');
const Styles = vm.runInNewContext(stylesSource + '\nWindowStyles;', {
    console,
    Gio: {SubprocessFlags: {STDERR_PIPE: 1}, Subprocess: {new(argv) {
        commands.push(Array.from(argv));
        return {
            communicate_utf8_async(_input, _cancel, done) { queued.push(() => done(this, {})); },
            communicate_utf8_finish() { return [true, '', '']; },
            get_successful() { return true; },
        };
    }}},
});
const styles = new Styles('/test/window_material.py');
styles.refresh(true, 37);
styles.refresh(true, 70);
styles.destroy();
assert.equal(commands.length, 1, 'Serialize helper processes');
queued.shift()();
assert.deepEqual(commands.at(-1), ['/usr/bin/python3', '/test/window_material.py']);
queued.shift()();
assert.equal(queued.length, 0, 'Disable must win over stale enables');
styles.refresh(true, 50);
styles.destroy();
styles.refresh(true, 80);
queued.shift()();
assert.deepEqual(commands.at(-1).slice(-3), ['--enable', '--opacity', '80']);
queued.shift()();
const beforeRepeat = commands.length;
styles.refresh(true, 80);
assert.equal(commands.length, beforeRepeat, 'Ignore unchanged requests');
console.log('Window style helper serialization and rapid re-enable passed');

const surfaceSource = fs.readFileSync(new URL('shellBlurSurface.js', base), 'utf8')
    .replace(/^import .*;\n/gm, '').replace('export class', 'class');
const Surface = vm.runInNewContext(surfaceSource + '\nShellBlurSurface;', {
    console, Main: {uiGroup: {}},
});
let panelStyle = 'background-color: rgba(0,0,0,0.7);';
const panelSignals = new Map();
let nextSignal = 0;
let styleWrites = 0;
const panel = {
    get_parent: () => null,
    connect(name, callback) { const id = ++nextSignal; panelSignals.set(id, [name, callback]); return id; },
    disconnect(id) { panelSignals.delete(id); },
    add_style_class_name() {}, remove_style_class_name() {},
    has_style_class_name: () => false,
    get_style: () => panelStyle,
    set_style(value) {
        assert.ok(++styleWrites < 20, 'Style repair must not recurse indefinitely');
        panelStyle = value;
        for (const [name, callback] of panelSignals.values())
            if (name === 'style-changed') callback();
    },
};
const surface = new Surface(panel, {kind: 'panel'});
assert.equal(styleWrites, 0, 'Unmapped targets stay untouched until material is applied');
surface._applyTargetStyle();
assert.match(panelStyle, /background-color: transparent/);
for (const opacity of ['0.80', '0.60', '0.90']) {
    panel.set_style(`background-color: rgba(0,0,0,${opacity});`);
    assert.match(panelStyle, /background-color: transparent/,
        'Overview opacity updates must not cover the blur');
}
surface.destroy();
assert.equal(panelStyle, 'background-color: rgba(0,0,0,0.90);',
    'Disabling restores the latest runtime style');
assert.equal(panelSignals.size, 0);
console.log('Panel overview style repair and current-style restoration passed');

// GNOME may dispose popup children and overlays before their controller.
const dyingSurface = new Surface(panel, {kind: 'panel'});
dyingSurface._applyTargetStyle();
const writesBeforeDestroy = styleWrites;
for (const [name, callback] of [...panelSignals.values()])
    if (name === 'destroy') callback();
assert.equal(styleWrites, writesBeforeDestroy, 'Do not restyle a destroying target');
assert.equal(dyingSurface.actor, null);
assert.equal(panelSignals.size, 0);
dyingSurface.destroy();

const childSignals = new Map();
let childDisposed = false;
const child = {
    connect(name, callback) { childSignals.set(1, callback); return 1; },
    disconnect(id) { assert.equal(childDisposed, false); childSignals.delete(id); },
    set visible(_value) { assert.fail('Do not restore a disposed popup border'); },
};
const popup = new Surface(panel, {kind: 'panel'});
popup._pointerBorder = child;
popup._pointerBorderVisible = true;
popup._watchLifetime(child);
childSignals.get(1)();
childDisposed = true;
popup.destroy();
assert.equal(popup._pointerBorder, null);
assert.equal(childSignals.size, 0);

let disposedOverlay = false;
let overlayDestroy;
const OverlaySurface = vm.runInNewContext(surfaceSource + '\nShellBlurSurface;', {
    console, Main: {uiGroup: {add_child() {}}},
    attachBlurRepaint() {}, createBackgroundEffect: () => ({}),
    St: {Widget: class {
        connect(_signal, callback) { overlayDestroy = callback; }
        add_effect_with_name() {} add_child() {}
        get_parent() { assert.equal(disposedOverlay, false); return null; }
        destroy() { assert.equal(disposedOverlay, false); }
    }},
});
const overlaySurface = new OverlaySurface(panel, {kind: 'panel'});
overlaySurface._rebuild('dynamic', null);
overlayDestroy();
disposedOverlay = true;
overlaySurface.destroy();
assert.equal(overlaySurface._overlay, null);
assert.equal(overlaySurface._effect, null);
console.log('Target, popup child and external overlay disposal passed');

for (const version of ['50.4', '51.beta']) {
    let wayland = true;
    const requests = [];
    const ExtensionClass = vm.runInNewContext(source + '\nFrostedGlassExtension;', {
        console, Config: {PACKAGE_VERSION: version}, Extension: class {},
        global: {compositor: {}, context: {get_wayland_compositor: () => wayland ? {} : null}},
    });
    const extension = new ExtensionClass();
    const config = {enabled: true, windowsEnabled: true, mode: 'dynamic', radius: 55, windowOpacity: 37};
    extension._config = () => config;
    extension._windowStyles = {refresh: (...args) => requests.push(args)};
    extension._syncWindowStyles();
    assert.equal(requests.at(-1)[0], version.startsWith('51'),
        'GNOME 51 native requests must not depend on the optional tuning API');
    wayland = false;
    extension._syncWindowStyles();
    assert.equal(requests.at(-1)[0], false, 'Do not enable on an X11 compositor');
    wayland = true;
    config.mode = 'static';
    extension._syncWindowStyles();
    assert.equal(requests.at(-1)[0], false);
    config.mode = 'dynamic';
    config.windowsEnabled = false;
    extension._syncWindowStyles();
    assert.equal(requests.at(-1)[0], false);
}
console.log('Native GTK styles without compositor tuning passed');

// Exercise enable and refresh without the removed Meta API.
for (const broken of [false, true]) {
    const calls = [];
    const queue = [];
    const ExtensionClass = vm.runInNewContext(source + '\nFrostedGlassExtension;', {
        console: {warn: message => calls.push('warning'), debug() {}, error() {}},
        Config: {PACKAGE_VERSION: '51.beta'}, Extension: class {},
        global: {settings: {}, context: {get_wayland_compositor: () => ({})}},
        Gio: {Settings: class {}, SettingsSchemaSource: {
            get_default: () => ({lookup: () => null}),
        }},
        GLib: {build_filenamev: parts => parts.join('/'), idle_add(_priority, callback) {
            queue.push(callback); return 1;
        }},
        WindowStyles: class {
            constructor() { if (broken) throw new Error('GTK unavailable'); }
            refresh() { calls.push('styles'); }
        },
        ConnectionManager: class {connect() {}},
        PowerMonitor: class {},
        OverviewController: class {enable() { calls.push('overview'); }},
    });
    const extension = new ExtensionClass();
    extension.path = '/usr/share/gnome-shell/extensions/frosted-glass@communitybig.org';
    extension.getSettings = () => ({});
    extension._config = () => ({enabled: true, windowsEnabled: true, mode: 'dynamic', radius: 55});
    extension._enableFullBackend = () => calls.push('backend');
    extension._applyNativeParameters = () => {};
    extension.enable();
    assert.ok(calls.includes('backend'), 'Always initialize panel/dock backend');
    assert.ok(calls.includes(broken ? 'warning' : 'styles'));
    extension._surfaces = {refresh() { calls.push('surfaces-refresh'); }};
    extension._overview = {refresh() { calls.push('overview-refresh'); }};
    extension._queueRefresh();
    queue.shift()();
    assert.ok(calls.includes('surfaces-refresh'), 'GTK failure must not block panel/dock refresh');
    assert.ok(calls.includes('overview-refresh'));
}
console.log('Extension enable and refresh isolate GTK failures from Shell surfaces');
