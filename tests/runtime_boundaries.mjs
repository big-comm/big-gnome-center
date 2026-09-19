import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = process.env.BGC_RUNTIME_DIRECTORY ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)),
    '../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
function load(file, exports, context = {}) {
    let source = read(file).replace(/^import .*\n/gm, '').replace(/^export /gm, '')
        .replace('await DBusMenuUtils.haveDBusMenu()', '__dbusMenu');
    const shared = file !== 'launcherEntry.js' && fs.existsSync(path.join(root, 'launcherEntry.js'))
        ? load('launcherEntry.js', 'parseLauncherUpdate, MAX_REMOTE_ENTRIES') : {};
    return vm.runInNewContext(`${source}\n;({${exports}})`, {console, __dbusMenu: null, ...shared, ...context}, {filename: file});
}
const cases = [];
const test = (group, name, run) => cases.push({group, name, run});
class Signals {
    constructor(...args) { this._init(...args); }
    _init() { this.handlers = new Map(); this.next = 0; }
    connect(signal, callback) { this.handlers.set(++this.next, {signal, callback}); return this.next; }
    disconnect(id) { this.handlers.delete(id); }
    emit(signal, ...args) {
        for (const [id, record] of [...this.handlers])
            if (record.signal === signal && this.handlers.has(id)) record.callback(this, ...args);
    }
}
function topology() {
    const replies = [];
    class Proxy {
        constructor(_bus, _name, _path, ready) { queueMicrotask(() => ready(this)); }
        GetCurrentStateRemote(callback) { replies.push(callback); }
    }
    const api = load('taskbar/panelSettings.js',
        'setMonitorsInfo, getPrimaryIndex, getPanelSize, get available(){return availableMonitors}',
        {Gio: {DBusProxy: {makeProxyWrapper: () => Proxy}, DBus: {}}, Pos: {}});
    const values = {'primary-monitor': 'vendor-one', 'panel-sizes': '{"vendor-one":42,"vendor-two":64}'};
    const settings = {get_string: key => values[key] ?? '', set_string: (key, value) => values[key] = value,
        get_int: () => 48};
    const request = async guard => { const promise = api.setMonitorsInfo(settings, guard); await Promise.resolve(); return {promise}; };
    const state = ids => [1, [], ids.map(([serial, connector], i) =>
        [i * 800, 0, 1, 0, i === 0, [[connector, 'vendor', 'product', serial]], {}]), {}];
    return {api, replies, request, state};
}
test('topology', 'removed monitor mappings disappear after complete replacement', async () => {
    const f = topology(); const a = await f.request();
    f.replies.shift()(f.state([['two', 'DP-2'], ['one', 'DP-1']])); await a.promise;
    const b = await f.request(); f.replies.shift()(f.state([['two', 'DP-2']])); await b.promise;
    assert.equal(f.api.getPrimaryIndex('vendor-one'), 0);
    assert.equal(f.api.getPrimaryIndex('vendor-two'), 0);
    assert.equal(f.api.available.length, 1);
});
test('topology', 'out-of-order responses cannot replace current topology', async () => {
    const f = topology(), a = await f.request(), b = await f.request();
    f.replies[1](f.state([['two', 'DP-2']])); await b.promise;
    f.replies[0](f.state([['one', 'DP-1']])); await a.promise;
    assert.equal(f.api.available[0].id, 'vendor-two');
});
test('topology', 'retired host cannot publish monitor state', async () => {
    const f = topology(); let current = true;
    const a = await f.request(() => current); current = false;
    f.replies[0](f.state([['one', 'DP-1']])); await a.promise;
    assert.equal(f.api.available.length, 0);
});
test('topology', 'invalid partial reply preserves complete previous state', async () => {
    const f = topology(), a = await f.request();
    f.replies.shift()(f.state([['one', 'DP-1']])); await a.promise;
    const old = f.api.available, b = await f.request();
    const reply = f.state([['two', 'DP-2']]); reply[2].push([]);
    const rejected = assert.rejects(b.promise);
    f.replies.shift()(reply); await rejected;
    assert.equal(f.api.available, old);
});
test('topology', 'empty topology clears mappings; duplicate serials remain unique', async () => {
    const f = topology(), a = await f.request();
    f.replies.shift()(f.state([['same', 'DP-1'], ['same', 'DP-2']])); await a.promise;
    assert.equal(new Set(f.api.available.map(m => m.id)).size, 2);
    const b = await f.request(); f.replies.shift()(f.state([])); await b.promise;
    assert.equal(f.api.getPrimaryIndex('vendor-same'), -1);
});
for (const invalid of ['duplicate-connector', 'scale', 'primary', 'identity', 'missing-array']) {
    test('topology', `${invalid} reply preserves previous topology`, async () => {
        const f = topology(), a = await f.request();
        f.replies.shift()(f.state([['one', 'DP-1']])); await a.promise;
        const previous = f.api.available, request = await f.request();
        const reply = f.state([['two', 'DP-2'], ['three', 'DP-3']]);
        if (invalid === 'duplicate-connector') reply[2][1][5][0][0] = 'DP-2';
        if (invalid === 'scale') reply[2][0][2] = NaN;
        if (invalid === 'primary') reply[2][1][4] = true;
        if (invalid === 'identity') reply[2][1][5] = [];
        if (invalid === 'missing-array') reply[2] = null;
        const rejected = assert.rejects(request.promise);
        f.replies.shift()(reply); await rejected;
        assert.equal(f.api.available, previous);
    });
}

function preview(extra = {}) {
    return load('taskbar/windowPreview.js', 'PreviewMenu, Preview, getTweenOpts, setStyle', {
        GObject: {registerClass: (_meta, cls) => cls}, St: {Widget: Signals},
        Clutter: {BinLayout: Signals}, ...extra,
    });
}
test('preview', 'workspace activation failure restores only the owned animation hook', () => {
    const original = () => true, replacement = () => 'new';
    const Main = {wm: {_shouldAnimate: original}};
    let replace = false;
    const workspace = {list_windows: () => [1], activate() {
        if (replace) Main.wm._shouldAnimate = replacement; throw Error('activation');
    }};
    const {PreviewMenu} = preview({Main, Utils: {getWorkspaceByIndex: () => workspace},
        global: {display: {get_current_time_roundtrip: () => 0}}});
    const menu = Object.create(PreviewMenu.prototype);
    assert.throws(() => menu._switchToWorkspaceImmediate(0));
    assert.equal(Main.wm._shouldAnimate, original);
    replace = true; assert.throws(() => menu._switchToWorkspaceImmediate(0));
    assert.equal(Main.wm._shouldAnimate, replacement);
});
test('preview', 'two preview owners retain independent scale, style and animation', () => {
    let scale = 1, manual = false, duration = 100;
    const {PreviewMenu, Preview, getTweenOpts, setStyle} = preview({
        Meta: {prefs_get_button_layout: () => ({left_buttons: []}), ButtonFunction: {CLOSE: 1}},
        SETTINGS: {get_boolean: key => key === 'window-preview-manual-styling' ? manual : true,
            get_string: () => 'TOP', get_int: key => key === 'window-preview-animation-time' ? duration : 100},
        Utils: {getScaleFactor: () => scale, mergeObjects: (opts, defaults) => ({...defaults, ...opts})},
    });
    const a = {_previewStyle: {aspectRatio: {}}, panel: {geom: {vertical: false}}};
    const b = {_previewStyle: {aspectRatio: {}}, panel: {geom: {vertical: false}}};
    PreviewMenu.prototype._refreshGlobals.call(a);
    scale = 2; manual = true; duration = 300;
    PreviewMenu.prototype._refreshGlobals.call(b);
    const dimensions = owner => Preview.prototype._getPreviewDimensions.call({
        _previewStyle: owner._previewStyle, _previewMenu: owner});
    assert.equal(dimensions(a)[0], 100); assert.equal(dimensions(b)[0], 200);
    assert.equal(getTweenOpts(a._previewStyle, {}).time, 0.1);
    assert.equal(getTweenOpts(b._previewStyle, {}).time, 0.3);
    let styles = 0;
    setStyle(a._previewStyle, {set_style: () => styles++}, 'a');
    setStyle(b._previewStyle, {set_style: () => styles++}, 'b');
    assert.equal(styles, 1);
});
for (const method of ['_mergeWindows', '_addAndRemoveWindows']) {
    test('preview', `${method} preserves caller window order`, () => {
        const {PreviewMenu} = preview({Taskbar: {sortWindowsCompareFunction: (a, b) => a - b},
            Utils: {findIndex: (items, predicate) => items.findIndex(predicate)}});
        const owner = {_box: {get_children: () => []}, _setShouldDisplayWorkspaces() {},
            _addNewPreview() {}, _updatePosition() {}, _updateScrollFade() {}};
        const windows = [3, 1, 2];
        if (method === '_mergeWindows') PreviewMenu.prototype[method].call(owner, {}, windows);
        else PreviewMenu.prototype[method].call(owner, windows);
        assert.deepEqual(windows, [3, 1, 2]);
    });
}
for (const fault of ['closed', 'zero', 'nan']) {
    test('preview', `${fault} window cannot produce invalid clone geometry`, () => {
        const {Preview} = preview();
        const window = {get_compositor_private: () => fault === 'closed' ? null : {},
            get_frame_rect: () => ({x: 0, y: 0, width: fault === 'zero' ? 0 : NaN, height: 100}),
            get_buffer_rect: () => ({x: 0, y: 0, width: 100, height: 100})};
        assert.equal(Preview.prototype._getWindowCloneBin.call({}, window), null);
    });
}

function notificationContext() {
    const tray = new Signals(); tray.sources = []; tray.getSources = () => tray.sources;
    const tracker = new Signals(), settings = new Signals();
    settings.get_boolean = () => true;
    const bus = {signal_subscribe: () => 1, signal_unsubscribe() {}, own_name: () => 1, unown_name() {}};
    const context = {EventEmitter: Signals, GObject: {Object: Signals, registerClass: (_meta, cls) => cls},
        Gio: {Settings: class { constructor() {return settings;} }, DBus: {session: bus},
            DBusSignalFlags: {}, BusNameOwnerFlags: {}},
        Shell: {WindowTracker: {get_default: () => tracker}}, Main: {messageTray: tray},
        MessageTray: {Urgency: {NORMAL: 1}, NotificationApplicationPolicy: class {}},
    };
    return {context, tray, tracker, settings};
}
test('notifications', 'retired dock callbacks cannot restore subscriptions', () => {
    const f = notificationContext();
    const {DockNotificationMonitor} = load('dockNotificationMonitor.js', 'DockNotificationMonitor', f.context);
    const monitor = new DockNotificationMonitor(f.settings);
    const callbacks = [...f.tray.handlers.values()].map(r => r.callback);
    monitor.destroy(); for (const callback of callbacks) callback();
    assert.equal(f.tray.handlers.size, 0);
    assert.equal(monitor.getAppNotificationsCount('a.desktop'), 0);
});
test('notifications', 'urgency and acknowledgment update taskbar without count changes', () => {
    const f = notificationContext();
    const {TaskbarNotificationMonitor} = load('taskbarNotificationMonitor.js', 'TaskbarNotificationMonitor', f.context);
    const source = new Signals(), notification = new Signals();
    Object.assign(source, {_appId: 'a.desktop', count: 1, notifications: [notification]});
    Object.assign(notification, {source, urgency: 1, acknowledged: false, resident: true});
    f.tray.sources.push(source);
    const monitor = new TaskbarNotificationMonitor();
    notification.urgency = 2; notification.emit('notify::urgency');
    assert.equal(monitor.getState({id: 'a.desktop'}).urgent, true);
    notification.acknowledged = true; notification.emit('notify::acknowledged');
    assert.equal(monitor.getState({id: 'a.desktop'})?.total ?? 0, 0);
    monitor.destroy();
});
test('launcher', 'untrusted taskbar properties cannot mutate internal tray state', () => {
    const f = notificationContext();
    const {TaskbarNotificationMonitor} = load('taskbarNotificationMonitor.js', 'TaskbarNotificationMonitor', f.context);
    const monitor = new TaskbarNotificationMonitor();
    monitor._handleLauncherUpdate(':1.25', {deep_unpack: () => ['application://a.desktop', {
        count: {unpack: () => 3}, 'count-visible': {unpack: () => true}, trayCount: {unpack: () => 900},
    }]});
    assert.equal(monitor.getState({id: 'a.desktop'}).total, 3);
    monitor.destroy();
});
test('launcher', 'untrusted dock properties cannot replace model methods', () => {
    const bus = {signal_subscribe: () => 1, signal_unsubscribe() {}, own_name: () => 1, unown_name() {}};
    const {LauncherEntryRemoteModel} = load('dock/launcherAPI.js', 'LauncherEntryRemoteModel', {
        Gio: {DBus: {session: bus}, DBusSignalFlags: {}, BusNameOwnerFlags: {}},
    });
    const model = new LauncherEntryRemoteModel();
    model._onUpdate(':1.25', 'application://a.desktop', {count: {unpack: () => 3}, connect: {unpack: () => false}});
    assert.equal(typeof model.lookupById('a.desktop').connect, 'function');
    model.destroy();
});
function launcherFixture(kind) {
    const f = notificationContext();
    if (kind === 'taskbar') {
        const {TaskbarNotificationMonitor} = load('taskbarNotificationMonitor.js', 'TaskbarNotificationMonitor', f.context);
        const model = new TaskbarNotificationMonitor();
        return {model, send: (sender, uri, props) => model._handleLauncherUpdate(sender, {deep_unpack: () => [uri, props]}),
            get: id => model.getState({id}), remove: sender => model._removeSender(sender)};
    }
    const {LauncherEntryRemoteModel} = load('dock/launcherAPI.js', 'LauncherEntryRemoteModel', f.context);
    const model = new LauncherEntryRemoteModel();
    return {model, send: (...args) => model._onUpdate(...args), get: id => model.lookupById(id),
        remove: sender => model._onDBusNameChange(sender, '')};
}
const variants = props => Object.fromEntries(Object.entries(props).map(([key, value]) => [key, {unpack: () => value}]));
test('launcher', 'quicklist replacement retires old client callbacks and sender loss releases client', () => {
    const clients = [];
    class Client extends Signals {
        constructor(props) { super(); Object.assign(this, props); this.root = {}; clients.push(this); }
        get_root() { assert.ok(!this.disposed); return this.root; }
        run_dispose() { this.disposed = true; }
    }
    const f = notificationContext();
    const {LauncherEntryRemoteModel} = load('dock/launcherAPI.js', 'LauncherEntryRemoteModel', {
        ...f.context, __dbusMenu: {Client, CLIENT_SIGNAL_ROOT_CHANGED: 'root-changed'},
    });
    const model = new LauncherEntryRemoteModel();
    model._onUpdate(':1.20', 'application://a.desktop', variants({quicklist: '/first'}));
    assert.equal(model.lookupById('a.desktop').quicklist, clients[0].root);
    const old = [...clients[0].handlers.values()][0].callback;
    model._onUpdate(':1.20', 'application://a.desktop', variants({quicklist: '/second'}));
    old(); assert.ok(clients[0].disposed);
    assert.equal(model.lookupById('a.desktop').quicklist, clients[1].root);
    const last = [...clients[1].handlers.values()][0].callback;
    model._onDBusNameChange(':1.20', ''); last();
    assert.ok(clients[1].disposed); assert.equal(model.lookupById('a.desktop').quicklist, null);
    model.destroy();
});
for (const kind of ['taskbar', 'dock']) {
    test('launcher', `${kind} rejects invalid values, IDs and senders`, () => {
        const f = launcherFixture(kind);
        f.send(':1.20', 'application://a.desktop', variants({count: 4, 'count-visible': true, progress: 0.5}));
        for (const value of [-1, NaN, Infinity, 2.5, '9', Number.MAX_SAFE_INTEGER + 1]) {
            f.send(':1.20', 'application://a.desktop', variants({count: value, progress: value}));
            assert.equal(f.get('a.desktop').count, 4);
        }
        for (const uri of ['file://a.desktop', 'application://../../a.desktop', 'application://', null])
            f.send(':1.20', uri, variants({count: 99}));
        for (const sender of ['', null, 'fake']) f.send(sender, 'application://a.desktop', variants({count: 99}));
        assert.equal(f.get('a.desktop').count, 4);
        f.model.destroy();
    });
    test('launcher', `${kind} publisher removal restores previous values and frees records`, () => {
        const f = launcherFixture(kind);
        f.send(':1.20', 'application://a.desktop', variants({count: 4, 'count-visible': true}));
        f.send(':1.21', 'application://a.desktop', variants({count: 7, 'count-visible': true}));
        assert.equal(f.get('a.desktop').count, 7);
        f.remove(':1.21'); assert.equal(f.get('a.desktop').count, 4);
        f.remove(':1.20'); assert.equal(f.get('a.desktop').count, 0);
        assert.equal(f.model._remoteMaps.size, 0); assert.equal(f.model._remoteCount, 0);
        f.model.destroy(); f.send(':1.21', 'application://a.desktop', variants({count: 1}));
        assert.equal(f.model._remoteMaps.size, 0);
    });
    test('launcher', `${kind} bounds external records and releases capacity on sender loss`, () => {
        const f = launcherFixture(kind);
        for (let i = 0; i < 600; i++) f.send(':1.20', `application://app${i}.desktop`, variants({count: i}));
        assert.equal(f.model._remoteCount, 512);
        f.remove(':1.20'); assert.equal(f.model._remoteCount, 0);
        if (kind === 'taskbar') assert.equal(Object.keys(f.model._state).length, 0);
        f.send(':1.21', 'application://new.desktop', variants({count: 3}));
        assert.equal(f.get('new.desktop').count, 3);
        f.model.destroy();
    });
}
for (const kind of ['taskbar', 'dock']) {
    test('notifications', `${kind} DND, resident acknowledgment reversal and retirement`, () => {
        const f = notificationContext(); let banners = true;
        f.settings.get_boolean = key => key === 'show-banners' ? banners : true;
        const source = new Signals(), notification = new Signals();
        Object.assign(source, {_appId: 'a.desktop', app: {id: 'a.desktop'}, count: 1, notifications: [notification]});
        Object.assign(notification, {source, urgency: 1, resident: true, acknowledged: false});
        f.tray.sources.push(source);
        const name = kind === 'dock' ? 'DockNotificationMonitor' : 'TaskbarNotificationMonitor';
        const file = kind === 'dock' ? 'dockNotificationMonitor.js' : 'taskbarNotificationMonitor.js';
        const api = load(file, name, f.context), model = new api[name](f.settings);
        const count = () => kind === 'dock' ? model.getAppNotificationsCount('a.desktop') : model.getState({id: 'a.desktop'}).total;
        assert.equal(count(), 1);
        notification.acknowledged = true; notification.emit('notify::acknowledged'); assert.equal(count(), 0);
        notification.acknowledged = false; notification.emit('notify::acknowledged'); assert.equal(count(), 1);
        banners = false; f.settings.emit('changed::show-banners'); assert.equal(count(), 0);
        banners = true; f.settings.emit('changed::show-banners'); assert.equal(count(), 1);
        const callbacks = [...source.handlers.values(), ...notification.handlers.values()].map(r => r.callback);
        model.destroy(); for (const callback of callbacks) callback();
        assert.equal(source.handlers.size, 0); assert.equal(notification.handlers.size, 0);
        assert.equal(count(), 0);
    });
}

let passed = 0;
for (const {group, name, run} of cases) {
    if (process.argv[2] && process.argv[2] !== group) continue;
    try { await run(); passed++; console.log(`PASS ${name}`); }
    catch (error) { process.exitCode = 1; console.error(`FAIL ${name}: ${error.stack}`); }
}
console.log(`${passed} boundary scenarios passed`);
