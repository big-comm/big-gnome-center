// SPDX-License-Identifier: GPL-2.0-or-later

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

export class ComponentHost {
    constructor(runtimeExtension, uuid, metadata = {}, codeDirectory = null) {
        this.uuid = uuid;
        this.path = GLib.build_filenamev([runtimeExtension.path, '..', uuid]);
        this.codePath = codeDirectory
            ? GLib.build_filenamev([runtimeExtension.path, codeDirectory])
            : this.path;
        this.dir = Gio.File.new_for_path(this.path);
        this.metadata = {uuid, ...metadata};
        this._stylesheets = [];
        this._schemaSource = null;
    }

    getSettings(schemaId) {
        if (!this._schemaSource) {
            const schemasPath = GLib.build_filenamev([this.path, 'schemas']);
            this._schemaSource = Gio.SettingsSchemaSource.new_from_directory(
                schemasPath,
                Gio.SettingsSchemaSource.get_default(),
                false,
            );
        }

        const schema = this._schemaSource.lookup(schemaId, true);
        if (!schema)
            throw new Error(`Missing schema ${schemaId} for ${this.uuid}`);
        return new Gio.Settings({settings_schema: schema});
    }

    loadStylesheet() {
        if (this._stylesheets.length)
            return;

        const file = this.dir.get_child('stylesheet.css');
        const theme = St.ThemeContext.get_for_stage(global.stage).get_theme();
        theme.load_stylesheet(file);
        this._stylesheets.push(file);
    }

    unloadStylesheet() {
        // Main.loadTheme() copies custom stylesheets into a new St.Theme.
        // Match GNOME Shell's ExtensionManager: unload the file from the
        // current theme, never from the stale theme that originally loaded it.
        const theme = St.ThemeContext.get_for_stage(global.stage).get_theme();
        for (const file of this._stylesheets.splice(0)) {
            try {
                theme.unload_stylesheet(file);
            } catch (error) {
                console.warn(`[layout-switcher-runtime] stylesheet unload failed: ${error}`);
            }
        }
    }
}
