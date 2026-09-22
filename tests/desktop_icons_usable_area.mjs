import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)),
    '../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org');
let source = fs.readFileSync(path.join(root, 'desktopIconsUsableArea.js'), 'utf8')
    .replace(/^import .*\n/gm, '')
    .replace(/^export /gm, '');

function fixture() {
    let nextId = 0;
    const timers = new Map();
    const ding = {uuid: 'gtk4-ding@smedius.gitlab.com', state: 1, stateObj: {}};
    const manager = {
        connect() { return 1; },
        disconnect() {},
        getUuids() { return [ding.uuid]; },
        lookup() { return ding; },
    };
    const GLib = {
        PRIORITY_DEFAULT: 0,
        SOURCE_REMOVE: false,
        timeout_add(_priority, _delay, callback) {
            timers.set(++nextId, callback);
            return nextId;
        },
        Source: {remove: id => timers.delete(id)},
    };
    const {DesktopIconsUsableAreaClass} = vm.runInNewContext(
        `${source}\n;({DesktopIconsUsableAreaClass})`,
        {GLib, Main: {extensionManager: manager},
            ExtensionUtils: {ExtensionState: {ENABLED: 1, ACTIVE: 2}}},
        {filename: 'desktopIconsUsableArea.js'},
    );
    const runNext = () => {
        const entry = timers.entries().next();
        assert.equal(entry.done, false, 'expected a pending dispatch');
        const [id, callback] = entry.value;
        timers.delete(id);
        callback();
    };
    return {DesktopIconsUsableAreaClass, ding, timers, runNext};
}

{
    const f = fixture();
    const calls = [];
    const bridge = new f.DesktopIconsUsableAreaClass('runtime@test');
    bridge.setMargins(0, 10, 20, 30, 40);
    f.runNext();
    assert.equal(f.timers.size, 1, 'DING startup schedules a retry');
    f.ding.stateObj.DesktopIconsUsableArea = {
        uuid: '130cbc66-235c-4bd6-8571-98d2d8bba5e2',
        setMarginsForExtension: (...args) => calls.push(args),
    };
    f.runNext();
    assert.equal(f.timers.size, 0);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], 'runtime@test');
    assert.deepEqual(JSON.parse(JSON.stringify(calls[0][1])), {
        0: {top: 10, bottom: 20, left: 30, right: 40},
    });
    assert.deepEqual([...bridge.diagnostics().recipientUuids],
        ['gtk4-ding@smedius.gitlab.com']);
}

{
    const f = fixture();
    const bridge = new f.DesktopIconsUsableAreaClass('runtime@test');
    bridge.setMargins(0, 1, 2, 3, 4);
    let attempts = 0;
    while (f.timers.size && attempts < 25) {
        f.runNext();
        attempts++;
    }
    assert.equal(f.timers.size, 0, 'readiness retry is bounded');
    assert.equal(attempts, 21);
    assert.equal(bridge.diagnostics().dispatchCount, 21);
}

{
    const f = fixture();
    const bridge = new f.DesktopIconsUsableAreaClass('runtime@test');
    bridge.setMargins(0, 1, 2, 3, 4);
    bridge.destroy();
    assert.equal(f.timers.size, 1, 'destroy keeps one cleanup dispatch');
    f.runNext();
    assert.equal(f.timers.size, 0, 'destroy cannot restart readiness retries');
}

console.log('3 desktop usable-area scenarios passed');
