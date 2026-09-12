// SPDX-License-Identifier: GPL-2.0-or-later
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {editFolders, validFolderId} from './folderModel.js';

const KEYS = {name: 'name', translate: 'translate', apps: 'apps',
    categories: 'categories', excluded: 'excluded-apps'};

export class AppFolders {
    constructor(changed, appProvider, settingsFactory = null) {
        this._changed = changed;
        this._appProvider = appProvider;
        this._factory = settingsFactory ?? (id => new Gio.Settings(id === null
            ? {schema_id: 'org.gnome.desktop.app-folders'}
            : {schema_id: 'org.gnome.desktop.app-folders.folder',
                path: `/org/gnome/desktop/app-folders/folders/${id}/`}));
        this._root = this._factory(null);
        this._folders = new Map();
        this._rootSignal = this._root.connect('changed::folder-children', () => this._queue());
        this._sync();
    }

    _queue() {
        if (this._idle)
            return;
        this._idle = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._idle = 0;
            this._sync();
            this._changed();
            return GLib.SOURCE_REMOVE;
        });
    }

    _sync() {
        const ids = this._root.get_strv('folder-children').filter(validFolderId);
        for (const [id, entry] of this._folders) {
            if (!ids.includes(id)) {
                entry.settings.disconnect(entry.signal);
                this._folders.delete(id);
            }
        }
        for (const id of ids) {
            if (!this._folders.has(id)) {
                const settings = this._factory(id);
                this._folders.set(id, {settings,
                    signal: settings.connect('changed', () => this._queue())});
            }
        }
    }

    snapshot() {
        this._sync();
        return [...new Set(this._root.get_strv('folder-children'))]
            .filter(id => this._folders.has(id)).map(id => {
                const settings = this._folders.get(id).settings;
                return Object.fromEntries([['id', id], ...Object.entries(KEYS)
                    .map(([field, key]) => [field, settings.get_value(key).deep_unpack()])]);
            });
    }

    edit(operation) {
        if (operation.type === 'create')
            operation = {...operation, folder: GLib.uuid_string_random()};
        const before = this.snapshot();
        const after = editFolders(before, this._appProvider(), operation);
        const changes = [];
        for (const folder of after) {
            const old = before.find(f => f.id === folder.id);
            const settings = this._folders.get(folder.id)?.settings ?? this._factory(folder.id);
            for (const [field, key] of Object.entries(KEYS)) {
                if (old && JSON.stringify(old[field]) === JSON.stringify(folder[field]))
                    continue;
                const previous = settings.get_user_value(key);
                changes.push({settings, key, previous,
                    value: new GLib.Variant(field === 'translate' ? 'b' : field === 'name' ? 's' : 'as', folder[field])});
            }
        }
        const children = this._root.get_strv('folder-children');
        // Preserve unknown IDs rather than rewriting unrelated settings.
        const removed = before.filter(f => !after.some(a => a.id === f.id)).map(f => f.id);
        const added = after.filter(f => !before.some(b => b.id === f.id)).map(f => f.id);
        const updated = [...children.filter(id => !removed.includes(id)), ...added];
        if (JSON.stringify(children) !== JSON.stringify(updated))
            changes.push({settings: this._root, key: 'folder-children',
                previous: this._root.get_user_value('folder-children'), value: new GLib.Variant('as', updated)});
        // Preflight every affected key before writing any of them.
        if (changes.some(({settings, key}) => !settings.is_writable(key)))
            throw new Error('Application folders are locked by system policy');
        const written = [];
        try {
            for (const change of changes) {
                if (!change.settings.set_value(change.key, change.value))
                    throw new Error('Could not save application folders');
                written.push(change);
            }
        } catch (error) {
            for (const {settings, key, previous} of written.reverse()) {
                if (previous === null)
                    settings.reset(key);
                else
                    settings.set_value(key, previous);
            }
            throw error;
        }
        // Retain detached settings as recovery data; GNOME ignores unlisted IDs.
        this._queue();
        return operation.folder;
    }

    destroy() {
        if (this._idle)
            GLib.source_remove(this._idle);
        this._idle = 0;
        this._root.disconnect(this._rootSignal);
        for (const {settings, signal} of this._folders.values())
            settings.disconnect(signal);
        this._folders.clear();
        this._changed = null;
    }
}
