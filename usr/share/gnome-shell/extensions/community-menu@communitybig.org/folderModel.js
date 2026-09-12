// SPDX-License-Identifier: GPL-2.0-or-later
// Pure folder operations. Never mutate the caller's snapshot.

export function containsApp(folder, app) {
    return !folder.excluded.includes(app.id) &&
        (folder.apps.includes(app.id) || app.categories.some(c => folder.categories.includes(c)));
}

export function folderMembers(folder, apps) {
    return apps.filter(app => containsApp(folder, app));
}

export function validFolderId(id) {
    return typeof id === 'string' && id !== '.' && id !== '..' && /^[A-Za-z0-9_.-]+$/.test(id);
}

function nameValue(name) {
    const value = String(name).trim();
    if (!value || value.length > 120)
        throw new Error('Invalid folder name');
    return value;
}

export function editFolders(folders, apps, operation) {
    const next = folders.map(folder => ({...folder, apps: [...folder.apps],
        categories: [...folder.categories], excluded: [...folder.excluded]}));
    const find = id => {
        const folder = next.find(f => f.id === id);
        if (!folder)
            throw new Error('Folder no longer exists');
        return folder;
    };
    if (operation.type === 'rename') {
        Object.assign(find(operation.folder), {name: nameValue(operation.name), translate: false});
        return next;
    }
    if (operation.type === 'dissolve') {
        find(operation.folder);
        return next.filter(f => f.id !== operation.folder);
    }
    if (!['create', 'move', 'ungroup'].includes(operation.type))
        throw new Error('Unknown folder operation');
    const ids = [...new Set(operation.apps)];
    const selected = ids.map(id => apps.find(app => app.id === id));
    if (!ids.length || selected.some(app => !app))
        throw new Error('Application no longer exists');
    let target = null;
    if (operation.type === 'create') {
        if (ids.length < 2 || !validFolderId(operation.folder) || next.some(f => f.id === operation.folder))
            throw new Error('A new folder requires two applications and a unique ID');
        target = {id: operation.folder, name: nameValue(operation.name), translate: false,
            apps: [], categories: [], excluded: []};
        next.push(target);
    } else if (operation.type === 'move') {
        target = find(operation.folder);
    }
    const emptied = new Set();
    for (const folder of next) {
        if (folder === target) {
            folder.apps = [...new Set([...folder.apps, ...ids])];
            folder.excluded = folder.excluded.filter(id => !ids.includes(id));
            continue;
        }
        let changed = false;
        for (const app of selected) {
            if (!containsApp(folder, app))
                continue;
            changed = true;
            folder.apps = folder.apps.filter(id => id !== app.id);
            if (app.categories.some(c => folder.categories.includes(c)))
                folder.excluded = [...new Set([...folder.excluded, app.id])];
        }
        // Hidden/uninstalled explicit entries remain intact. Only explicit edits
        // can delete a folder; filtering or installed-changed must never do so.
        if (changed && !folder.apps.length && !folderMembers(folder, apps).length)
            emptied.add(folder.id);
    }
    return next.filter(folder => !emptied.has(folder.id));
}
