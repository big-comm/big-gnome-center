// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {ExtensionTransitions} from '../usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/extensionTransitions.js';

const root = new URL('../usr/share/gnome-shell/extensions/', import.meta.url);
const shared = fs.readFileSync(new URL('layout-switcher-helper@communitybig.org/helperLifecycle.js', root), 'utf8');
const Main = {extensionManager: null};
let now = 0;
const timers = new Map();
let timerId = 0;
const queried = [];
const missing = new Set();
const shell = {};
const HelperLifecycle = vm.runInNewContext(shared.replace(/^import .*;$/gm, '')
    .replace('export class', 'class') + '\nHelperLifecycle;', {
    Main, global: shell,
    Extension: class { constructor(metadata) { this.metadata = metadata; } },
    ExtensionType: {SYSTEM: 1},
    Gio: {File: {new_for_path(path) {
        queried.push(path);
        return {path, query_exists: () => !missing.has(path.split('/').at(-1))};
    }}},
    GLib: {
        get_monotonic_time: () => now * 1000,
        PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
        timeout_add(_priority, delay, callback) {
            timers.set(++timerId, {delay, callback});
            return timerId;
        },
        Variant: class { constructor(signature, values) { this.signature = signature; this.values = values; } },
    },
});

// The actual sleep tracks its source until the main-loop callback runs.
const timerHelper = new HelperLifecycle({uuid: 'timer'});
timerHelper._pendingSources = new Set();
let resolved = false;
const sleeping = timerHelper._sleep(50).then(() => { resolved = true; });
assert.equal(resolved, false);
assert.ok(timerHelper._pendingSources.has(timerId));
assert.equal(timers.get(timerId).delay, 50);
timers.get(timerId).callback();
await sleeping;
assert.equal(resolved, true);
assert.equal(timerHelper._pendingSources.size, 0);

const helper = new HelperLifecycle({uuid: 'polling'});
let polls = 0;
helper._sleep = async delay => { now += delay; polls++; };
assert.equal(await helper._waitUntil(() => now >= 100, 100), true);
assert.equal(polls, 2);
assert.equal(await helper._waitUntil(() => false, 100), false);
helper._cancelled = true;
const before = polls;
assert.equal(await helper._waitUntil(() => { throw new Error('cancelled predicate ran'); }), false);
assert.equal(polls, before);
helper._cancelled = false;
shell.dashToPanel = {panels: [{taskbar: {_box: {}}}]};
assert.equal(await helper._waitDashToPanelReady(), true);
shell.dashToPanel.panels = [];
assert.equal(await helper._waitDashToPanelReady(0), false);
assert.equal(await helper._waitState({lookup: () => ({state: 1})}, 'active', state => state === 1), true);

// Discovery accepts only shipped UUIDs, de-duplicates, and loads sequentially.
const known = new Map([['community-panel@communitybig.org', {}]]);
const loading = [];
let inFlight = false;
missing.add('big-shot@communitybig.org');
Main.extensionManager = {
    lookup: uuid => known.get(uuid),
    createExtensionObject(uuid, directory, type) {
        assert.equal(type, 1);
        assert.equal(directory.path, `/usr/share/gnome-shell/extensions/${uuid}`);
        return {uuid};
    },
    async loadExtension(extension) {
        assert.equal(inFlight, false);
        inFlight = true;
        await new Promise(resolve => setImmediate(resolve));
        loading.push(extension.uuid);
        inFlight = false;
        if (extension.uuid === 'community-menu@communitybig.org') throw new Error('broken extension');
        known.set(extension.uuid, extension);
    },
};
const result = await helper._discoverExtensions(JSON.stringify({uuids: [
    'community-panel@communitybig.org', 'community-dock@communitybig.org',
    'community-dock@communitybig.org', 'community-menu@communitybig.org',
    'big-shot@communitybig.org', '../../untrusted',
]}));
assert.equal(result.ok, false);
assert.deepEqual([...result.loaded], ['community-dock@communitybig.org']);
assert.deepEqual([...result.missing], ['big-shot@communitybig.org', 'community-menu@communitybig.org']);
assert.match(result.error, /broken extension/);
assert.deepEqual(loading, ['community-dock@communitybig.org', 'community-menu@communitybig.org']);
assert.ok(queried.every(path => !path.includes('untrusted')));
let reply;
helper.DiscoverExtensionsAsync(['{invalid'], {return_value(value) { reply = value; }});
await new Promise(resolve => setImmediate(resolve));
assert.equal(reply.signature, '(s)');
assert.equal(JSON.parse(reply.values[0]).ok, false);

// Run the shipped classes with the shared base, preserving their UUIDs and
// different frame-draining policies without starting a real Shell session.
for (const domain of ['communitybig.org', 'bigcommunity.org']) {
    const uuid = `layout-switcher-helper@${domain}`;
    const source = fs.readFileSync(new URL(`${uuid}/extension.js`, root), 'utf8');
    const importPath = source.match(/import \{HelperLifecycle\} from '([^']+)'/)[1];
    assert.equal(fs.realpathSync(new URL(importPath, new URL(`${uuid}/extension.js`, root))),
        fs.realpathSync(new URL('layout-switcher-helper@communitybig.org/helperLifecycle.js', root)));
    for (const mode of ['success', 'timeout', 'rejected', 'failure']) {
        const events = [], active = new Map([[uuid, 1], ['panel', 1], ['menu', 1]]);
        const manager = {
            _extensionOrder: ['panel', uuid, 'menu'],
            getUuids: () => [...active.keys()],
            lookup: id => ({state: active.get(id)}),
            disableExtension(id) {
                events.push(`disable ${id}`);
                if (mode === 'failure' && id === 'menu') throw new Error('disable failed');
                if (mode === 'rejected' && id === 'menu') return false;
                if (mode !== 'timeout') active.delete(id);
                return true;
            },
        };
        Main.extensionManager = manager;
        const Helper = vm.runInNewContext(source.slice(source.indexOf('export default class'))
            .replace('export default ', '') + '\nLayoutSwitcherHelper;', {
            HelperLifecycle, ExtensionTransitions, Main,
            CURTAIN_FADE_MS: 100, ROLLBACK_TIMEOUT_S: 60,
            System: {gc: () => events.push('gc')}, logHelper: () => undefined,
        });
        const instance = new Helper({uuid});
        let frames = 0;
        instance._curtainUp = () => events.push('curtain');
        instance._clearBigGnomeDockClass = () => events.push('clear dock');
        instance._isGUnityActive = () => false;
        instance._yieldTransitionFrame = async () => { frames++; };
        instance._sleep = async delay => { now += delay; };
        instance._armRollbackTimer = seconds => {
            assert.equal(seconds, 60);
            events.push('rollback armed');
        };
        assert.equal(instance._selfUuid(), uuid);
        const answer = await instance._beginSwitch('{}');
        assert.equal(answer.ok, true);
        assert.deepEqual([...manager._extensionOrder], [uuid, 'panel', 'menu']);
        assert.deepEqual([...instance._prevEnabled], [uuid, 'panel', 'menu']);
        assert.ok(active.has(uuid));
        assert.ok(events.indexOf('rollback armed') < events.indexOf('disable menu'));
        assert.ok(events.indexOf('disable menu') < events.indexOf('disable panel'));
        assert.deepEqual([...answer.disabled], mode === 'rejected' || mode === 'failure'
            ? ['panel'] : ['menu', 'panel']);
        assert.equal(frames, domain === 'communitybig.org' ? answer.disabled.length : 0);
        if (mode === 'timeout') assert.ok(answer.steps.some(step => step.endsWith('TIMEOUT')));
        if (mode === 'rejected') assert.ok(answer.steps.includes('disable menu REJECTED'));
        if (mode === 'failure') assert.ok(answer.steps.some(step => step.includes('ERR Error: disable failed')));
        if (domain === 'communitybig.org' && mode === 'success') {
            const lists = {'enabled-extensions': ['pending'], 'disabled-extensions': []};
            instance._shellSettings = {get_strv: key => lists[key]};
            manager._enabledExtensions = [];
            assert.equal(await instance._waitConfigured(manager, 'pending', 0), false);
            manager._enabledExtensions = ['pending'];
            assert.equal(await instance._waitConfigured(manager, 'pending', 0), true);
            lists['disabled-extensions'] = ['pending'];
            assert.equal(await instance._waitConfigured(manager, 'pending', 0), false);
            lists['enabled-extensions'] = [];
            assert.equal(await instance._waitUnconfigured(manager, 'pending', 0), false);
            manager._enabledExtensions = [];
            active.set('pending', 7);
            assert.equal(await instance._waitUnconfigured(manager, 'pending', 0), false);
            active.delete('pending');
            assert.equal(await instance._waitUnconfigured(manager, 'pending', 0), true);
        }
    }
}
console.log('Helper lifecycle: discovery, cancellation, timeouts, both UUIDs and rollback ordering passed');
