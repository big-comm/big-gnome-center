// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../usr/share/gnome-shell/extensions/' +
    'layout-switcher-helper@communitybig.org/extension.js', import.meta.url), 'utf8');
const constants = source.slice(source.indexOf('const NOTIFICATION_POSITION_DEFAULTS'),
    source.indexOf('// Build marker within'));
const methods = source.slice(source.indexOf('    _readAppSettings() {'),
    source.indexOf('    _isGUnityActive() {'));
const files = new Map();
const signals = new Map();
const bin = {
    x: 1, y: 0, xe: true, ye: true, translation_y: 0,
    get_x_align() { return this.x; }, get_y_align() { return this.y; },
    get_x_expand() { return this.xe; }, get_y_expand() { return this.ye; },
    set_x_align(value) { this.x = value; }, set_y_align(value) { this.y = value; },
    set_x_expand(value) { this.xe = value; }, set_y_expand(value) { this.ye = value; },
    connect(name, callback) { signals.set(name, callback); return name; },
    disconnect(id) { signals.delete(id); }, queue_relayout() {},
};
const context = {
    TextDecoder, Clutter: {ActorAlign: {START: 0, CENTER: 1, END: 2}},
    GLib: {get_user_config_dir: () => '/config', build_filenamev: parts => parts.join('/')},
    Gio: {File: {new_for_path: path => ({
        query_exists: () => files.has(path),
        load_contents: () => {
            if (!files.has(path)) throw Error('missing');
            return [true, Buffer.from(files.get(path))];
        },
    })}},
    Main: {messageTray: {_bannerBin: bin}, layoutManager: {primaryIndex: 0},
        extensionManager: {lookup: () => ({stateObj: {notificationBottomOffset: () => 40}})}},
    RUNTIME_UUID: 'runtime', logHelper() {},
};
const {Helper, defaults, aligns} = vm.runInNewContext(constants +
    `class Helper {${methods}}; ({Helper, defaults: NOTIFICATION_POSITION_DEFAULTS,
    aligns: NOTIFICATION_POSITION_ALIGNS})`, context);
const helper = new Helper();
helper._busy = () => false;
const current = '/config/big-gnome-center/settings.json';
const legacy = '/config/big-appearance/settings.json';
files.set(legacy, JSON.stringify({active_layout: 'Classic',
    notification_positions: {Classic: 'top-left', BigGnome: 'top-center'}}));

for (const [layout, defaultPosition] of defaults) {
    helper._activeLayoutLabel = layout;
    files.set(current, JSON.stringify({active_layout: layout}));
    assert.equal(helper._readActiveLayoutLabel(), layout, 'new layout wins over stale legacy data');
    helper._syncNotificationPosition();
    assert.equal(helper._notificationPosition, defaultPosition);
    for (const [position, [x, y]] of aligns) {
        assert.equal(JSON.parse(helper.SetNotificationPosition(position)).ok, true);
        // The app persists the choice before submitting its preview.
        files.set(current, JSON.stringify({active_layout: layout,
            notification_positions: {[layout]: position}}));
        for (let banner = 0; banner < 3; banner++) {
            signals.get('child-added')();
            assert.equal(helper._notificationPosition, position, `${layout}: ${position} persists`);
            assert.equal(bin.x, x);
            assert.equal(bin.y, y);
            assert.equal(bin.translation_y, position.startsWith('bottom-') ? -52 : 0);
        }
        helper._restoreNotificationPosition();
        assert.equal(signals.size, 0);
        assert.equal(bin.translation_y, 0);
        helper._syncNotificationPosition();
        assert.equal(helper._notificationPosition, position, 're-enable restores saved position');
    }
}
files.delete(current);
helper._activeLayoutLabel = 'Classic';
assert.equal(helper._readActiveLayoutLabel(), 'Classic');
assert.equal(helper._savedNotificationPosition(), 'top-left', 'legacy fallback before migration');
for (const contents of ['{}', 'null', '[]', 'invalid json']) {
    files.set(current, contents);
    assert.equal(Object.keys(helper._readAppSettings()).length, 0);
    assert.equal(helper._savedNotificationPosition(), 'bottom-right', 'never revive stale legacy data');
}
assert.equal(JSON.parse(helper.SetNotificationPosition('invalid')).ok, false);
helper._restoreNotificationPosition();
console.log('All six positions, six layouts, repeated banners, migration and restoration passed');
