// Modified by Community Big, 2026-07-10: renamed, de-Zorinized, and adapted for GNOME Shell 50.
/*
 * Zorin Menu: The official applications menu for Zorin OS.
 *
 * Copyright (C) 2016-2021 Zorin OS Technologies Ltd.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

// Import Libraries
import Gio from 'gi://Gio';
import GMenu from 'gi://GMenu';
import Shell from 'gi://Shell';
import {gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';
import {EventEmitter} from 'resource:///org/gnome/shell/misc/signals.js';
import * as ParentalControlsManager from 'resource:///org/gnome/shell/misc/parentalControlsManager.js';

export const AppsBackend = class extends EventEmitter {
    constructor() {
        super();

        this._appSys = Shell.AppSystem.get_default();
        this._parentalControlsManager = ParentalControlsManager.getDefault();

        this._categories = [];
        this._appsByCategory = {};

        this.reloading = false;
        this._reload();

        this._parentalControlsManager.connectObject('app-filter-changed', this._reload.bind(this), this);
        this._appSys.connectObject('installed-changed', this._reload.bind(this), this);
    }

    allAppsCategory() {
        return {
            get_name: () => _('All Apps'),
            get_menu_id: () => 'all_apps',
            get_icon: () => Gio.icon_new_for_string('view-app-grid-symbolic'),
        };
    }

    frequentAppsCategory() {
        return {
            get_name: () => _('Frequent Apps'),
            get_menu_id: () => 'frequent_apps',
            get_icon: () => Gio.icon_new_for_string('starred-symbolic'),
        };
    }

    recentFilesCategory() {
        return {
            get_name: () => _('Recent Files'),
            get_menu_id: () => 'recent_files',
            get_icon: () => Gio.icon_new_for_string('document-open-recent-symbolic'),
        };
    }

    // Load data for a single menu category
    _loadCategory(categoryId, dir, appsByCategory) {
        let iter = dir.iter();
        let nextType;
        while ((nextType = iter.next()) != GMenu.TreeItemType.INVALID) {
            if (nextType == GMenu.TreeItemType.ENTRY) {
                let entry = iter.get_entry();
                let id;
                try {
                    id = entry.get_desktop_file_id();
                } catch(e) {
                    continue;
                }
                let app = this._appSys.lookup_app(id);
                if (app && app.get_app_info().should_show() && (this._parentalControlsManager.shouldShowApp(app.app_info)))
                    appsByCategory[categoryId].push(app);
            } else if (nextType == GMenu.TreeItemType.DIRECTORY) {
                let subdir = iter.get_directory();
                if (!subdir.get_is_nodisplay())
                    this._loadCategory(categoryId, subdir, appsByCategory);
            }
        }
    }

    // Load data for all menu categories
    _load() {
        const tree = new GMenu.Tree({ menu_basename: 'applications.menu', flags: GMenu.TreeFlags.SORT_DISPLAY_NAME });
        tree.load_sync();
        const categories = [];
        const appsByCategory = {};

        let root = tree.get_root_directory();
        let iter = root.iter();
        let nextType;
        while ((nextType = iter.next()) != GMenu.TreeItemType.INVALID) {
            if (nextType == GMenu.TreeItemType.DIRECTORY) {
                let dir = iter.get_directory();
                if (!dir.get_is_nodisplay()) {
                    let categoryId = dir.get_menu_id();
                    appsByCategory[categoryId] = [];
                    this._loadCategory(categoryId, dir, appsByCategory);
                    if (appsByCategory[categoryId].length > 0) {
                        categories.push(dir);
                    }
                }
            }
        }
        tree.connectObject('changed', this._reload.bind(this), this);
        this._menuTree?.disconnectObject(this);
        this._menuTree = tree;
        this._categories = categories;
        this._appsByCategory = appsByCategory;
    }

    // Reload data for all menu categories
    _reload() {
        if (this.reloading || !this._appSys) {
            return
        }
        this.reloading = true;

        try {
            this._load();
        } catch (error) {
            console.warn(`Community Menu: failed to reload apps: ${error}`);
            return;
        } finally {
            this.reloading = false;
        }
        this.emit('reload');
    }

    // Return a list of all apps (unsorted)
    _allApps() {
        let appsMap = new Map();

        for (const info of this._appSys.get_installed()) {
            const app = this._appSys.lookup_app(info.get_id());
            if (app && info.should_show() && this._parentalControlsManager.shouldShowApp(info))
                appsMap.set(app.get_id(), app);
        }

        // Get all apps, deduplicated by app ID
        for (let directory in this._appsByCategory) {
            for (let app of this._appsByCategory[directory]) {
                const info = app.get_app_info();
                if (info?.should_show() && this._parentalControlsManager.shouldShowApp(info))
                    appsMap.set(app.get_id(), app);
            }
        }
        return [...appsMap.values()];
    }

    // Sort apps alphabetically by name
    _sortApps(apps) {
        if (!apps)
            return [];

        return apps.sort((a, b) =>
            a.get_name().toLowerCase().localeCompare(b.get_name().toLowerCase())
        );
    }

    // Return a list of all apps (sorted)
    getAllApps() {
        let apps = this._allApps();
        return this._sortApps(apps);
    }

    getFrequentlyUsedApps() {
        const installedApps = new Map(
            this._allApps().map(app => [app.get_id(), app]));
        const usage = Shell.AppUsage.get_default();

        try {
            const frequentApps = usage.get_most_used()
                .filter(app => installedApps.has(app.get_id()));
            return frequentApps.length > 0
                ? frequentApps
                : this.getAllApps();
        } catch (error) {
            console.warn(`Community Menu: failed to load frequent apps: ${error}`);
            return this.getAllApps();
        }
    }

    // Return a list of apps for a category (sorted)
    getAppsByCategory(category_menu_id) {
        if (category_menu_id == "all_apps") {
            return this.getAllApps();
        }

        if (category_menu_id == "frequent_apps") {
            return this.getFrequentlyUsedApps();
        }

        if (category_menu_id) {
            let apps = (this._appsByCategory[category_menu_id] ?? []).slice();
            return this._sortApps(apps);
        }

        return [];
    }

    // Return a list of all categories
    getCategories() {
        return this._categories.slice();
    }

    // Destroy the Apps Backend object
    destroy() {
        this._appSys?.disconnectObject(this);
        this._appSys = null;

        this._parentalControlsManager?.disconnectObject(this);
        this._parentalControlsManager = null;

        this._menuTree?.disconnectObject(this);
        this._menuTree = null;

        this._categories = null;
        this._appsByCategory = null;

        this.reloading = null;

        this.emit('destroy');
    }
};
