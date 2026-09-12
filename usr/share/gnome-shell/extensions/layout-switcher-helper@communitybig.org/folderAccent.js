// SPDX-License-Identifier: MIT
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const ACCENTS = ['blue', 'teal', 'green', 'yellow', 'orange', 'red', 'pink', 'purple', 'slate', 'maia'];
export function folderBaseTheme(name) {
    const match = /^bgc-folders--(bigicons-papient(?:-dark|-light)?)--([a-z]+)--[0-9a-f]{16}$/.exec(name);
    return match && ACCENTS.includes(match[2]) ? match[1] : name;
}

export class FolderAccentFollower {
    constructor(settings, busy, reportError,
        script = '/usr/share/big-gnome-center/folder_accent.py') {
        this._settings = settings;
        this._busy = busy;
        this._reportError = reportError;
        this._script = script;
        this._state = {status: 'pending'};
        this._signals = ['accent-color', 'icon-theme'].map(key =>
            settings.connect(`changed::${key}`, () => this.queue()));
        this.queue();
    }

    diagnostics() {
        return {...this._state, pending: Boolean(this._source || this._process)};
    }

    queue() {
        if (!this._settings || this._source)
            return;
        this._source = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 200, () => {
            if (this._busy() || this._process)
                return GLib.SOURCE_CONTINUE;
            this._source = 0;
            this._sync();
            return GLib.SOURCE_REMOVE;
        });
    }

    _sync() {
        const settings = this._settings;
        const current = settings.get_string('icon-theme');
        const accent = settings.get_string('accent-color');
        const base = folderBaseTheme(current);
        if (!/^bigicons-papient(?:-dark|-light)?$/.test(base) || !ACCENTS.includes(accent)) {
            this._state = {status: 'unsupported', base, accent};
            return;
        }
        if (!settings.is_writable('icon-theme')) {
            this._state = {status: 'locked', base, accent};
            return;
        }
        try {
            const process = Gio.Subprocess.new([
                '/usr/bin/python3', this._script, '--theme', current, '--accent', accent,
            ], Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
            this._process = process;
            // Bound source-theme reads; never block the compositor thread.
            this._deadline = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 15, () => {
                this._deadline = 0;
                process.force_exit();
                return GLib.SOURCE_REMOVE;
            });
            process.communicate_utf8_async(null, null, (proc, result) => {
                try {
                    const [, stdout, stderr] = proc.communicate_utf8_finish(result);
                    if (!this._settings)
                        return;
                    if (!proc.get_successful())
                        throw new Error(stderr.trim() || 'Folder accent generation failed');
                    const state = JSON.parse(stdout);
                    if (this._busy() || settings.get_string('icon-theme') !== current ||
                        settings.get_string('accent-color') !== accent) {
                        this.queue();
                        return;
                    }
                    if (folderBaseTheme(state.theme) !== base)
                        throw new Error('Unexpected folder accent theme');
                    this._state = state;
                    if (state.theme !== current && !settings.set_string('icon-theme', state.theme))
                        throw new Error('Folder accent setting failed');
                } catch (error) {
                    if (this._settings)
                        this._failed(error);
                } finally {
                    if (this._deadline)
                        GLib.Source.remove(this._deadline);
                    this._deadline = 0;
                    this._process = null;
                }
            });
        } catch (error) {
            this._failed(error);
        }
    }

    _failed(error) {
        this._state = {status: 'error', error: String(error)};
        this._reportError(error);
    }

    destroy() {
        if (this._source)
            GLib.Source.remove(this._source);
        this._source = 0;
        if (this._deadline)
            GLib.Source.remove(this._deadline);
        this._deadline = 0;
        for (const id of this._signals)
            this._settings.disconnect(id);
        this._signals = [];
        this._settings = null;
        this._process?.force_exit();
    }
}
