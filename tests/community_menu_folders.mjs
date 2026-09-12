// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import {editFolders, folderMembers, validFolderId} from '../usr/share/gnome-shell/extensions/community-menu@communitybig.org/folderModel.js';

const apps = [
    {id: 'a.desktop', categories: ['Utility']},
    {id: 'b.desktop', categories: ['Utility']},
    {id: 'c.desktop', categories: ['Office']},
];
const folder = (id, extra = {}) => ({id, name: id, translate: true, apps: [], categories: [], excluded: [], ...extra});
const category = folder('Utility', {categories: ['Utility']});
const source = [category, folder('Office', {apps: ['c.desktop']})];
const original = JSON.stringify(source);
let result = editFolders(source, apps, {type: 'create', folder: 'new', name: ' Projects ', apps: ['a.desktop', 'c.desktop']});
assert.equal(JSON.stringify(source), original);
assert.equal(result.length, 2);
assert.deepEqual(result[0].excluded, ['a.desktop']);
assert.deepEqual(folderMembers(result[0], apps).map(a => a.id), ['b.desktop']);
assert.equal(result[1].name, 'Projects');
assert.equal(result[1].translate, false);
assert.deepEqual(result[1].apps, ['a.desktop', 'c.desktop']);

result = editFolders(result, apps, {type: 'move', folder: 'new', apps: ['b.desktop']});
assert.equal(result.length, 1, 'Remove the source only after its last effective app leaves');
assert.deepEqual(result[0].apps, ['a.desktop', 'c.desktop', 'b.desktop']);
result = editFolders(result, apps, {type: 'ungroup', apps: ['a.desktop', 'b.desktop']});
assert.equal(result.length, 1, 'Keep single-app folders');
assert.deepEqual(result[0].apps, ['c.desktop']);
assert.deepEqual(editFolders(result, apps, {type: 'ungroup', apps: ['c.desktop']}), []);

const renamed = editFolders(source, apps, {type: 'rename', folder: 'Utility', name: 'Tools'});
assert.equal(renamed[0].name, 'Tools');
assert.equal(renamed[0].translate, false);
assert.deepEqual(editFolders(source, apps, {type: 'dissolve', folder: 'Utility'}), [source[1]]);
const excluded = folder('excluded', {apps: ['a.desktop'], categories: ['Utility'], excluded: ['a.desktop']});
assert.deepEqual(folderMembers(excluded, apps).map(a => a.id), ['b.desktop']);
assert.deepEqual(editFolders([excluded], apps, {type: 'move', folder: 'excluded', apps: ['a.desktop']})[0].excluded, []);

const hidden = folder('hidden', {apps: ['uninstalled.desktop', 'a.desktop']});
assert.deepEqual(editFolders([hidden], apps, {type: 'ungroup', apps: ['a.desktop']})[0].apps, ['uninstalled.desktop']);
assert.equal(folderMembers(hidden, []).length, 0);
assert.deepEqual(hidden.apps, ['uninstalled.desktop', 'a.desktop'], 'Display filtering does not rewrite folders');
assert.equal(editFolders([folder('empty'), category], apps, {type: 'ungroup', apps: ['c.desktop']}).length, 2);

for (const operation of [
    {type: 'create', folder: 'new', name: 'X', apps: ['a.desktop']},
    {type: 'create', folder: 'new', name: 'X', apps: ['a.desktop', 'a.desktop']},
    {type: 'create', folder: 'Utility', name: 'X', apps: ['a.desktop', 'b.desktop']},
    {type: 'create', folder: '../bad', name: 'X', apps: ['a.desktop', 'b.desktop']},
    {type: 'create', folder: 'new', name: ' ', apps: ['a.desktop', 'b.desktop']},
    {type: 'move', folder: 'missing', apps: ['a.desktop']},
    {type: 'ungroup', apps: ['missing.desktop']},
    {type: 'rename', folder: 'Utility', name: 'x'.repeat(121)},
    {type: 'dissolve', folder: 'missing'},
    {type: 'bad'},
]) {
    assert.throws(() => editFolders(source, apps, operation));
    assert.equal(JSON.stringify(source), original);
}
for (const id of ['', '/bad', 'bad/name', '..\n', null])
    assert.equal(validFolderId(id), false);
assert.equal(validFolderId('gnome-tools_1.directory'), true);
console.log('Folder membership, create, move, ungroup, rename, dissolve, and preservation passed');
