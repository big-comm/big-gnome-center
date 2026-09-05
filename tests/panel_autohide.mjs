// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const path = new URL('../usr/share/gnome-shell/extensions/' +
    'layout-switcher-runtime@communitybig.org/panelAutohide.js', import.meta.url);
const source = fs.readFileSync(path, 'utf8').replace(/^import .*;\n/gm, '')
    .replace('export class PanelAutohide', 'class PanelAutohide');
const timers = new Map();
let nextId = 0;
let revealed = 0;
class Signals {
    callbacks = new Map();
    connect(name, callback) { this.callbacks.set(name, callback); return name; }
    disconnect(id) { this.callbacks.delete(id); }
    destroy() { this.destroyed = true; this.callbacks.clear(); }
}
class Pressure extends Signals {
    constructor(threshold, timeout) { super(); this.threshold = threshold; this.timeout = timeout; }
    addBarrier(barrier) { this.barrier = barrier; }
}
const context = {
    Clutter: {AnimationMode: {EASE_OUT_QUAD: 7}},
    GLib: {
        PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
        timeout_add(priority, delay, callback) {
            const id = ++nextId;
            timers.set(id, {delay, callback});
            return id;
        },
        Source: {remove(id) { timers.delete(id); }},
    },
    Meta: {
        BackendCapabilities: {BARRIERS: 1}, BarrierDirection: {POSITIVE_Y: 1},
        Barrier: class extends Signals { constructor(options) { super(); this.options = options; } },
    },
    Shell: {ActionMode: {NORMAL: 1}},
    Layout: {PressureBarrier: Pressure},
    Main: {layoutManager: {
        primaryMonitor: {x: 0, y: 0, width: 1280}, _queueUpdateRegions() {},
    }},
    global: {backend: {capabilities: 1}, get_pointer: () => [100, 0]},
};
const Autohide = vm.runInNewContext(source + '\nPanelAutohide;', context);
const actor = {
    visible: true, height: 32, translation_y: 0, transition: null, animations: [],
    show() { this.visible = true; },
    get_transition() { return this.transition; },
    remove_transition() { this.transition = null; },
    ease(options) { this.transition = options; this.animations.push(options); },
    finish() {
        const transition = this.transition;
        this.translation_y = transition.translation_y;
        this.transition = null;
        transition.onComplete();
    },
};
const zone = new Signals();
zone.hover = true;
const panel = new Autohide(actor, zone, () => revealed++);
panel.setEnabled(true);
const pressure = panel._pressure;
assert.equal(pressure.threshold, 100);
zone.callbacks.get('enter-event')();
assert.equal(revealed, 0, 'touching the edge must not bypass pressure');
pressure.callbacks.get('trigger')();
assert.equal(revealed, 1);

panel.setVisible(false);
assert.equal(actor.visible, true, 'hide only after the slide finishes');
assert.equal(actor.transition.duration, 200);
assert.equal(actor.transition.translation_y, -32);
panel.setVisible(false);
assert.equal(actor.animations.length, 1, 'repeated updates must not restart motion');
actor.finish();
assert.equal(actor.visible, false);
panel.setVisible(true);
assert.equal(actor.visible, true);
assert.equal(actor.translation_y, -32);
assert.equal(actor.transition.translation_y, 0);
panel.setVisible(false);
actor.finish();
assert.equal(actor.visible, false, 'reversing motion must retain the newest target');
panel.setVisible(true, true);
assert.equal(actor.visible, true);
assert.equal(actor.translation_y, 0);
assert.equal(zone.reactive, false, 'the reveal strip must not intercept panel clicks');
assert.equal(panel.pointerInside(), true, 'the top edge counts even without actor hover');
context.global.get_pointer = () => [100, 31];
assert.equal(panel.pointerInside(), true, 'panel margins count as interaction');
context.global.get_pointer = () => [100, 32];
assert.equal(panel.pointerInside(), false);
context.global.get_pointer = () => [1280, 0];
assert.equal(panel.pointerInside(), false, 'other monitors must not hold this panel');

for (const file of ['dockPanelController.js', 'nativePanelOpacityIntegration.js']) {
    const controllerSource = fs.readFileSync(new URL(file, path), 'utf8');
    const queueMethod = controllerSource.slice(controllerSource.indexOf('    _queueHide() {'),
        controllerSource.indexOf('    _cancelHide() {'));
    const Controller = vm.runInNewContext(`class Controller {${queueMethod}}; Controller`, {...context});
    const controller = new Controller();
    let inside = true;
    let menuOpen = false;
    let updates = 0;
    controller._panel = {hover: false};
    controller._pointerReveal = true;
    controller._autohide = {pointerInside: () => inside};
    controller._panelInteractionActive = () => menuOpen;
    controller._cancelHide = () => {};
    controller._applyVisibility = () => updates++;
    const tick = () => {
        const [id, timer] = [...timers.entries()][0];
        timers.delete(id);
        timer.callback();
    };
    controller._queueHide();
    tick();
    tick();
    assert.equal(updates, 0, `${file}: edge dwell must survive multiple hide timers`);
    inside = false;
    menuOpen = true;
    tick();
    assert.equal(updates, 0, `${file}: open popovers hold the panel`);
    menuOpen = false;
    tick();
    assert.equal(updates, 1);
    assert.equal(controller._pointerReveal, false);
    assert.equal(timers.size, 0);
}

const barrier = panel._barrier;
panel.setEnabled(false);
assert.equal(pressure.destroyed, true);
assert.equal(barrier.destroyed, true);
context.global.backend.capabilities = 0;
panel.setEnabled(true);
zone.callbacks.get('enter-event')();
assert.equal(revealed, 1);
assert.equal([...timers.values()][0].delay, 250);
zone.callbacks.get('leave-event')();
assert.equal(timers.size, 0, 'leaving early must cancel fallback reveal');
zone.callbacks.get('enter-event')();
const [timerId, timer] = [...timers.entries()][0];
timers.delete(timerId);
timer.callback();
assert.equal(revealed, 2);
panel.setVisible(false);
panel.destroy();
assert.equal(actor.transition, null);
assert.equal(actor.translation_y, 0, 'teardown must restore panel geometry');
assert.equal(zone.callbacks.size, 0);
assert.equal(timers.size, 0);
const visibilityPath = new URL('../usr/share/gnome-shell/extensions/' +
    'layout-switcher-runtime@communitybig.org/taskbarVisibilityModes.js', import.meta.url);
const visibilitySource = fs.readFileSync(visibilityPath, 'utf8')
    .replace(/^import .*;\n/gm, '')
    .replace('export class TaskbarVisibilityModes', 'class TaskbarVisibilityModes');
const Visibility = vm.runInNewContext(visibilitySource + '\nTaskbarVisibilityModes;', {});
const writes = [];
const settings = {
    set_int(key, value) { writes.push([key, value]); },
    set_boolean(key, value) { writes.push([key, value]); },
    set_string(key, value) { writes.push([key, value]); },
};
new Visibility(settings).apply('always-hidden');
assert.equal(writes.find(([key]) => key === 'intellihide-use-pressure')[1], true);
assert.equal(writes.find(([key]) => key === 'intellihide-pressure-threshold')[1], 100);
assert.equal(writes.at(-1)[0], 'intellihide', 'configure pressure before enabling autohide');
const intellihidePath = new URL('../usr/share/gnome-shell/extensions/' +
    'layout-switcher-runtime@communitybig.org/taskbar/intellihide.js', import.meta.url);
const intellihide = fs.readFileSync(intellihidePath, 'utf8');
assert.ok(intellihide.includes("import GLib from 'gi://GLib'"));
const pointerMethod = intellihide.slice(intellihide.indexOf('  _checkMousePointer(x, y) {'),
    intellihide.indexOf('  _pointerIn(x, y, fixedOffset, limitSizeSetting) {'));
let now = 1000000;
const Pointer = vm.runInNewContext('class Pointer {' + pointerMethod + '\n}; Pointer;', {
    GLib: {get_monotonic_time: () => now}, Main: {overview: {visible: false}}, SETTINGS: {},
});
const pointer = new Pointer();
let edge = true;
let requests = 0;
pointer._panelBox = {visible: false};
pointer._pointerIn = () => edge;
pointer._queueUpdatePanelPosition = () => requests++;
pointer._checkMousePointer(1, 1);
assert.equal(requests, 0);
now += 100000;
edge = false;
pointer._checkMousePointer(1, 1);
edge = true;
pointer._checkMousePointer(1, 1);
now += 200000;
pointer._checkMousePointer(1, 1);
assert.equal(requests, 0, 'leaving the edge resets taskbar dwell');
now += 100000;
pointer._checkMousePointer(1, 1);
assert.equal(requests, 1);
console.log('Panel animation, pressure, dwell, reversal, and teardown passed');
