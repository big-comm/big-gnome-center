// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/extension.js', import.meta.url), 'utf8');
const start = source.indexOf('    enable() {');
assert.notEqual(start, -1);
const method = source.slice(start, source.indexOf('\n    }', start) + 6);
const messages = [];
class Settings {
    connect() { return 1; }
    get_string() { return 'prefer-dark'; }
}
class Follower {
    constructor(settings) { this.settings = settings; }
}
const Helper = vm.runInNewContext(`class Helper {${method}}; Helper`, {
    Gio: {Settings}, GtkThemeFollower: Follower, FolderAccentFollower: Follower,
    applyShellColorScheme: () => undefined,
    logHelper: message => messages.push(message),
});

for (const failure of [null, 'timer', 'callback']) {
    messages.length = 0;
    const helper = new Helper();
    for (const name of ['_export', '_setupPanelSystemIndicator',
        '_syncNativeAccentPanelClass', '_syncBigGnomePanelClass',
        '_syncMinimalPanelClass', '_syncGUnitySurfaceClasses',
        '_syncLightOverviewPanelClass']) {
        helper[name] = () => undefined;
    }
    let synced = 0;
    helper._syncNotificationPosition = () => { synced++; };
    helper._readActiveLayoutLabel = () => 'G-Unity';
    helper._sleep = () => failure === 'timer'
        ? Promise.reject(new Error('timer failed')) : Promise.resolve();
    helper._onColorSchemeChanged = () => {
        if (failure === 'callback') throw new Error('callback failed');
    };
    helper.enable();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(synced, failure ? 1 : 2);
    assert.deepEqual(messages, failure
        ? [`delayed startup sync failed: Error: ${failure} failed`] : []);
}
console.log('Helper startup: success and delayed failures handled');
