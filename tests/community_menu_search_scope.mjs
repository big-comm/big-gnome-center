// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const path = '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/layouts/appGridLayout.js';
const source = fs.readFileSync(new URL(path, import.meta.url), 'utf8');
const method = source.slice(source.indexOf('    _syncSearchInterceptor('), source.indexOf('    _onKeyPress('));
const stage = {};
const Controller = vm.runInNewContext(`class Controller {${method}}; Controller`, {global: {stage}});
for (const mapped of [true, false]) {
    for (const searching of [true, false]) {
        for (const editing of [true, false]) {
            let assigned;
            const controller = new Controller();
            controller._deskUxApps = {hasNameEntry: editing};
            controller._searchEntry = {mapped, searchActive: searching,
                clutter_text: {set_input_interceptor: value => { assigned = value; }}};
            controller._syncSearchInterceptor();
            assert.equal(assigned, mapped && (searching || !editing) ? stage : null);
            controller._syncSearchInterceptor(!editing);
            assert.equal(assigned, mapped && (searching || editing) ? stage : null);
            controller._searchEntry.clutter_text = {};
            controller._syncSearchInterceptor();
        }
    }
}
console.log('Folder editor and search input scopes passed');

const widgets = fs.readFileSync(new URL(
    '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/widgets/deskUxApps.js', import.meta.url), 'utf8');
const selectionMethods = widgets.slice(widgets.indexOf('    _updateSave() {'), widgets.indexOf('    perform(operation) {'));
const Selection = vm.runInNewContext(`class Selection {${selectionMethods}}; Selection`);
const picker = new Selection();
picker.view = '@create';
picker.selecting = true;
picker._selected = new Set();
picker._nameEntry = {get_text: () => 'Test'};
picker._saveButton = {};
picker._selectionCount = {};
picker._updateSave();
assert.equal(picker._saveButton.reactive, false, 'Name alone cannot create an empty folder');
assert.equal(picker._selectionCount.text, '0 / 2');
const first = {app: {get_id: () => 'first.desktop'}, checked: true};
const second = {app: {get_id: () => 'second.desktop'}, checked: true};
picker.activateTile(first);
assert.equal(picker._saveButton.reactive, false, 'One app is insufficient');
assert.equal(picker._selectionCount.text, '1 / 2');
picker.activateTile(second);
assert.equal(picker._saveButton.reactive, true, 'Two distinct checked apps enable creation');
assert.equal(picker._selectionCount.text, '2 / 2');
assert.equal(first.checked && second.checked, true);
picker._nameEntry.get_text = () => '  ';
picker._updateSave();
assert.equal(picker._saveButton.reactive, false, 'An empty name disables creation');
picker._nameEntry.get_text = () => 'Test';
first.checked = false;
picker.activateTile(first);
assert.equal(picker._selectionCount.text, '1 / 2');
assert.equal(picker._saveButton.reactive, false, 'Deselection updates creation availability');
console.log('Creation selection, counter, name validation, and toggle synchronization passed');

const saveMethods = widgets.slice(widgets.indexOf('    _save() {'), widgets.indexOf('    perform(operation) {'));
let writable = true;
const Saving = vm.runInNewContext(`class Saving {${saveMethods}}; Saving`, {
    _: text => text, global: {settings: {is_writable: () => writable}},
});
const editor = new Saving();
editor._selected = new Set(['one.desktop']);
editor._saveButton = {};
editor._selectionCount = {};
editor.view = '@add';
editor._targetFolder = 'destination';
editor._updateSave();
assert(editor._saveButton.reactive, 'Adding to an existing folder only requires one selection');
let operation;
let destination;
editor.perform = value => { operation = value; return false; };
editor.navigate = value => { destination = value; };
editor._save();
assert.equal(operation.type, 'move');
assert.equal(operation.folder, 'destination');
assert.equal(destination, undefined, 'Failed writes keep the picker open');
editor.perform = () => 'destination';
editor._save();
assert.equal(destination, 'destination');
editor.view = '@pin';
writable = false;
editor._updateSave();
assert.equal(editor._saveButton.reactive, false, 'Locked favorites disable bulk pinning');
writable = true;
editor._selected.clear();
editor._updateSave();
assert.equal(editor._saveButton.reactive, false, 'Empty selections cannot be saved');
console.log('Bulk selection, failed-write preservation, and favorite locks passed');
