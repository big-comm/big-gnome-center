import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const file = new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/pointerWatcher.js', import.meta.url);
const source = fs.readFileSync(file, 'utf8');
const body = source.slice(0, source.indexOf('const legacy ='))
    .replace(/^import .*;\n/gm, '').replace('export class', 'class');
let changed;
let connects = 0;
let disconnects = 0;
let id = 0;
let position = [5, 8];
const timers = new Map();
const tracker = {
    connect(signal, callback) {
        assert.equal(signal, 'position-invalidated');
        connects++;
        changed = callback;
        return 12;
    },
    disconnect(signal) { assert.equal(signal, 12); disconnects++; },
};
const Watcher = vm.runInNewContext(body + '\nCursorWatcher;', {
    global: {backend: {get_cursor_tracker: () => tracker}, get_pointer: () => position},
    GLib: {
        PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
        timeout_add(_priority, interval, callback) {
            timers.set(++id, {interval, callback});
            return id;
        },
        source_remove(key) { timers.delete(key); },
    },
});
function flush() {
    for (const [key, timer] of [...timers]) {
        if (!timers.delete(key)) continue;
        assert.equal(timer.callback(), false);
    }
}
const watcher = new Watcher();
const calls = [];
const first = watcher.addWatch(50, (x, y) => calls.push([x, y]));
const second = watcher.addWatch(100, () => second.remove());
assert.equal(connects, 1, 'One native signal for multiple clients');
assert.equal(timers.size, 0, 'No polling while stationary');
changed(); changed(); changed();
assert.equal(timers.size, 2, 'Coalesce motion per consumer');
assert.deepEqual([...timers.values()].map(x => x.interval), [50, 100]);
position = [9, 10];
flush();
assert.deepEqual(calls, [[9, 10]], 'Read the latest pointer, not stale event coordinates');
assert.equal(disconnects, 0, 'Self-removal keeps other clients alive');
changed();
assert.equal(timers.size, 1);
first.remove(); first.remove();
assert.equal(timers.size, 0, 'Teardown cancels pending callbacks');
assert.equal(disconnects, 1);
watcher.addWatch(25, () => {}).remove();
assert.equal(connects, 2, 'Re-enable reconnects');
assert.equal(disconnects, 2);
assert.match(source, /Number\.parseInt\(Config\.PACKAGE_VERSION, 10\) < 51\s*\? await import/,
    'Only GNOME 50 imports the retired Shell module');
console.log('Native cursor notifications, coalescing, teardown and legacy gate passed');
