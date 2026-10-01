// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {ExtensionTransitions} from '../usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/extensionTransitions.js';

const root = new URL('../usr/share/gnome-shell/extensions/', import.meta.url);

for (const domain of ['communitybig.org', 'bigcommunity.org']) {
    const uuid = `layout-switcher-helper@${domain}`;
    const source = fs.readFileSync(new URL(`${uuid}/extension.js`, root), 'utf8');
    const method = source.slice(source.indexOf('    async _applyLayout(payload) {'), source.lastIndexOf('\n}'));
    // Resolve each shipped import, including the legacy sibling path.
    const modulePath = source.match(/import \{ExtensionTransitions\} from '([^']+)'/)[1];
    const imported = await import(new URL(modulePath, new URL(`${uuid}/extension.js`, root)));
    assert.equal(imported.ExtensionTransitions, ExtensionTransitions);

    for (const failure of [null, 'reload', 'disable', 'enable', 'rejected']) {
        const events = [];
        const live = new Set([uuid, 'panel', 'menu']);
        let pending = false;
        const manager = {
            _extensionOrder: ['panel', 'menu', uuid],
            disableExtension(id) {
                assert.equal(pending, false, 'previous transition must settle');
                events.push(`disable ${id}`);
                if (failure === 'disable' && id === 'panel') throw new Error('disable failed');
                live.delete(id);
                return failure === 'rejected' ? false : true;
            },
            enableExtension(id) {
                assert.equal(pending, false, 'previous transition must settle');
                events.push(`enable ${id}`);
                if (failure === 'enable' && id === 'new') throw new Error('enable failed');
                live.add(id);
                return failure === 'rejected' ? false : true;
            },
        };
        const Helper = vm.runInNewContext(`class Helper {${method}}; Helper`, {
            ExtensionTransitions,
            Main: {extensionManager: manager, loadTheme: () => events.push('theme')},
            applyShellColorScheme: () => false, ensureValidColorScheme: () => false,
            logHelper: () => undefined,
        });
        const helper = new Helper();
        helper._selfUuid = () => uuid;
        helper._liveUuids = () => new Set(live);
        helper._readActiveLayoutLabel = () => 'Classic';
        helper._isDown = state => state === 'down';
        helper._isSettledUp = state => state === 'up';
        const pause = async () => {
            assert.equal(pending, false);
            pending = true;
            await new Promise(resolve => setImmediate(resolve));
            pending = false;
        };
        helper._waitState = async (_manager, id, predicate) => {
            await pause();
            assert.ok(predicate(live.has(id) ? 'up' : 'down'));
            events.push(`settled ${id}`);
            return true;
        };
        helper._sleep = async delay => {
            assert.equal(delay, 23);
            await pause();
            events.push('sleep');
        };
        helper._reloadOne = async (_manager, id) => {
            await pause();
            events.push(`reload ${id}`);
            if (failure === 'reload') throw new Error('reload failed');
        };
        for (const name of ['_panelStyleRecompute', '_setupPanelSystemIndicator',
            '_syncLightOverviewPanelClass', '_syncNativeAccentPanelClass',
            '_syncBigGnomePanelClass', '_syncMinimalPanelClass',
            '_syncGUnitySurfaceClasses', '_syncNotificationPosition']) {
            helper[name] = () => undefined;
        }
        const result = JSON.parse(await helper._applyLayout(JSON.stringify({
            enabled: [uuid, 'menu', 'new'], reload: [uuid, 'menu'],
            teardown: [uuid, 'panel'], step_ms: 23,
        })));
        assert.equal(result.ok, true);
        assert.ok(live.has(uuid));
        assert.ok(!events.some(event => event.endsWith(uuid)));
        assert.equal(events.filter(event => event === 'enable menu').length, 1);
        assert.ok(events.indexOf('theme') < events.indexOf('enable menu'));
        assert.ok(events.indexOf('enable menu') < events.indexOf('enable new'));
        const panelIndex = events.indexOf('reload panel');
        const menuIndex = events.indexOf('disable menu');
        assert.ok(domain === 'communitybig.org' ? menuIndex < panelIndex : panelIndex < menuIndex);
        if (failure === 'rejected') {
            assert.ok(result.steps.includes('disable panel REJECTED'));
            assert.ok(result.steps.includes('enable new REJECTED'));
        } else if (failure) {
            assert.ok(result.steps.some(step => step.includes(`ERR Error: ${failure} failed`)));
        } else {
            assert.deepEqual([...live], [uuid, 'menu', 'new']);
            assert.ok(events.indexOf('reload panel') < events.indexOf('disable panel'));
            assert.ok(events.indexOf('settled menu') < events.indexOf('enable menu'));
        }
    }
}
console.log('Helper transitions: both UUIDs, ordering, self-protection, failures and rejection passed');
