import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';

const root = process.env.BGC_FROSTED_DIRECTORY
    ? pathToFileURL(`${process.env.BGC_FROSTED_DIRECTORY}/`)
    : new URL('../usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/', import.meta.url);
function load(file, name, context) {
    const source = fs.readFileSync(new URL(file, root), 'utf8')
        .replace(/^import .*;$/gm, '').replace(/^export /gm, '');
    return vm.runInNewContext(`${source}\n;${name}`, {console: {warn() {}, debug() {}}, ...context});
}
function actors() {
    const all = [], managers = [], failures = new Set(), timers = new Map();
    let id = 0;
    function hit(name) { if (failures.has(name)) throw new Error(name); }
    class Actor {
        constructor(props = {}) {
            Object.assign(this, {visible: true, mapped: true, width: 80, height: 40,
                opacity: 255, parent: null, style: null}, props);
            this.children = []; this.signals = new Map(); this.classes = new Set(); this.effects = new Set();
            all.push(this);
        }
        connect(signal, callback) { this.signals.set(++id, {signal, callback}); return id; }
        disconnect(id) { hit(`disconnect:${this.name}`); this.signals.delete(id); }
        emit(signal) {
            for (const [id, record] of [...this.signals])
                if (record.signal === signal && this.signals.has(id)) record.callback(this);
        }
        get_parent() { return this.parent; }
        get_children() { return [...this.children]; }
        add_child(actor) { hit('add-child'); this.children.push(actor); actor.parent = this; }
        remove_child(actor) { hit('remove-child'); this.children = this.children.filter(a => a !== actor); actor.parent = null; }
        destroy() {
            hit(`destroy:${this.name}`);
            if (this.destroyed) return;
            this.destroyed = true; this.emit('destroy');
            for (const child of [...this.children]) child.destroy();
            this.parent?.remove_child(this); this.effects.clear(); this.signals.clear();
        }
        get_style() { return this.style; }
        set_style(value) { hit(`style:${this.name}`); this.style = value; this.emit('style-changed'); }
        has_style_class_name(name) { return this.classes.has(name); }
        add_style_class_name(name) { this.classes.add(name); }
        remove_style_class_name(name) { hit(`class:${this.name}`); this.classes.delete(name); }
        get_style_class_name() { return [...this.classes].join(' '); }
        hide() { this.visible = false; }
        get_transformed_position() { return [0, 0]; }
        get_transformed_size() { return [this.width, this.height]; }
        get_paint_opacity() { return this.opacity; }
        set_position() {} set_size() {} set_clip() {} remove_clip() {} set_child_below_sibling() {}
        add_effect_with_name(name, effect) { hit(`effect:${name}`); this.effects.add(effect); }
        add_effect(effect) { this.effects.add(effect); }
        remove_effect(effect) { this.effects.delete(effect); }
    }
    class Effect { queue_repaint() {} }
    const group = new Actor({name: 'group'});
    const monitor = {index: 0, x: 0, y: 0, width: 1280, height: 800};
    const Main = {uiGroup: group, layoutManager: {uiGroup: group, modalDialogGroup: new Actor(),
        primaryMonitor: monitor, monitors: [monitor], findMonitorForActor: () => monitor}};
    const context = {Main, global: {stage: {}}, Clutter: {},
        GLib: {PRIORITY_DEFAULT: 0, PRIORITY_DEFAULT_IDLE: 0, SOURCE_REMOVE: false, SOURCE_CONTINUE: true,
            idle_add(_p, cb) { timers.set(++id, cb); return id; },
            timeout_add_seconds(_p, _s, cb) { timers.set(++id, cb); return id; },
            source_remove(id) { hit('source-remove'); timers.delete(id); }},
        St: {Widget: Actor, Corner: {TOPLEFT: 0}, ThemeContext: {get_for_stage: () => ({scale_factor: 1})}},
        Shell: {BlurEffect: Effect, BlurMode: {ACTOR: 0}}, RoundedCornersEffect: Effect,
        createBackgroundEffect() { hit('effect-new'); return new Effect(); },
        attachBlurRepaint(actor, getEffect) { const e = {getEffect}; actor.add_effect(e); return e; },
        Background: {BackgroundManager: class {
            constructor() { managers.push(this); }
            destroy() { hit('manager-destroy'); this.destroyed = true; }
        }},
    };
    const Surface = load('shellBlurSurface.js', 'ShellBlurSurface', context);
    const Surfaces = load('shellSurfaces.js', 'ShellSurfaces', {...context, ShellBlurSurface: Surface});
    function surface(kind = 'dash-to-dock') {
        const pointer = new Actor({name: 'pointer', style: 'pointer-original;'});
        pointer.classes.add('popup-menu-boxpointer');
        pointer._border = new Actor({name: 'border'});
        group.add_child(pointer); pointer.add_child(pointer._border);
        const actor = new Actor({name: 'target', style: 'target-original;'});
        pointer.add_child(actor);
        actor.panel = new Actor({name: 'content', style: 'content-original;'});
        actor.add_child(actor.panel);
        const s = new Surface(actor, {kind, cornerRadius: 12});
        return {s, actor, pointer, border: pointer._border, content: actor.panel};
    }
    const config = {enabled: true, mode: 'dynamic', radius: 30, brightness: 0.9, tintOpacity: 0.1, lightMode: false};
    return {Actor, Surface, Surfaces, surface, config, all, managers, failures, timers, group, Main};
}

const cases = [];
const test = (group, name, run) => cases.push({group, name, run});
for (const kind of ['panel', 'dash-to-panel', 'dash-to-dock', 'quick-settings', 'date-menu']) {
    test('styles', `untouched ${kind} styles survive destroy before first update`, () => {
        const h = actors(), f = h.surface(kind);
        f.s.destroy();
        assert.equal(f.actor.style, 'target-original;');
        assert.equal(f.content.style, 'content-original;');
        assert.equal(f.pointer.style, 'pointer-original;');
    });
}
test('styles', 'external target, pointer and border changes survive disable', () => {
    const h = actors(), f = h.surface('quick-settings');
    f.s.update(h.config);
    f.actor.style = 'external-target;'; f.pointer.style = 'external-pointer;'; f.border.visible = true;
    f.s.destroy();
    assert.equal(f.actor.style, 'external-target;'); assert.equal(f.pointer.style, 'external-pointer;');
    assert.equal(f.border.visible, true);
});
test('styles', 'one failed style restore does not stop independent actors', () => {
    const h = actors(), f = h.surface('quick-settings'); f.s.update(h.config);
    h.failures.add('style:target'); f.s.destroy();
    assert.equal(f.pointer.style, 'pointer-original;'); assert.equal(f.border.visible, true);
    assert(!h.group.children.some(a => a.name?.startsWith('frosted-glass-')));
});
test('styles', 'external panel styles become the restoration baseline', () => {
    const h = actors(), f = h.surface('dash-to-panel'); f.s.update(h.config);
    f.actor.set_style('external-panel;'); f.content.set_style('external-content;');
    f.s.destroy();
    assert.equal(f.actor.style, 'external-panel;'); assert.equal(f.content.style, 'external-content;');
});
test('styles', 'preexisting material classes survive destroy', () => {
    const h = actors(), f = h.surface();
    f.actor.classes.add('frosted-glass-shell-surface'); f.actor.classes.add('frosted-glass-light');
    f.s.update({...h.config, lightMode: true}); f.s.destroy();
    assert(f.actor.classes.has('frosted-glass-shell-surface')); assert(f.actor.classes.has('frosted-glass-light'));
});
test('styles', 'target destruction still restores surviving pointer', () => {
    const h = actors(), f = h.surface('quick-settings'); f.s.update(h.config); f.actor.destroy();
    assert.equal(f.pointer.style, 'pointer-original;'); assert.equal(f.border.visible, true);
});

test('resources', 'constructor failure disconnects already acquired signals', () => {
    const h = actors(), actor = new h.Actor({name: 'partial'});
    actor.get_parent = () => { throw new Error('parent'); };
    assert.throws(() => new h.Surface(actor, {kind: 'panel'}));
    assert.equal(actor.signals.size, 0);
});
test('resources', 'failed overlay construction releases all partial resources', () => {
    const h = actors(), f = h.surface(); h.failures.add('effect-new');
    assert.throws(() => f.s.update(h.config));
    assert(!f.s._overlay); assert(!h.group.children.some(a => a.name?.startsWith('frosted-glass-')));
    h.failures.clear(); f.s.update(h.config); assert(f.s._effect); f.s.destroy();
});
for (const mode of ['static', 'dynamic']) {
    test('resources', `failed ${mode} effect attachment destroys orphan widgets`, () => {
        const h = actors(), f = h.surface(), before = h.all.length;
        h.failures.add('effect:communitybig-frosted-glass-shell');
        assert.throws(() => f.s.update({...h.config, mode}));
        assert(h.all.slice(before).every(actor => actor.destroyed));
        assert(!f.s._overlay && !f.s._wallpaper); f.s.destroy();
    });
}
test('resources', 'failure after wallpaper creation releases its manager', () => {
    const h = actors(), f = h.surface(), before = h.all.length;
    f.s._ensureStacking = () => { throw new Error('stack'); };
    assert.throws(() => f.s.update({...h.config, mode: 'static'}));
    assert(h.managers.every(manager => manager.destroyed));
    assert(h.all.slice(before).every(actor => actor.destroyed)); f.s.destroy();
});
test('resources', 'retired overlay callback cannot clear a replacement', () => {
    const h = actors(), f = h.surface(); f.s.update(h.config);
    const previous = f.s._overlay;
    const callback = [...previous.signals.values()].find(r => r.signal === 'destroy').callback;
    f.s.update({...h.config, mode: 'static'});
    const current = f.s._overlay, effect = f.s._effect;
    callback(previous);
    assert.equal(f.s._overlay, current); assert.equal(f.s._effect, effect); f.s.destroy();
});
test('resources', 'external overlay destruction retires wallpaper manager', () => {
    const h = actors(), f = h.surface(); f.s.update({...h.config, mode: 'static'});
    const manager = f.s._manager; f.s._overlay.destroy();
    assert(manager.destroyed); assert(!f.s._manager); f.s.destroy();
});
test('resources', 'failed parent detach still destroys overlay', () => {
    const h = actors(), f = h.surface(); f.s.update(h.config);
    const overlay = f.s._overlay; h.failures.add('remove-child'); f.s.destroy();
    assert(overlay.destroyed);
});
test('resources', 'retired paint callback does not repaint replacement effect', () => {
    const h = actors(), f = h.surface(); f.s.update(h.config);
    const paint = f.s._paintSignal; f.s.update({...h.config, mode: 'static'});
    assert.equal(paint.getEffect(), null); f.s.destroy();
});
test('resources', 'mode changed while hidden is applied when mapped again', () => {
    const h = actors(), f = h.surface(); f.s.update(h.config);
    f.actor.mapped = false; f.s.update({...h.config, mode: 'static'});
    f.actor.mapped = true; f.actor.emit('notify::mapped');
    assert.equal(f.s._mode, 'static'); assert(f.s._manager); f.s.destroy();
});
test('resources', 'destroy releases all records after one cleanup failure', () => {
    const h = actors(), surfaces = new h.Surfaces(() => h.config);
    let retired = false;
    surfaces._records.set({}, {destroy() { throw new Error('first'); }});
    surfaces._records.set({}, {destroy() { retired = true; }});
    surfaces.destroy(); assert(retired); assert.equal(surfaces._records.size, 0);
});
test('resources', 'failed target setup does not prevent other surfaces', () => {
    const h = actors(), f = h.surface(), good = new h.Actor({name: 'good'});
    h.group.add_child(good); const surfaces = new h.Surfaces(() => h.config);
    surfaces._discover = () => new Map([[f.actor, 'panel'], [good, 'panel']]);
    const parent = f.actor.get_parent;
    let calls = 0;
    f.actor.get_parent = () => { if (++calls > 1) throw new Error('bad parent'); return parent.call(f.actor); };
    surfaces.refresh(); assert(surfaces._records.has(good)); assert(!surfaces._records.has(f.actor));
    surfaces.destroy(); f.s.destroy();
});
test('resources', 'retired scan and refresh callbacks cannot recreate surfaces', () => {
    const h = actors(), surfaces = new h.Surfaces(() => h.config);
    let discoveries = 0;
    surfaces._discover = () => { discoveries++; return new Map(); };
    surfaces.enable(); surfaces._queueRefresh();
    const callbacks = [...h.timers.values()]; surfaces.destroy();
    const before = discoveries;
    callbacks.forEach(cb => cb()); surfaces.refresh(); surfaces._queueRefresh();
    assert.equal(discoveries, before); assert.equal(h.timers.size, 0);
});
test('resources', 'failed timer removal leaves retired callbacks inert', () => {
    const h = actors(), surfaces = new h.Surfaces(() => h.config);
    surfaces._discover = () => new Map(); surfaces.enable(); surfaces._queueRefresh();
    const callbacks = [...h.timers.values()]; h.failures.add('source-remove');
    surfaces.destroy();
    assert(callbacks.every(callback => callback() === false));
    assert.equal(surfaces._scanId, 0); assert.equal(surfaces._refreshId, 0);
});
test('styles', 'quick submenu classes retain external and preexisting styles', () => {
    const h = actors(), surfaces = new h.Surfaces(() => h.config), a = new h.Actor();
    a.classes.add('frosted-glass-quick-submenu'); a.classes.add('frosted-glass-light');
    surfaces._syncQuickSubmenus(new Set([a]), false);
    surfaces._syncQuickSubmenus(new Set(), false);
    assert(a.classes.has('frosted-glass-quick-submenu')); assert(a.classes.has('frosted-glass-light'));
    const b = new h.Actor(); surfaces._syncQuickSubmenus(new Set([b]), true);
    b.classes.delete('frosted-glass-light'); surfaces.destroy();
    assert(!b.classes.has('frosted-glass-light')); assert(!b.classes.has('frosted-glass-quick-submenu'));
});

function writer() {
    const processes = [];
    let spawnFailure = false, registrationFailure = false, waitFailure = false;
    const Styles = load('windowStyles.js', 'WindowStyles', {Gio: {
        SubprocessFlags: {STDERR_PIPE: 1}, Subprocess: {new(argv) {
            if (spawnFailure) throw new Error('spawn');
            const process = {argv, successful: true, stderr: '',
                communicate_utf8_async(_a, _b, callback) {
                    this.callback = callback;
                    if (registrationFailure) throw new Error('registration');
                },
                communicate_utf8_finish() { if (this.error) throw new Error('communication'); return [true, '', this.stderr]; },
                get_successful() { return this.successful; },
                force_exit() { this.stopped = true; this.successful = false; },
                wait_async(_cancel, callback) {
                    if (waitFailure) throw new Error('wait registration');
                    this.waitCallback = callback;
                },
                wait_finish() { if (this.waitError) throw new Error('wait'); },
                finishWait() { this.waitCallback(this, {}); },
                finish() { this.callback(this, {}); }};
            processes.push(process); return process;
        }},
    }});
    return {styles: new Styles('/test/helper.py'), processes, failSpawn: value => spawnFailure = value,
        failRegistration: value => registrationFailure = value, failWait: value => waitFailure = value};
}
for (const failure of ['exit', 'communication', 'spawn']) {
    test('writer', `${failure} failure retries only on a new request`, () => {
        const h = writer(), w = h.styles;
        if (failure === 'spawn') h.failSpawn(true);
        w.refresh(true, 40);
        if (failure !== 'spawn') {
            h.processes[0].successful = false;
            h.processes[0].error = failure === 'communication';
            h.processes[0].finish();
            if (failure === 'communication') h.processes[0].finishWait();
        }
        assert.equal(w._applied, null);
        assert.equal(h.processes.length, failure === 'spawn' ? 0 : 1, 'unbounded retry');
        h.failSpawn(false); w.refresh(true, 40);
        assert.equal(h.processes.length, failure === 'spawn' ? 1 : 2);
        h.processes.at(-1).finish();
        assert.equal(w._applied, JSON.stringify([true, 40]));
        w.refresh(true, 40); assert.equal(h.processes.length, failure === 'spawn' ? 1 : 2);
    });
}
test('writer', 'failed partial request invalidates previous success', () => {
    const h = writer(), w = h.styles;
    w.refresh(false); h.processes[0].finish();
    w.refresh(true); h.processes[1].successful = false; h.processes[1].finish();
    assert.equal(w._applied, null);
    w.destroy(); assert.equal(h.processes.length, 3); h.processes[2].finish();
});
test('writer', 'communication failure holds final disable until confirmed exit', () => {
    const h = writer(), w = h.styles;
    w.refresh(true); h.processes[0].error = true; h.processes[0].finish();
    w.destroy(); assert(w._busy); assert.equal(h.processes.length, 1);
    h.processes[0].finishWait(); assert.equal(h.processes.length, 2);
    assert(!h.processes[1].argv.includes('--enable'));
    h.processes[1].finish(); assert.equal(w._applied, JSON.stringify([false, 37]));
});
test('writer', 'final disable stays serialized behind failed enable', () => {
    const h = writer(), w = h.styles;
    w.refresh(true, 40); w.refresh(true, 65); w.destroy();
    assert.equal(h.processes.length, 1);
    h.processes[0].successful = false; h.processes[0].finish();
    assert.equal(h.processes.length, 2); assert(!h.processes[1].argv.includes('--enable'));
    h.processes[1].finish(); assert.equal(w._applied, JSON.stringify([false, 37]));
});
test('writer', 'latest explicit refresh during a failed request retries once', () => {
    const h = writer(), w = h.styles;
    w.refresh(true); for (let i = 0; i < 20; i++) w.refresh(true);
    h.processes[0].successful = false; h.processes[0].finish();
    assert.equal(h.processes.length, 2);
    h.processes[1].successful = false; h.processes[1].finish();
    assert.equal(h.processes.length, 2);
});
test('writer', 'spawned writer stays owned after communication registration fails', () => {
    const h = writer(), w = h.styles; h.failRegistration(true);
    w.refresh(true); assert(w._busy); assert(h.processes[0].stopped);
    h.failRegistration(false); w.destroy(); assert.equal(h.processes.length, 1);
    h.processes[0].finishWait(); assert.equal(h.processes.length, 2);
    h.processes[0].finish(); assert(w._busy, 'old completion released the new writer');
    h.processes[1].finish(); assert.equal(w._applied, JSON.stringify([false, 37]));
});
test('writer', 'failed exit observer is retried without starting concurrent writers', () => {
    const h = writer(), w = h.styles; h.failRegistration(true); h.failWait(true);
    w.refresh(true); assert(w._busy); assert(w._waitRetry);
    h.failRegistration(false); h.failWait(false); w.destroy();
    assert.equal(h.processes.length, 1); h.processes[0].finishWait();
    assert.equal(h.processes.length, 2); h.processes[1].finish();
});
test('writer', 'stderr warning on successful exit does not force a retry', () => {
    const h = writer(), w = h.styles; w.refresh(true);
    h.processes[0].stderr = 'diagnostic'; h.processes[0].finish(); w.refresh(true);
    assert.equal(h.processes.length, 1); assert.equal(w._applied, JSON.stringify([true, 37]));
});
let passed = 0, failed = 0;
for (const item of cases) {
    if (process.argv[2] && item.group !== process.argv[2]) continue;
    try { item.run(); passed++; console.log(`PASS ${item.name}`); }
    catch (error) { failed++; console.error(`FAIL ${item.name}: ${error.stack}`); }
}
console.log(`${passed} passed, ${failed} failed`);
if (failed) process.exitCode = 1;
