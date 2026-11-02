import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL(
    '../usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/redrawGuard.js',
    import.meta.url), 'utf8').replace(/^import .*;$/gm, '').replace(/^export /gm, '');

// Pixel-set regions are enough for the small rectangles used here.
class Rectangle {
    constructor({x, y, width, height}) { Object.assign(this, {x, y, width, height}); }
}
class Region {
    constructor() { this.pixels = new Set(); }
    static create() { return new Region(); }
    static create_rectangle(rect) { const r = new Region(); r.union_rectangle(rect); return r; }
    union_rectangle(rect) {
        for (let x = rect.x; x < rect.x + rect.width; x++)
            for (let y = rect.y; y < rect.y + rect.height; y++) this.pixels.add(`${x},${y}`);
    }
    subtract(other) { for (const p of other.pixels) this.pixels.delete(p); }
    is_empty() { return this.pixels.size === 0; }
}

function load(monitors) {
    class Effect { _init() {} vfunc_set_actor(actor) { this.actor = actor; } get_actor() { return this.actor; } }
    const context = {
        Clutter: {Effect, ActorNode: class { constructor(actor) { this.actor = actor; } }},
        GObject: {registerClass: (_meta, klass) => class extends klass {
            constructor(...args) { super(); this._init(...args); }
        }},
        Mtk: {Region, Rectangle},
        Main: {layoutManager: {monitors}},
    };
    return vm.runInNewContext(`${source}\n;createRedrawGuard`, context);
}

function actor(x, y, width, height) {
    return {
        mapped: true, redraws: 0,
        get_transformed_position: () => [x, y],
        get_transformed_size: () => [width, height],
        queue_redraw() { this.redraws++; },
    };
}

function attach(createRedrawGuard, target) {
    const guard = createRedrawGuard();
    guard.vfunc_set_actor(target);
    return guard;
}

function paint(guard, clip) {
    const node = {children: [], add_child(child) { this.children.push(child); }};
    guard.vfunc_paint_node(node, {get_redraw_clip: () => clip});
    assert.equal(node.children.length, 1, 'the actor itself is always painted');
}

const rect = (x, y, width, height) => Region.create_rectangle(new Rectangle({x, y, width, height}));
const monitors = [{x: 0, y: 0, width: 40, height: 30}];
const tests = [];
const test = (name, fn) => tests.push({name, fn});

test('a full redraw queues nothing', () => {
    const create = load(monitors), dock = actor(10, 20, 20, 6), guard = attach(create, dock);
    paint(guard, null);
    paint(guard, rect(0, 0, 40, 30));
    assert.equal(dock.redraws, 0);
});

test('a partial redraw queues the whole surface once', () => {
    const create = load(monitors), dock = actor(10, 20, 20, 6), guard = attach(create, dock);
    paint(guard, rect(12, 20, 4, 4));
    assert.equal(dock.redraws, 1);
    // The queued redraw covers the surface, so the next paint ends the cycle.
    paint(guard, rect(10, 20, 20, 6));
    assert.equal(dock.redraws, 1);
});

test('a clip that never covers the surface stops after three paints', () => {
    const create = load(monitors), dock = actor(10, 20, 20, 6), guard = attach(create, dock);
    for (let i = 0; i < 10; i++)
        paint(guard, rect(12, 20, 4, 4));
    assert.equal(dock.redraws, 3);
    paint(guard, null);
    paint(guard, rect(12, 20, 4, 4));
    assert.equal(dock.redraws, 4, 'a full paint rearms the guard');
});

test('the off-screen part of a surface does not need a redraw', () => {
    const create = load(monitors), dock = actor(30, 25, 20, 10), guard = attach(create, dock);
    paint(guard, rect(30, 25, 10, 5));
    assert.equal(dock.redraws, 0);
});

test('overlapping blurred surfaces are redrawn together', () => {
    const create = load(monitors);
    const panel = actor(0, 0, 40, 4), menu = actor(20, 3, 10, 10), dock = actor(10, 24, 20, 6);
    const guard = attach(create, menu);
    attach(create, panel); attach(create, dock);
    paint(guard, rect(22, 5, 2, 2));
    assert.deepEqual([panel.redraws, menu.redraws, dock.redraws], [1, 1, 0]);
});

test('a detached guard is forgotten', () => {
    const create = load(monitors);
    const panel = actor(0, 0, 40, 4), menu = actor(20, 3, 10, 10);
    const guard = attach(create, menu), panelGuard = attach(create, panel);
    panelGuard.vfunc_set_actor(null);
    paint(guard, rect(22, 5, 2, 2));
    assert.deepEqual([panel.redraws, menu.redraws], [0, 1]);
});

let failed = 0;
for (const {name, fn} of tests) {
    try {
        fn();
        console.log(`PASS ${name}`);
    } catch (error) {
        failed++;
        console.log(`FAIL ${name}: ${error.message}`);
    }
}
console.log(`${tests.length - failed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
