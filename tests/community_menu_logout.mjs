// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL(
    '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/widgets/sessionButtons.js', import.meta.url), 'utf8');
const start = source.indexOf('class CommunityBigLogoutButton');
const end = source.indexOf('\n});', start) + 2;
const policySignals = new Map();
const modeSignals = new Map();
let disabled = false;
let closed = 0;
let hidden = 0;
const requests = [];
const mode = {
    isLocked: false, isGreeter: false,
    connectObject: (signal, callback) => modeSignals.set(signal, callback),
    disconnectObject: () => modeSignals.clear(),
};
const Button = vm.runInNewContext(`(${source.slice(start, end)})`, {
    SessionButton: class {
        _init() {}
        activate() { closed++; }
        _onDestroy() {}
    },
    Gio: {Settings: class {
        get_boolean() { return disabled; }
        connectObject(signal, callback) { policySignals.set(signal, callback); }
        disconnectObject() { policySignals.clear(); }
    }},
    Main: {sessionMode: mode, overview: {hide() { hidden++; }}},
    GnomeSession: {SessionManager: () => ({LogoutAsync: flags => {
        requests.push(flags);
        return Promise.resolve();
    }})},
    _: text => text, console,
});
const button = new Button();
button._init({canLogout: false});
assert.equal(button.visible, true, 'Single-user Shell visibility does not hide the explicit logout button');
button.activate();
assert.deepEqual(requests, [0], 'Request normal confirmation; never force logout');
assert.equal(closed, 1);
assert.equal(hidden, 1);
disabled = true;
policySignals.get('changed::disable-log-out')();
assert.equal(button.visible, false, 'Respect administrator logout policy');
button.activate();
disabled = false;
for (const flag of ['isLocked', 'isGreeter']) {
    mode[flag] = true;
    modeSignals.get('updated')();
    assert.equal(button.visible, false, `Hide during ${flag}`);
    button.activate();
    mode[flag] = false;
}
modeSignals.get('updated')();
assert.equal(button.visible, true);
assert.deepEqual(requests, [0], 'Blocked activations never contact the session manager');
button._onDestroy();
assert.equal(policySignals.size, 0);
assert.equal(modeSignals.size, 0);
console.log('Logout visibility, lockdown, session modes, confirmation, and cleanup passed');
