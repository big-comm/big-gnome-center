// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {FOLDER_COLORS, folderTint} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/deskUxModel.js';

const root = '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/';
const source = fs.readFileSync(new URL(`${root}widgets/deskUxApps.js`, import.meta.url), 'utf8');
const css = fs.readFileSync(new URL(`${root}stylesheet.css`, import.meta.url), 'utf8');
const theme = fs.readFileSync(new URL('../usr/share/big-gnome-center/constants.py', import.meta.url), 'utf8');
for (const [color, hex] of FOLDER_COLORS) {
    assert(theme.includes(`"${color}": "${hex}"`), 'Palette matches system theme');
    const rgb = hex.slice(1).match(/../g).map(value => parseInt(value, 16)).join(',');
    assert(css.includes(`.desk-ux-color-${color} { background-color: rgba(${rgb},0.22)`));
}

class Actor {
    constructor(...args) { this._init(...args); }
    _init(props = {}) {
        Object.assign(this, props);
        this.children = [];
        this.clutter_text = {
            set_single_line_mode(value) {this.single = value;},
            set_line_wrap(value) {this.wrap = value;},
            set_line_wrap_mode() {},
            set_ellipsize(value) {this.ellipsize = value;},
        };
    }
    add_child(child) {this.children.push(child);}
    set_child(child) {this.child = child;}
    set(props) {Object.assign(this, props);}
    set_style(value) {this.style = value;}
    add_style_class_name(value) {this.style_class += ` ${value}`;}
    add_style_pseudo_class(value) {this.pseudo = value;}
    connect(signal, callback) {this[signal] = callback;}
    add_action() {}
}
const Clutter = {ActorAlign: {START: 'start', CENTER: 'center', FILL: 'fill', END: 'end'},
    BinLayout: class {}, ClickGesture: Actor, AnimationMode: {EASE_OUT_QUAD: 1}};
const Pango = {WrapMode: {WORD_CHAR: 1}, EllipsizeMode: {NONE: 'none', END: 'end'}};
const St = Object.fromEntries(['Button', 'Widget', 'Bin', 'Icon', 'Label'].map(name => [name, Actor]));
const box = vertical => new Actor({vertical});
const tileSource = source.slice(source.indexOf('const Tile ='), source.indexOf('export const DeskUxApps'));
const Tile = vm.runInNewContext(`${tileSource}; Tile`, {
    GObject: {registerClass: klass => klass}, St, Clutter, Pango, box, _: text => text,
    folderTint, DND: {makeDraggable: () => new Actor()},
});
for (const list of [false, true]) {
    for (const name of ['Files', 'A very long application name that must not shift the icon']) {
        const tile = new Tile({listMode: list, selecting: false}, {app: {
            get_name: () => name, create_icon_texture: size => new Actor({size}),
            get_app_info: () => ({get_description: () => 'Description'}),
        }});
        const [slot, label, description] = tile.child.children;
        assert.equal(slot.x_expand, !list, 'List icon column never absorbs text-dependent spare width');
        assert.equal(label.clutter_text.wrap, !list);
        assert.equal(label.clutter_text.single, list);
        if (list) {
            assert.equal(label.y_align, 'center');
            assert.equal(label.x_expand, true);
            assert.equal(label.clutter_text.ellipsize, 'end');
            assert.equal(description.y_align, 'center');
        }
    }
}
const actionMethod = source.slice(source.indexOf('    _actionTile('), source.indexOf('    _renderBody('));
const Actions = vm.runInNewContext(`class Actions {${actionMethod}}; Actions`, {St, Clutter, Pango, box});
for (const list of [false, true]) {
    const actions = new Actions();
    actions.listMode = list;
    let tile;
    actions._actionTile('Add Applications', () => {}, {add_item: value => {tile = value;}});
    assert.equal(tile.child.vertical, !list, 'Action cards follow list/grid orientation');
    assert.equal(tile.child.children[0].x_expand, !list);
    assert.equal(tile.child.children[1].clutter_text.wrap, !list);
}

const pickerMethod = source.slice(source.indexOf('    _colorPicker('), source.indexOf('    _actionTile('));
class ColorGrid extends Actor {
    constructor(columns) {super(); this.columns = columns;}
    add_item(item) {this.add_child(item);}
}
const Picker = vm.runInNewContext(`class Picker {${pickerMethod}}; Picker`, {
    St, Grid: ColorGrid, FOLDER_COLORS, themeText: text => text,
    button: (label, clicked) => {const actor = new Actor({label}); actor.connect('clicked', clicked); return actor;},
});
for (const width of [280, 700]) {
    const picker = new Picker();
    picker._layoutWidth = width;
    picker._toolbar = new Actor();
    picker._colorButtons = [];
    picker._heading = () => {};
    let selected = 'red';
    let accepted = true;
    let queued = false;
    picker.queueRender = () => {queued = true;};
    picker._folderColors = {writable: true, get: () => selected,
        set: (_id, color) => {if (accepted) selected = color; return accepted;}};
    picker._colorPicker({id: 'folder'});
    const grid = picker._toolbar.children.at(-1);
    assert.equal(grid.children.length, 10, 'Every system color is available');
    assert.equal(grid.children.filter(item => item.checked).length, 1);
    assert.equal(grid.children.find(item => item.checked).accessible_name, 'Red');
    assert.equal(grid.columns, width === 700 ? 10 : 6, 'Palette wraps using the stable parent width');
    const blue = grid.children.find(item => item.colorKey === 'blue');
    blue.clicked();
    assert.equal(selected, 'blue');
    assert(queued, 'Refresh saved color and preserve keyboard focus');
    accepted = false;
    grid.children.find(item => item.colorKey === 'green').clicked();
    assert.equal(selected, 'blue', 'Rejected choice preserves saved color');
    accepted = true;
    picker._colorButtons[0].clicked();
    assert.equal(selected, null, 'Default restores the original automatic tint');
    picker._folderColors.writable = false;
    picker._colorButtons = [];
    picker._colorPicker({id: 'folder'});
    assert(picker._colorButtons.every(item => !item.reactive && !item.can_focus), 'Locked palette stays disabled');
}

const navigation = source.slice(source.indexOf('    navigate('), source.indexOf('    closeMenus('));
const settings = {enable_animations: true, reduced_motion: false};
const Navigator = vm.runInNewContext(`class Navigator {${navigation}}; Navigator`, {
    St: {Settings: {get: () => settings}}, Clutter,
});
const screen = new Navigator();
screen.view = null;
screen.mapped = true;
screen._navigationSerial = 0;
screen.closeMenus = () => {};
let renders = 0;
screen.queueRender = () => {renders++;};
screen._render = () => {renders++;};
screen.remove_transition = () => {};
const transitions = [];
screen.ease = parameters => transitions.push(parameters);
screen.navigate('folder');
assert.equal(renders, 0, 'Retain old content during fade-out');
assert.equal(screen._navigationFading, true);
const outgoing = transitions.shift();
assert.equal(outgoing.opacity, 0);
outgoing.onComplete();
assert.equal(renders, 1, 'Render once between fades');
const incoming = transitions.shift();
assert.equal(incoming.opacity, 255);
assert.equal(outgoing.duration + incoming.duration, 170, 'Short opacity-only transition');
assert.deepEqual(Object.keys(outgoing).sort(), ['duration', 'mode', 'onComplete', 'opacity']);

screen.navigate('@all');
const stale = transitions.shift();
screen.back();
const latest = transitions.shift();
const before = renders;
stale.onComplete();
assert.equal(renders, before, 'Rapid navigation ignores stale callbacks');
latest.onComplete();
assert.equal(screen.view, null);
assert.equal(renders, before + 1);
transitions.length = 0;
screen.navigate('folder');
const closed = transitions.shift();
screen.reset();
closed.onComplete();
assert.equal(screen.view, null, 'Reset cancels pending navigation');
assert.equal(screen.opacity, 255, 'Reset restores full opacity');
assert.equal(screen._navigationFading, false);
assert.equal(transitions.length, 0, 'Reset never animates menu closure');
for (const option of ['enable_animations', 'reduced_motion', 'mapped', '_dragging', '_destroyed']) {
    settings.enable_animations = option !== 'enable_animations';
    settings.reduced_motion = option === 'reduced_motion';
    screen.mapped = option !== 'mapped';
    screen._dragging = option === '_dragging';
    screen._destroyed = option === '_destroyed';
    screen.navigate(`view-${option}`);
    assert.equal(transitions.length, 0, `${option}: suppress navigation animation`);
    assert.equal(screen.opacity, 255);
}
console.log('Aligned list cells, palette parity, and cancellable navigation fades passed');
