// SPDX-License-Identifier: MIT
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export function resolveGtkTheme(current, scheme, exists) {
    if (!current || current.includes('/') || current === '.' || current === '..')
        return current;
    if (!['default', 'prefer-light', 'prefer-dark'].includes(scheme))
        return current;
    const dark = scheme === 'prefer-dark';
    const base = current.replace(/-(dark|light)$/, '');
    if (!base || (dark && current.endsWith('-dark')) ||
        (!dark && !current.endsWith('-dark')))
        return current;
    const candidates = dark ? [`${base}-dark`] : [base, `${base}-light`];
    return candidates.find(name => exists(name)) ?? current;
}

export function gtkThemeExists(name) {
    if (!name || name.includes('/') || name === '.' || name === '..')
        return false;
    const roots = [
        GLib.build_filenamev([GLib.get_user_data_dir(), 'themes']),
        GLib.build_filenamev([GLib.get_home_dir(), '.themes']),
        ...GLib.get_system_data_dirs().map(dir => GLib.build_filenamev([dir, 'themes'])),
        GLib.build_filenamev([GLib.getenv('GTK_DATA_PREFIX') || '/usr', 'share', 'themes']),
    ];
    for (const root of new Set(roots)) {
        // GTK3 searches compatible even minor versions, down to gtk-3.0.
        for (let minor = 24; minor >= 0; minor -= 2) {
            const css = Gio.File.new_for_path(GLib.build_filenamev([
                root, name, `gtk-3.${minor}`, 'gtk.css',
            ]));
            if (css.query_file_type(Gio.FileQueryInfoFlags.NONE, null) === Gio.FileType.REGULAR)
                return true;
        }
    }
    return false;
}

export class GtkThemeFollower {
    constructor(settings, busy, reportError) {
        this._settings = settings;
        this._busy = busy;
        this._reportError = reportError;
        this._signals = ['color-scheme', 'gtk-theme'].map(key =>
            settings.connect(`changed::${key}`, () => this.queue()));
        this.queue();
    }

    queue() {
        if (this._source || !this._settings)
            return;
        this._source = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 150, () => {
            // A layout's dconf load may still be in progress.
            if (this._busy())
                return GLib.SOURCE_CONTINUE;
            try {
                this.sync();
            } catch (error) {
                this._reportError(error);
            }
            this._source = 0;
            return GLib.SOURCE_REMOVE;
        });
    }

    sync() {
        if (!this._settings?.is_writable('gtk-theme'))
            return;
        const current = this._settings.get_string('gtk-theme');
        const target = resolveGtkTheme(
            current, this._settings.get_string('color-scheme'), gtkThemeExists);
        if (target !== current && !this._settings.set_string('gtk-theme', target))
            throw new Error('GTK3 theme update failed');
    }

    destroy() {
        if (this._source)
            GLib.Source.remove(this._source);
        this._source = 0;
        for (const id of this._signals)
            this._settings.disconnect(id);
        this._signals = [];
        this._settings = null;
    }
}
