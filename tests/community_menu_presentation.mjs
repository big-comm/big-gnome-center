// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {matchesQuery, folderTint, gridColumns, tileWidth, scrollEdge, SessionRecents} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/deskUxModel.js';

assert(matchesQuery('Multimídia', 'MULTIMIDIA'));
assert(matchesQuery('Développement', ' develop '));
assert(!matchesQuery('Games', 'music'));
for (const width of [1, 320, 640, 800, 1024, 1920]) {
    assert(gridColumns(width) >= 1 && gridColumns(width) <= 6);
    assert(gridColumns(width, true) >= 1 && gridColumns(width, true) <= 4);
}
assert.equal(gridColumns(720, true), 4);
assert.equal(tileWidth(920, 6), 108);
assert.equal(tileWidth(920, 4), 180);
assert.equal(gridColumns(840 - 64, true), 4);
assert.equal(tileWidth(840, 4), 160, 'Compact menu retains four narrower folder cards');
assert.equal(gridColumns(700 - 40, true), 4, 'Larger square folders retain four columns');
assert.equal(gridColumns(700 - 48 - 64), 5, 'Five compact pinned cards fit');
assert.equal(tileWidth(700, 4, 28, 124, 40), 124, 'Folder content fits three 35px icons and two 9px gaps');
assert(Math.abs((124 + 28) / 138 - 1.1) < 0.005, 'Folder size grows 10%, rounded to whole pixels');
assert.equal(gridColumns(638, true), 4);
assert.equal(gridColumns(637, true), 3, 'Constrained monitors must fit the larger cards');
assert.equal(tileWidth(652, 5, 18, 94), 91, 'Pinned squares fit the icon and a two-line label');
assert.equal(tileWidth(920, 4, 28, 124, 40), 124, 'Folder cards do not stretch into spare space');
assert(tileWidth(880, 6) < tileWidth(920, 6), 'Resize must update tiles even with unchanged columns');
assert.equal(folderTint('test-id'), folderTint('test-id'));
for (let i = 0; i < 100; i++)
    assert(folderTint(String(i)) >= 0 && folderTint(String(i)) < 6);
const recent = new SessionRecents();
for (let i = 0; i < 30; i++) recent.remember(String(i));
assert.equal(recent.ids.length, 24);
recent.remember('28');
assert.equal(recent.ids[0], '28');
assert.equal(new Set(recent.ids).size, 24);
assert.deepEqual(recent.visible([{id: '28'}, {id: '1'}]), [{id: '28'}]);
recent.clear();
assert.deepEqual(recent.ids, []);
console.log('Responsive grids, stable colors, search, and ephemeral recents passed');

const source = fs.readFileSync(new URL(
    '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/widgets/deskUxApps.js', import.meta.url), 'utf8');
const gridMethod = source.slice(source.indexOf('    _grid('), source.indexOf('    _dropArea('));
const viewMethods = source.slice(source.indexOf('    get selecting()'), source.indexOf('    _remember('));
const sizingMethod = source.slice(source.indexOf('    setLayoutWidth('), source.indexOf('    _appRecords('));
class TestGrid {
    constructor(columns, gap, rowGap) {
        this.columns = columns; this.styles = []; this.gap = gap; this.rowGap = rowGap;
    }
    add_style_class_name(style) { this.styles.push(style); }
}
const Presentation = vm.runInNewContext(`class Presentation {${sizingMethod}${viewMethods}${gridMethod}}; Presentation`,
    {Grid: TestGrid, tileWidth, gridColumns});
const ui = new Presentation();
let renders = 0;
ui.queueRender = () => renders++;
ui.setLayoutWidth(700);
assert.equal(ui._columns, 5);
assert.equal(ui._folderColumns, 4);
for (const allocation of [820, 652, 620, 570, 700]) {
    ui.width = allocation;
    ui.setLayoutWidth(700);
    assert.equal(ui._columns, 5, 'Child allocations cannot wrap the add tile');
    assert.equal(ui._folderColumns, 4, 'Child allocations cannot drop a folder column');
}
assert.equal(renders, 1, 'Stable menu width must not create render feedback');
ui.setLayoutWidth(480);
assert.equal(ui._columns, 3, 'Constrained monitors retain responsive fallback');
assert.equal(ui._folderColumns, 2);
ui.setLayoutWidth(700);
assert.equal(ui._columns, 5);
assert.equal(ui._folderColumns, 4);
ui._content = {add_child() {}};
for (const view of [null, '@create', '@add', '@pin', '@all', '@recent', 'folder-id']) {
    for (const list of [false, true]) {
        ui.view = view;
        ui._listMode = list;
        const grid = ui._grid([]);
        const horizontal = list && ['@all', '@recent', 'folder-id'].includes(view);
        assert.equal(grid._tileStyle.includes('height:'), !horizontal, `${view}: square unless list mode`);
        assert.equal(grid.styles.includes('desk-ux-compact-grid'), !horizontal);
        assert.equal(grid.columns, horizontal ? 1 : 5);
        if (!horizontal)
            assert.equal(grid._tileStyle, `width: ${grid._tileWidth}px; height: ${grid._tileWidth}px;`);
        const folders = ui._grid([], true);
        assert.equal(folders.gap, 10);
        assert.equal(folders.rowGap, folders.gap, 'Folder gaps match on both axes');
        assert.equal(grid.rowGap, grid.gap, 'App gaps match on both axes');
        assert.equal(folders.columns, 4);
        assert.equal(folders._tileWidth, 124);
        assert.equal(folders._tileStyle, `width: ${folders._tileWidth}px; height: ${folders._tileWidth}px;`);
    }
}
console.log('Square cards across every app grid; horizontal list rows preserved');

const layoutSource = fs.readFileSync(new URL(
    '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/layouts/appGridLayout.js', import.meta.url), 'utf8');
const heightStart = layoutSource.indexOf('    updateHeight()');
const heightEnd = layoutSource.indexOf('\n    }', heightStart) + 6;
for (const scale of [1, 2]) {
    let monitorWidth = 1280 * scale;
    const Layout = vm.runInNewContext(`class Layout {${layoutSource.slice(heightStart, heightEnd)}}; Layout`, {
        St: {ThemeContext: {get_for_stage: () => ({scale_factor: scale})}},
        global: {stage: {}},
        Main: {layoutManager: {getWorkAreaForMonitor: () => ({width: monitorWidth})}},
    });
    const layout = new Layout();
    layout._box = {set_style(style) { this.style = style; }};
    layout._deskUxApps = ui;
    layout._availableHeight = () => 760 * scale;
    layout.set_height = height => { layout.height = height; };
    layout.updateHeight();
    assert.equal(layout._box.style, 'width: 700px;');
    assert.equal(layout.height, 640 * scale);
    assert.equal(ui._layoutWidth, 700, 'Grid budget remains logical at every scale');
    assert.equal(ui._columns, 5);
    assert.equal(ui._folderColumns, 4);
    monitorWidth = 528 * scale;
    layout.updateHeight();
    assert.equal(ui._layoutWidth, 480, 'Only monitor constraints shrink the grid budget');
    assert.equal(ui._folderColumns, 2);
}
console.log('Fixed menu dimensions and grid budget at 1x/2x; constrained monitors supported');

const adjustment = {lower: 0, upper: 1000, page_size: 400, value: 0};
assert.equal(scrollEdge(-1, adjustment), 1);
assert.equal(scrollEdge(1, adjustment), 0);
assert.equal(scrollEdge(0, adjustment), 0);
assert.equal(scrollEdge(-1, {...adjustment, value: 200}), 0);
assert.equal(scrollEdge(1, {...adjustment, value: 600}), -1);
assert.equal(scrollEdge(-1, {...adjustment, value: 600}), 0);
assert.equal(scrollEdge(1, {...adjustment, upper: 400}), 0, 'No feedback for unscrollable content');

const feedbackMethods = source.slice(source.indexOf('    _resetScrollFeedback('), source.indexOf('    _render('));
const settings = {enable_animations: true, reduced_motion: false};
const Feedback = vm.runInNewContext(`class Feedback {${feedbackMethods}}; Feedback`, {
    St: {Settings: {get: () => settings}, ThemeContext: {get_for_stage: () => ({scale_factor: 2})}},
    global: {stage: {}}, Clutter: {AnimationMode: {EASE_OUT_QUAD: 1}},
});
const feedback = new Feedback();
const transitions = [];
feedback.mapped = true;
feedback._content = {
    ease(options) { transitions.push(options); },
    remove_transition(property) { assert.equal(property, 'translation-y'); },
};
feedback._pulseScrollEdge(1);
assert.equal(transitions[0].translation_y, 8, 'Feedback scales, while layout stays untouched');
feedback._pulseScrollEdge(1);
assert.equal(transitions.length, 1, 'Repeated edge input cannot stack animations');
transitions[0].onComplete();
assert.equal(transitions[1].translation_y, 0);
transitions[1].onComplete();
assert.equal(feedback._edgeAnimating, false);
settings.reduced_motion = true;
feedback._pulseScrollEdge(-1);
assert.equal(transitions.length, 2);
settings.reduced_motion = false;
settings.enable_animations = false;
feedback._pulseScrollEdge(-1);
assert.equal(transitions.length, 2);
settings.enable_animations = true;
feedback._dragging = true;
feedback._pulseScrollEdge(-1);
assert.equal(transitions.length, 2, 'Dragging never triggers feedback');
feedback._dragging = false;
feedback._pulseScrollEdge(-1);
feedback._resetScrollFeedback();
assert.equal(feedback._content.translation_y, 0);
assert.equal(feedback._edgeAnimating, false);
console.log('Subtle edge feedback: direction, range, scaling, reduced motion, and cleanup');

const scrollbarMethods = source.slice(source.indexOf('    notePointerMotion('),
    source.indexOf('    _resetScrollFeedback('));
const timers = new Map();
let nextTimer = 0;
let pointerButtons = 0;
const Scrollbars = vm.runInNewContext(`class Scrollbars {${scrollbarMethods}}; Scrollbars`, {
    GLib: {PRIORITY_DEFAULT: 0, SOURCE_CONTINUE: 1, SOURCE_REMOVE: 0,
        source_remove(id) { timers.delete(id); },
        timeout_add(_priority, delay, callback) {
            assert.equal(delay, 1000);
            timers.set(++nextTimer, callback);
            return nextTimer;
        }},
    St: {Settings: {get: () => settings}},
    global: {stage: {key_focus: null}, get_pointer: () => [0, 0, pointerButtons]},
    Clutter: {AnimationMode: {EASE_OUT_QUAD: 1, EASE_IN_OUT_QUAD: 2}, ModifierType: {BUTTON1_MASK: 256}},
});
const scrollbars = new Scrollbars();
const fades = [];
const bar = {opacity: 0, hover: false, contains: () => false,
    remove_transition(property) { assert.equal(property, 'opacity'); },
    ease(options) { fades.push(options); this.opacity = options.opacity; }};
scrollbars._scrollbars = [bar];
scrollbars.mapped = true;
scrollbars.notePointerMotion();
assert.equal(bar.opacity, 255);
assert.equal(fades[0].duration, 120);
scrollbars.notePointerMotion();
assert.equal(fades.length, 1, 'Pointer motion extends the timer without restarting the fade');
assert.equal(timers.size, 1);
bar.hover = true;
assert.equal(timers.get(scrollbars._scrollbarHideId)(), 1, 'Keep scrollbar available while hovered');
bar.hover = false;
const expiredTimer = scrollbars._scrollbarHideId;
assert.equal(timers.get(expiredTimer)(), 0);
timers.delete(expiredTimer);
assert.equal(bar.opacity, 0);
assert.equal(fades[1].duration, 2000);
assert.equal(fades[1].mode, 2);
assert.equal(scrollbars._scrollbarHideId, 0);
scrollbars._scrollbarPressed = true;
pointerButtons = 256;
scrollbars.notePointerMotion();
for (let tick = 0; tick < 5; tick++)
    assert.equal(timers.get(scrollbars._scrollbarHideId)(), 1, 'Hold without motion or hover must remain visible');
assert.equal(bar.opacity, 255);
scrollbars._scrollbarDragging = true;
pointerButtons = 0;
assert.equal(timers.get(scrollbars._scrollbarHideId)(), 1, 'Native drag keeps visibility even without pointer-button state');
scrollbars._scrollbarDragging = false;
const releasedTimer = scrollbars._scrollbarHideId;
assert.equal(timers.get(releasedTimer)(), 0, 'Release outside the menu must not leave visibility stuck');
timers.delete(releasedTimer);
assert.equal(scrollbars._scrollbarPressed, false);
assert.equal(fades.at(-1).duration, 2000);
settings.reduced_motion = true;
scrollbars.notePointerMotion();
assert.equal(fades.at(-1).duration, 0, 'Reduced motion disables scrollbar fades');
settings.reduced_motion = false;
scrollbars._resetScrollbarVisibility();
assert.equal(bar.opacity, 0);
assert.equal(scrollbars._scrollbarPressed, false);
assert.equal(scrollbars._scrollbarDragging, false);
assert.equal(timers.size, 0, 'Closing cancels the idle timer');
scrollbars.mapped = false;
scrollbars.notePointerMotion();
assert.equal(timers.size, 0);
console.log('Pointer-triggered scrollbar fades, idle delay, accessibility, and teardown passed');

const widgetsSource = fs.readFileSync(new URL(
    '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/widgets/widgets.js', import.meta.url), 'utf8');
const sharedGrid = widgetsSource.slice(widgetsSource.indexOf('    _init(column_count'),
    widgetsSource.indexOf('\n});', widgetsSource.indexOf('export const Grid')));
class Actor {
    constructor(params = {}) { Object.assign(this, params); }
    _init(params) { Object.assign(this, params); }
    get_n_children() { return this.layout_manager.items.length; }
    get_text_direction() { return this.rtl ? 1 : 0; }
    remove_all_children() { this.layout_manager.items = []; }
}
class LayoutManager {
    constructor(params) { Object.assign(this, params); this.items = []; }
    hookup_style() {}
    attach(actor, column, row) { this.items.push({actor, column, row}); }
    get_child_at(column, row) { return this.items.find(item => item.column === column && item.row === row)?.actor; }
}
const SharedGrid = vm.runInNewContext(`class SharedGrid extends Actor {${sharedGrid}}; SharedGrid`, {
    Actor, St: {Widget: Actor}, Clutter: {GridLayout: LayoutManager, Orientation: {VERTICAL: 1},
        ActorAlign: {FILL: 'fill', CENTER: 'center'}, TextDirection: {RTL: 1}},
});
for (const rtl of [false, true]) {
    const grid = new SharedGrid();
    grid._init(4, 10, 10);
    grid.rtl = rtl;
    assert.equal(grid.x_align, 'center', 'Spare width stays outside the grid');
    assert.equal(grid.layout_manager.column_spacing, 10);
    assert.equal(grid.layout_manager.row_spacing, 10);
    const tiles = Array.from({length: 8}, () => new Actor());
    tiles.forEach(tile => grid.add_item(tile));
    assert.equal(grid.get_n_children(), tiles.length, 'No flexible gap columns');
    tiles.forEach((tile, index) => {
        const column = rtl ? 3 - index % 4 : index % 4;
        assert.equal(grid.layout_manager.get_child_at(column, Math.floor(index / 4)), tile);
    });
    assert.equal(grid.get_first_item(), tiles[0], 'RTL focus starts at the first tile');
    grid.clear();
    grid.add_item(tiles[0]);
    assert.equal(grid.get_first_item(), tiles[0], 'Clear resets placement');
}
console.log('Uniform grid gaps, RTL focus, and clearing passed');
