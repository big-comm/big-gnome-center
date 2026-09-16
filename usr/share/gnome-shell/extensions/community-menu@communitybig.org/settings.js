// SPDX-License-Identifier: GPL-2.0-or-later
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export function createMenuSettings(id) {
    const cached = Gio.SettingsSchemaSource.get_default();
    let schema = cached?.lookup(id, true);
    if (!schema) {
        // The running Shell keeps its schema catalog across package upgrades.
        const directories = [
            GLib.getenv('GSETTINGS_SCHEMA_DIR'),
            ...GLib.get_system_data_dirs().map(dir => GLib.build_filenamev([dir, 'glib-2.0', 'schemas'])),
        ];
        for (const directory of directories.filter(Boolean)) {
            if (!GLib.file_test(GLib.build_filenamev([directory, 'gschemas.compiled']), GLib.FileTest.EXISTS))
                continue;
            const source = Gio.SettingsSchemaSource.new_from_directory(directory, cached, false);
            schema = source.lookup(id, false);
            if (schema)
                break;
        }
    }
    if (!schema)
        throw new Error(`Community Menu schema not installed: ${id}`);
    return new Gio.Settings({settings_schema: schema});
}
