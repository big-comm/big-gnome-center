// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const root = new URL('../usr/share/gnome-shell/extensions/', import.meta.url);
const runtime = new URL('layout-switcher-runtime@communitybig.org/', root);
const menu = new URL('community-menu@communitybig.org/', root);
const read = (base, file) => fs.readFileSync(new URL(file, base), 'utf8');
const load = (source, name, context) => vm.runInNewContext(
    source.replace(/^import .*;\n/gm, '').replaceAll('export ', '') + `\n${name};`, context);

function startup(startingUp) {
    const callbacks = new Map();
    const adjustment = {value: 1, remove_transition() {}};
    const Main = {
        sessionMode: {hasOverview: true},
        layoutManager: {
            _startingUp: startingUp,
            connect(name, callback) { callbacks.set(name, callback); return name; },
            disconnect(id) { callbacks.delete(id); },
        },
        overview: {
            visible: false, visibleTarget: false, hides: 0,
            _overview: {controls: {_stateAdjustment: adjustment}},
            hide() { this.hides++; this.visible = false; this.visibleTarget = false; },
        },
    };
    const context = {Main, global: {}, ControlsState: {HIDDEN: 0}};
    const Integration = load(read(runtime, 'startupOverviewIntegration.js'), 'StartupOverviewIntegration', context);
    return {Main, adjustment, Integration, callbacks};
}

for (const late of [false, true]) {
    const state = startup(!late);
    const integration = new state.Integration();
    integration.apply(true);
    if (!late) {
        assert.equal(state.Main.sessionMode.hasOverview, false);
        state.Main.layoutManager._startingUp = false;
        state.callbacks.get('startup-complete')();
    }
    assert.equal(state.Main.sessionMode.hasOverview, true);
    assert.equal(state.adjustment.value, 0, 'skipped overview must finish in desktop state');
    assert.equal(state.callbacks.size, 0);
    state.Main.overview.visible = true;
    integration.apply(true);
    assert.equal(state.Main.overview.hides, 0, 'settings updates must not close user overview');
    integration.destroy();
    new state.Integration().apply(true);
    assert.equal(state.Main.overview.hides, 0, 'runtime reload must not repeat startup handling');
}
const race = startup(true);
const raced = new race.Integration();
raced.apply(true);
race.Main.overview.visible = true;
race.Main.overview.visibleTarget = true;
race.Main.layoutManager._startingUp = false;
race.callbacks.get('startup-complete')();
assert.equal(race.Main.overview.hides, 1, 'overview already started must be closed after startup');
const normal = startup(true);
new normal.Integration().apply(false);
normal.Main.layoutManager._startingUp = false;
normal.callbacks.get('startup-complete')();
assert.equal(normal.adjustment.value, 1, 'normal startup remains unchanged');

const Constants = Object.fromEntries(['COMMUNITY_PANEL_UUID', 'RUNTIME_UUID'].map(name =>
    [name, read(menu, 'constants.js').match(new RegExp(`export const ${name} = '([^']+)'`))[1]]));
const providers = new Map();
const global = {};
const extensionSource = read(menu, 'extension.js');
const detect = extensionSource.slice(extensionSource.indexOf('    _getActivePanelExtension() {'),
    extensionSource.indexOf('    _connectExtensionSignals() {'));
const Extension = vm.runInNewContext(`class Extension {${detect}}; Extension`, {
    Constants, global, Main: {extensionManager: {lookup: uuid => providers.get(uuid)}},
    Utils: {isExtensionEnabled: extension => extension?.state === 1},
});
const extension = new Extension();
for (const uuid of Object.values(Constants)) {
    providers.clear();
    providers.set(uuid, {state: 1});
    global.dashToPanel = {panels: []};
    extension._getActivePanelExtension();
    assert.equal(extension._panelExtension, 'dashToPanel');
    delete global.dashToPanel;
    extension._getActivePanelExtension();
    assert.equal(extension._panelExtension, null);
}
const menuSource = read(menu, 'menu.js');
const arrowMethod = menuSource.slice(menuSource.indexOf('    _syncArrowSide() {'),
    menuSource.indexOf('    setLightStyle(enabled) {'));
const showMethod = menuSource.slice(menuSource.indexOf('    _maybeShowPanel() {'),
    menuSource.indexOf('    // Return that the menu is not empty'));
const Button = vm.runInNewContext(`class Button {${arrowMethod}${showMethod}}; Button`,
    {St: {Side: {TOP: 0}}});
const button = new Button();
let held = false;
button._panelParent = {
    getPosition: () => 2,
    intellihide: {enabled: true, revealAndHold: () => { held = true; }},
};
button._menu = {_arrowSide: 0};
button._setMenuArrowSides = side => { button._menu._arrowSide = side; };
button._syncArrowSide();
assert.equal(button._menu._arrowSide, 2, 'bottom panel must anchor menu above it');
button._maybeShowPanel();
assert.equal(held, true, 'keyboard menu must reveal and hold its owning panel');
const trackingSource = read(runtime, 'dockPanelController.js');
const trackingMethod = trackingSource.slice(trackingSource.indexOf('    _applyPanelTracking(mode) {'),
    trackingSource.indexOf('    _dockTrackingDiagnostics() {'));
const Tracking = vm.runInNewContext(`class Tracking {${trackingMethod}}; Tracking`, {
    Main: {layoutManager: {_queueUpdateRegions() {}}},
});
for (const layout of ['BigGnome', 'G-Unity']) {
    const tracking = new Tracking();
    tracking._autohide = {setEnabled() {}};
    tracking._panelActorData = {};
    tracking._originalAffectsStruts = true;
    tracking._originalTrackFullscreen = true;
    tracking._inOverview = false;
    tracking._applyPanelTracking('always-hidden');
    assert.equal(tracking._panelActorData.affectsStruts, false);
    tracking._inOverview = true;
    tracking._applyPanelTracking('always-hidden');
    assert.equal(tracking._panelActorData.affectsStruts, true, `${layout}: reserve overview panel space`);
    tracking._inOverview = false;
    tracking._applyPanelTracking('always-hidden');
    assert.equal(tracking._panelActorData.affectsStruts, false);
}
console.log('Startup, menu ownership, anchoring and overview struts passed');
