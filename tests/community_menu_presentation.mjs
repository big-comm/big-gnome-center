// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {matchesQuery, folderTint, gridColumns, tileWidth, SessionRecents} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/deskUxModel.js';

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
assert.equal(gridColumns(700 - 48 - 64, true), 4, 'Square folders retain four columns');
assert.equal(gridColumns(700 - 48 - 64), 5, 'Five compact pinned cards fit');
assert.equal(tileWidth(652, 4, 26, 112), 112, 'Folder content fits three 32px icons and two 8px gaps');
assert.equal(tileWidth(652, 5, 18, 94), 91, 'Pinned squares fit the icon and a two-line label');
assert.equal(tileWidth(920, 4, 26, 112), 112, 'Folder cards do not stretch into spare space');
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
class TestGrid {
    constructor(columns) { this.columns = columns; this.styles = []; }
    add_style_class_name(style) { this.styles.push(style); }
}
const Presentation = vm.runInNewContext(`class Presentation {${viewMethods}${gridMethod}}; Presentation`,
    {Grid: TestGrid, tileWidth});
const ui = new Presentation();
ui._layoutWidth = 700;
ui._columns = 5;
ui._folderColumns = 4;
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
        assert.equal(folders.columns, 4);
        assert.equal(folders._tileStyle, `width: ${folders._tileWidth}px; height: ${folders._tileWidth}px;`);
    }
}
console.log('Square cards across every app grid; horizontal list rows preserved');
