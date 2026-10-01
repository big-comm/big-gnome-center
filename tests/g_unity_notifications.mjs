// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source = fs.readFileSync(new URL('../usr/share/gnome-shell/extensions/layout-switcher-helper@communitybig.org/extension.js', import.meta.url), 'utf8');
let height = 800;
let scale = 1;
const Main = {layoutManager: {
    findMonitorForActor: () => ({index: 0}),
    getWorkAreaForMonitor: () => ({y: 29, height: height - 29}),
}};
const St = {Bin: class {
    vfunc_get_preferred_height() { return [190, 1200]; }
}, ThemeContext: {get_for_stage: () => ({scale_factor: scale})}};
const start = source.indexOf('class GUnityMessageBin extends St.Bin');
const Bin = vm.runInNewContext(`(${source.slice(start, source.indexOf('\n});', start) + 2)})`, {Main, St, global: {stage: {}}});
const bin = new Bin();
const row = h => ({get_preferred_height: () => [h, h]});
let rows = [[row(40)], [row(48), row(48)], [row(48)], [bin]];
const node = padding => ({adjust_preferred_height: () => [padding, padding], get_length: () => 6});
bin.menuOwner = {
    sourceActor: {get_transformed_position: () => [900, 0], get_transformed_size: () => [124, 29]},
    _grid: {layout_manager: {_getRows: () => rows, row_spacing: 12, _overlay: row(0)}},
    box: {get_theme_node: () => node(38)},
    _boxPointer: {get_theme_node: () => node(0)},
};
function fits() {
    const [min, nat] = bin.vfunc_get_preferred_height(332);
    const controls = rows.slice(0, -1).reduce((sum, r) => sum + Math.max(...r.map(a => a.get_preferred_height(-1)[1])), 0);
    const total = nat + controls + (rows.length - 1) * 12 + 38 + 6;
    assert.ok(total <= height - 29 - 12 * scale, `popup ${total} must fit screen ${height}`);
    assert.ok(min >= 0 && min <= nat);
    return nat;
}
assert.ok(fits() > 190, 'retain room to scroll expanded groups');
rows.splice(2, 0, [row(48), row(48)], [row(48), row(48)]);
fits();
height = 600;
fits();
height = 1600;
scale = 2;
fits();

class Signals {
    constructor() { this.handlers = new Map(); this.next = 0; }
    connect(name, fn) { const id = ++this.next; this.handlers.set(id, {name, fn}); return id; }
    disconnect(id) { assert.ok(this.handlers.delete(id)); }
    emit(name, value) { for (const h of this.handlers.values()) if (h.name === name) h.fn(this, value); }
}
const methods = ['_setupGUnityMessageEvents', '_teardownGUnityMessageEvents'].map(name => {
    const i = source.indexOf(`    ${name}(`);
    return source.slice(i, source.indexOf('\n    }', i) + 6);
});
const Helper = vm.runInNewContext(`class Helper {${methods.join('\n')}}; Helper`);
for (const version of [50, 51]) {
    const helper = new Helper();
    const menu = new Signals(); menu.actor = new Signals();
    const dateMenu = {menu: {actor: {calendar: true}}};
    let collapsed = 0;
    let captured = 0;
    const list = {_messageView: {collapse() { collapsed++; }}, maybeCollapseMessageGroupForEvent() { captured++; }};
    if (version === 51) list.setCaptureContainer = actor => {list.capture = actor;};
    for (let cycle = 0; cycle < 3; cycle++) {
        helper._gUnityMessageBin = {menuOwner: menu};
        helper._setupGUnityMessageEvents(list, menu);
        if (version === 51) assert.equal(list.capture, menu.actor);
        else {
            assert.equal(menu.actor.handlers.size, 3);
            menu.actor.emit('captured-event::button', {});
            assert.equal(captured, cycle + 1);
        }
        const before = collapsed;
        menu.emit('open-state-changed', true);
        assert.equal(collapsed, before);
        menu.emit('open-state-changed', false);
        assert.equal(collapsed, before + 1, 'closing releases expanded state');
        helper._teardownGUnityMessageEvents(list, dateMenu);
        assert.equal(collapsed, before + 2);
        assert.equal(menu.handlers.size, 0);
        assert.equal(menu.actor.handlers.size, 0);
        assert.equal(helper._gUnityMessageBin.menuOwner, null);
        if (version === 51) assert.equal(list.capture, dateMenu.menu.actor);
        helper._teardownGUnityMessageEvents(list, dateMenu);
        assert.equal(collapsed, before + 2, 'teardown is idempotent');
    }
}
// Layout lifecycle must preserve the labelled native DND control and its state.
class Actor extends Signals {
    constructor(props = {}) { super(); Object.assign(this, props); this.children = []; }
    add_child(child) { this.children.push(child); }
    get_children() { return this.children; }
    add_style_class_name(name) { (this.styles ??= new Set()).add(name); }
    remove_style_class_name(name) { this.styles?.delete(name); }
    destroy() { this.handlers.clear(); }
}
const nativeDnd = new Actor({visible: true, checked: false, title: 'Do Not Disturb'});
nativeDnd.hide = () => { nativeDnd.visible = false; };
const systemBox = new Actor();
systemBox.children = [new Actor(), new Actor(), new Actor()];
systemBox.insert_child_at_index = (actor, index) => systemBox.children.splice(index, 0, actor);
const quickSettings = {
    _doNotDisturb: {quickSettingsItems: [nativeDnd]},
    _system: {_systemItem: {child: systemBox}},
    menu: {actor: new Actor()},
};
const shellMain = {
    panel: {statusArea: {dateMenu: {}, quickSettings}, _leftBox: new Actor(), _rightBox: new Actor()},
    overview: new Signals(),
};
const display = new Signals();
const lifecycleMethods = ['_setupGUnityShell', '_teardownGUnityShell', '_teardownGUnityMessageEvents', '_setupGUnityDndAction']
    .filter(name => source.includes(`    ${name}(`))
    .map(name => {
        const i = source.indexOf(`    ${name}(`);
        return source.slice(i, source.indexOf('\n    }', i) + 6);
    });
const ShellHelper = vm.runInNewContext(`class Helper {${lifecycleMethods.join('\n')}}; Helper`, {
    Main: shellMain, global: {display}, KIWI_UUID: 'kiwi',
    St: {BoxLayout: Actor, Icon: Actor, Label: Actor, Button: Actor},
    Clutter: {ActorAlign: {CENTER: 0}},
});
const shellHelper = new ShellHelper();
shellHelper._extensionWillRun = () => false;
shellHelper._syncGUnityDatePosition = () => {};
shellHelper._syncGUnityWindowTitle = () => {};
for (const checked of [false, true, false]) {
    nativeDnd.checked = checked;
    shellHelper._setupGUnityShell();
    shellHelper._setupGUnityShell();
    assert.equal(nativeDnd.visible, true, 'G-Unity keeps the labelled native toggle visible');
    assert.equal(nativeDnd.checked, checked, 'entering G-Unity preserves DND preference');
    assert.equal(systemBox.children.length, 3, 'no duplicate icon-only control');
    shellHelper._teardownGUnityShell();
    assert.equal(nativeDnd.visible, true);
    assert.equal(nativeDnd.checked, checked, 'leaving G-Unity preserves DND preference');
    assert.equal(display.handlers.size, 0);
    assert.equal(shellMain.overview.handlers.size, 0);
    assert.equal(shellMain.panel._rightBox.handlers.size, 0);
}
console.log('G-Unity notification geometry and lifecycle passed');
