import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = process.env.BGC_MENU_DIRECTORY ?? path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    '../usr/share/gnome-shell/extensions/community-menu@communitybig.org');
const source = file => fs.readFileSync(path.join(root, file), 'utf8');
const pending = () => {
    let resolve, reject;
    const promise = new Promise((a, b) => { resolve = a; reject = b; });
    return {promise, resolve, reject};
};
class Actor {
    constructor(...args) { this._init(...args); }
    _init(props = {}) { Object.assign(this, props); this.handlers = {}; this.children = []; }
    connect(name, callback) { (this.handlers[name] ??= []).push(callback); }
    emit(name) { for (const callback of this.handlers[name] ?? []) callback(this); }
    add_child(child) { this.children.push(child); }
    hide() { assert.ok(!this.dead); this.visible = false; }
    show() { assert.ok(!this.dead); this.visible = true; }
    destroy() { assert.ok(!this.dead, 'double destroy'); this.dead = true; this.isDestroyed = true; this.emit('destroy'); }
    activate() { assert.ok(!this.dead, 'activation after destruction'); }
}
class Cancellable {
    cancel() { this.cancelled = true; }
    is_cancelled() { return !!this.cancelled; }
}
const defaults = {
    console: {warn() {}}, logError() {}, _: s => s, ngettext: s => s,
    Gio: {Cancellable}, GObject: {registerClass: (_meta, cls) => cls},
    St: {BoxLayout: Actor, Bin: Actor},
    BaseMenuItem: {BaseMenuItem: Actor}, AppMenuItem: {AppMenuItem: Actor},
    getOrientationProp: () => ({}),
};
function load(file, names, extra = {}) {
    const text = source(file).replace(/^import .*\n/gm, '').replace(/^export /gm, '');
    return vm.runInNewContext(`${text}\n;({${names}})`, {...defaults, ...extra}, {filename: file});
}
const tests = [];
function test(group, name, run) { tests.push({group, name, run}); }

function backendFixture() {
    const apps = new Map();
    const app = (id, visible = true, allowed = true) => {
        const info = {get_id: () => id, should_show: () => visible, allowed};
        const value = {get_id: () => id, get_name: () => id, get_app_info: () => info, app_info: info};
        apps.set(id, value);
        return value;
    };
    const state = {fail: false, ids: ['listed.desktop'], trees: []};
    const iter = ids => {
        let i = -1;
        return {next: () => ++i < ids.length ? 1 : 0,
            get_entry: () => ({get_desktop_file_id: () => ids[i]})};
    };
    class Tree {
        constructor() { state.trees.push(this); }
        load_sync() { if (state.fail === 'load') throw Error('load'); }
        get_root_directory() {
            let count = 0;
            return {iter: () => ({next: () => count++ === 0 ? 2 : 0,
                get_directory: () => ({get_is_nodisplay: () => false, get_menu_id: () => 'test',
                    iter: () => { if (state.fail === 'iterate') throw Error('iterate'); return iter(state.ids); }})})};
        }
        connectObject() { this.connected = true; }
        disconnectObject() { this.connected = false; }
    }
    class Emitter { emit() { this.reloads = (this.reloads ?? 0) + 1; } }
    const {AppsBackend} = load('appsbackend.js', 'AppsBackend', {
        EventEmitter: Emitter, GMenu: {Tree, TreeFlags: {}, TreeItemType: {INVALID: 0, ENTRY: 1, DIRECTORY: 2}},
        Shell: {AppSystem: {get_default: () => ({get_installed: () => [...apps.values()].map(app => app.app_info),
            lookup_app: id => apps.get(id), connectObject() {}, disconnectObject() {}})}},
        ParentalControlsManager: {getDefault: () => ({shouldShowApp: info => info.allowed,
            connectObject() {}, disconnectObject() {}})},
    });
    app('listed.desktop');
    return {state, app, apps, AppsBackend};
}
test('catalog', 'uncategorized apps, deduplication, visibility and parental filters', () => {
    const {AppsBackend, app} = backendFixture();
    app('extra.desktop'); app('hidden.desktop', false); app('blocked.desktop', true, false);
    const backend = new AppsBackend();
    assert.deepEqual(Array.from(backend.getAllApps(), app => app.get_id()), ['extra.desktop', 'listed.desktop']);
    assert.equal(backend.getAppsByCategory('missing').length, 0);
    backend.destroy();
});
for (const failure of ['load', 'iterate']) {
    test('catalog', `${failure} failure retains catalog and next reload succeeds`, () => {
        const {AppsBackend, state, app} = backendFixture();
        const backend = new AppsBackend();
        const oldTree = state.trees[0], oldCategories = backend._categories;
        const oldApps = backend._appsByCategory, reloads = backend.reloads;
        state.fail = failure;
        backend._reload();
        assert.equal(backend.reloading, false);
        assert.equal(backend.reloads, reloads);
        assert.equal(backend._categories, oldCategories);
        assert.equal(backend._appsByCategory, oldApps);
        assert.equal(oldTree.connected, true);
        state.fail = false; app('new.desktop'); state.ids = ['new.desktop'];
        backend._reload();
        assert.equal(backend.reloads, reloads + 1);
        assert.equal(oldTree.connected, false);
        assert.equal(backend.getAppsByCategory('test')[0].get_id(), 'new.desktop');
        backend.destroy();
    });
}
test('catalog', 'initial category failure still permits installed app enumeration', () => {
    const {AppsBackend, state} = backendFixture();
    state.fail = 'load';
    const backend = new AppsBackend();
    assert.equal(backend.getAllApps().length, 1);
    state.fail = false; backend._reload();
    assert.equal(backend.getCategories().length, 1);
    backend.destroy();
});

const searchClasses = () => load('search.js',
    'SearchResultsBase, SearchResults, ListSearchResult, AppSearchResult, ProviderInfo');
function searchFixture() {
    const {SearchResultsBase} = searchClasses();
    const calls = [], created = [], published = [];
    const provider = {id: 'fake', canLaunchSearch: true,
        filterResults: (ids, limit) => ids.slice(0, limit),
        getResultMetas(ids, cancellable) {
            const call = {...pending(), ids, cancellable}; calls.push(call); return call.promise;
        }};
    const resultsView = {};
    const display = new SearchResultsBase(provider, resultsView);
    Object.assign(display, {
        _getMaxDisplayedResults: () => 10,
        _clearResultDisplay() { this.items = []; },
        _addItem(item) { assert.ok(!item.dead); this.items.push(item); },
        _createResultDisplay(meta) { const item = new Actor(meta); created.push(item); return item; },
        _setMoreCount(count) { this.more = count; },
    });
    const update = ids => display.updateSearch(ids, ids, () => published.push([...ids]));
    const resolve = (index, metas) => calls[index].resolve(metas ?? calls[index].ids.map(id => ({id, name: id})));
    return {display, provider, calls, created, published, update, resolve, resultsView};
}
for (const retire of ['new', 'cached', 'empty', 'clear', 'destroy', 'reject']) {
    test('search', `obsolete metadata cannot publish after ${retire}`, async () => {
        const f = searchFixture();
        const seed = f.update(['cached']); f.resolve(0); await seed;
        const old = f.update(['cached', 'old']);
        if (retire === 'new' || retire === 'reject') {
            const fresh = f.update(['new']); f.resolve(2); await fresh;
        } else if (retire === 'cached') await f.update(['cached']);
        else if (retire === 'empty') await f.update([]);
        else if (retire === 'clear') f.display.clear();
        else f.display.destroy();
        const published = f.published.length, created = f.created.length;
        if (retire === 'reject') f.calls[1].reject(Error('late failure'));
        else f.resolve(1);
        await old;
        assert.equal(f.published.length, published);
        assert.equal(f.created.length, created);
        assert.equal(f.calls[1].cancellable.is_cancelled(), true);
        if (retire !== 'destroy') f.display.destroy();
        assert.ok(f.created.every(actor => actor.dead));
    });
}
test('search', 'retained actors are bounded, reusable and prototype-safe', async () => {
    const f = searchFixture();
    for (let i = 0; i < 40; i++) {
        const ids = [`item-${i}`, '__proto__', '__proto__'];
        const request = f.update(ids); f.resolve(i); await request;
        assert.equal(f.display.items.length, 2);
        assert.equal(f.created.filter(actor => !actor.dead).length, 2);
    }
    f.resultsView._defaultResult = f.display.items[0];
    f.display.clear();
    assert.equal(f.resultsView._defaultResult, null);
    assert.ok(f.created.every(actor => actor.dead));
    f.display.destroy();
});
for (const failure of ['reject', 'invalid', 'partial']) {
    test('search', `${failure} metadata cleans actors and permits retry`, async () => {
        const f = searchFixture();
        const create = f.display._createResultDisplay;
        if (failure === 'partial') f.display._createResultDisplay = meta => {
            if (meta.id === 'b') throw Error('actor construction'); return create(meta);
        };
        const request = f.update(['a', 'b']);
        if (failure === 'reject') f.calls[0].reject(Error('provider'));
        else f.resolve(0, failure === 'invalid' ? [{id: 'wrong', name: 'wrong'}] : undefined);
        await request;
        assert.equal(f.display.visible, false);
        assert.ok(f.created.every(actor => actor.dead));
        f.display._createResultDisplay = create;
        const retry = f.update(['retry']); f.resolve(1); await retry;
        assert.equal(f.display.items[0].id, 'retry');
        f.display.destroy();
    });
}
test('search', 'actor destruction reentering search cannot overwrite replacement', async () => {
    const f = searchFixture();
    const seed = f.update(['a', 'b']); f.resolve(0); await seed;
    let replacement;
    f.created[0].connect('destroy', () => { replacement = f.update(['replacement']); });
    const retired = f.update(['obsolete']);
    f.resolve(1); await replacement; await retired;
    assert.deepEqual(f.display.items.map(item => item.id), ['replacement']);
    f.display.destroy();
});
for (const retire of ['query', 'remove', 'replace', 'destroy', 'reject']) {
    test('search', `provider completion is retired by ${retire}`, async () => {
        const {SearchResults} = searchClasses();
        const delayed = pending();
        const provider = {id: 'fake', getInitialResultSet: () => delayed.promise};
        const view = Object.create(SearchResults.prototype);
        Object.assign(view, {_terms: ['old'], _cancellable: new Cancellable(),
            _providerDisplays: new Map([[provider, {}]]), _results: {}, updates: 0,
            _updateResults() { this.updates++; }});
        const request = view._doProviderSearch(provider);
        if (retire === 'query' || retire === 'reject') {
            view._terms = ['new']; view._cancellable.cancel(); view._cancellable = new Cancellable();
        } else if (retire === 'remove') view._providerDisplays.delete(provider);
        else if (retire === 'replace') view._providerDisplays.set(provider, {});
        else view._providerDisplays = null;
        if (retire === 'reject') delayed.reject(Error('late'));
        else delayed.resolve(['old']);
        await request;
        assert.equal(view.updates, 0);
        assert.deepEqual(Object.keys(view._results), []);
    });
}

for (const type of ['ListSearchResult', 'AppSearchResult', 'ProviderInfo']) {
    test('activation', `${type} captures provider and terms before synchronous destruction`, () => {
        class ClosingApp extends Actor { activate() { this.emit('activated'); } }
        const copied = [], launches = [];
        const classes = load('search.js', type, {AppMenuItem: {AppMenuItem: ClosingApp},
            St: {...defaults.St, Clipboard: {get_default: () => ({set_text: (...args) => copied.push(args)})},
                ClipboardType: {CLIPBOARD: 1}}});
        const item = Object.create(classes[type].prototype);
        Actor.prototype._init.call(item);
        const provider = {canLaunchSearch: true,
            activateResult(id, terms) { assert.equal(this, provider); launches.push([id, ...terms]); },
            launchSearch(terms) { assert.equal(this, provider); launches.push([...terms]); }};
        Object.assign(item, {provider, metaInfo: {id: 'result', clipboardText: 'copy'},
            resultsView: {terms: ['original']}, _terms: ['original'], animateLaunch() {}});
        item.connect('activated', () => {
            item.resultsView.terms[0] = 'changed'; item._terms[0] = 'changed';
            item.destroy(); item.provider = null; item.metaInfo = null; item.resultsView = null;
        });
        item.activate();
        assert.equal(launches.length, 1);
        assert.deepEqual(launches[0], type === 'ProviderInfo' ? ['original'] : ['result', 'original']);
        assert.equal(copied.length, type === 'ProviderInfo' ? 0 : 1);
    });
}
for (const [name, method] of [['ApplicationButton', 'activate'], ['PowerButton', 'activatePowerOff'],
    ['RestartButton', 'activateRestart'], ['SuspendButton', 'activateSuspend'], ['LockButton', 'activateLockScreen']]) {
    test('activation', `${name} survives synchronous close without duplicate action`, () => {
        const classes = load('widgets/sessionButtons.js', name);
        const item = Object.create(classes[name].prototype);
        Actor.prototype._init.call(item);
        let calls = 0;
        item._app = item._systemActions = {[method]: () => calls++};
        item.connect('activated', () => { item.destroy(); item._app = item._systemActions = null; });
        item.activate();
        assert.equal(calls, 1);
    });
}

for (const kind of ['new-window', 'activate-app', 'system-action']) {
    test('activation', `search captures ${kind} before synchronous destruction`, () => {
        let calls = 0;
        const app = {can_open_new_window: () => kind === 'new-window', state: 1,
            open_new_window: () => calls++, activate: () => calls++};
        const {ListSearchResult} = load('search.js', 'ListSearchResult', {
            Shell: {AppState: {STOPPED: 0}, AppSystem: {get_default: () => ({lookup_app: () => app})}},
            SystemActions: {getDefault: () => ({activateAction: () => calls++})},
        });
        const item = Object.create(ListSearchResult.prototype);
        Actor.prototype._init.call(item);
        Object.assign(item, {provider: {}, metaInfo: {id: kind === 'system-action' ? 'power' : 'app.desktop'},
            resultsView: {terms: []}, animateLaunch() {}});
        item.connect('activated', () => { item.destroy(); item.metaInfo = null; });
        item.activate(); assert.equal(calls, 1);
    });
}
for (const [field, method] of [['_suspendItem', 'activateSuspend'], ['_restartItem', 'activateRestart'],
    ['_powerOffItem', 'activatePowerOff']]) {
    test('activation', `power submenu ${field} survives destruction while closing`, () => {
        let item, calls = 0;
        class Menu {
            constructor() { this.actor = new Actor(); }
            connect() {} addMenuItem() {}
            itemActivated() { item.destroy(); item._systemActions = item.powerMenu = null; }
        }
        const {PowerMenuButton} = load('widgets/sessionButtons.js', 'PowerMenuButton', {
            SecondaryMenu: {ButtonMenu: Menu}, PopupMenu: {PopupImageMenuItem: Actor},
            GObject: {...defaults.GObject, BindingFlags: {}}, BoxPointer: {PopupAnimation: {}},
            Main: {uiGroup: {add_child() {}}},
        });
        item = Object.create(PowerMenuButton.prototype);
        Actor.prototype._init.call(item);
        item._menuManager = {addMenu() {}};
        item._systemActions = {bind_property() {}, [method]() { calls++; }};
        item._createPowerMenu(); item[field].emit('activate');
        assert.equal(calls, 1);
    });
}

function timers() {
    let next = 0;
    const active = new Map();
    return {active, GLib: {timeout_add: (_priority, _time, callback) => { active.set(++next, callback); return next; },
        source_remove: id => { assert.ok(active.delete(id), 'unknown source'); },
        SOURCE_REMOVE: false, SOURCE_CONTINUE: true}};
}
function tooltipFixture() {
    const {active, GLib} = timers();
    const monitor = {x: 0, y: 0, width: 800, height: 600};
    class Label extends Actor {
        _init(props) { super._init(props); this.clutterText = {set() {}}; }
        remove_all_transitions() {}
        ease(options) { this.transition = options; }
        get_width() { return 100; } get_height() { return 30; }
        set_position() {} get_parent() { return {remove_child() {}}; }
    }
    const state = {monitor};
    const {Tooltip} = load('widgets/tooltip.js', 'Tooltip', {GLib, St: {Label},
        Pango: {WrapMode: {}}, Constants: {TooltipLocation: {BOTTOM: 0}},
        Clutter: {AnimationMode: {}}, Dash: {}, Utils: {isBlockHover: () => false},
        Main: {layoutManager: {findMonitorForActor: () => state.monitor}},
        global: {stage: {add_child() {}, remove_child() {}}}});
    const actor = {hover: true, connectObject() {}, disconnectObject() {},
        get_transformed_position: () => [10, 10], allocation: {x1: 0, x2: 20, y1: 0, y2: 20}};
    return {tooltip: new Tooltip(actor, 'title'), active, state};
}
for (const retire of ['hide', 'show', 'destroy']) {
    test('tooltip', `retired timer is inert after ${retire}`, () => {
        const {tooltip, active} = tooltipFixture();
        tooltip._onHover(); const callback = [...active.values()][0];
        tooltip[retire](); callback();
        assert.equal(active.size, 0);
        if (retire !== 'destroy') tooltip.destroy();
        tooltip.destroy();
    });
}
test('tooltip', 'retired fade cannot hide a new tooltip or touch destroyed actor', () => {
    const {tooltip} = tooltipFixture();
    tooltip.hide(); const old = tooltip.actor.transition.onComplete;
    tooltip.show(); old(); assert.equal(tooltip.actor.visible, true);
    tooltip.hide(); const last = tooltip.actor.transition.onComplete;
    tooltip.destroy(); last(); old();
});
test('tooltip', 'missing monitor is harmless', () => {
    const {tooltip, state} = tooltipFixture();
    state.monitor = null; tooltip.show(); tooltip.actor.transition.onComplete();
    assert.equal(tooltip.actor.visible, false); tooltip.destroy();
});

test('drag', 'repeated begin, retired callbacks, cancel and destruction own resources', () => {
    const {active, GLib} = timers(), monitors = new Set();
    const text = source('widgets/deskUxApps.js');
    const methods = text.slice(text.indexOf('    beginDrag()'), text.indexOf('    _canDrop('));
    const methodsObject = vm.runInNewContext(`new (class {${methods}})`, {GLib,
        DND: {addDragMonitor: m => monitors.add(m), removeDragMonitor: m => assert.ok(monitors.delete(m)),
            DragMotionResult: {CONTINUE: 1}}});
    Object.assign(methodsObject, {_cancelNavigation() {}, _resetScrollFeedback() {}, closeMenus() {},
        renders: 0, queueRender() { this.renders++; }});
    methodsObject._idle = GLib.timeout_add(0, 0, () => assert.fail('rebuild during drag'));
    const first = methodsObject.beginDrag();
    const oldTimer = [...active.values()][0], oldMonitor = [...monitors][0];
    const second = methodsObject.beginDrag();
    assert.equal(active.size, 1); assert.equal(monitors.size, 1);
    assert.equal(methodsObject.renders, 0);
    methodsObject.endDrag(first); oldTimer(); oldMonitor.dragMotion({x: 999, y: 999});
    assert.equal(methodsObject._drag, second); assert.equal(methodsObject._dragPoint, null);
    methodsObject.endDrag(); methodsObject.endDrag();
    assert.equal(active.size, 0); assert.equal(monitors.size, 0);
    assert.equal(methodsObject.renders, 1);
    methodsObject.beginDrag(); methodsObject._destroyed = true; methodsObject.endDrag();
    assert.equal(methodsObject.beginDrag(), null);
    assert.equal(active.size, 0); assert.equal(monitors.size, 0);
});

let count = 0;
for (const {group, name, run} of tests) {
    if (process.argv[2] && process.argv[2] !== group) continue;
    try { await run(); count++; console.log(`PASS ${name}`); }
    catch (error) { console.error(`FAIL ${name}`, error); process.exitCode = 1; }
}
console.log(`${count} lifecycle scenarios passed`);
