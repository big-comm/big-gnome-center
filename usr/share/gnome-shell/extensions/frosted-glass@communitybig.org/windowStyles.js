// SPDX-License-Identifier: GPL-3.0-or-later
import Gio from 'gi://Gio';

export class WindowStyles {
    constructor(helperPath) {
        this._helperPath = helperPath;
        this._desired = null;
        this._applied = null;
        this._busy = false;
    }

    refresh(enabled, opacity = 37) {
        this._desired = JSON.stringify([enabled, enabled ? opacity : 37]);
        this._drain();
    }

    _drain() {
        if (this._busy || this._desired === this._applied)
            return;
        const request = this._desired;
        const [enabled, opacity] = JSON.parse(request);
        const argv = ['/usr/bin/python3', this._helperPath];
        if (enabled)
            argv.push('--enable', '--opacity', `${opacity}`);
        this._busy = true;
        try {
            const process = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDERR_PIPE);
            process.communicate_utf8_async(null, null, (source, result) => {
                try {
                    const [, , error] = source.communicate_utf8_finish(result);
                    if (!source.get_successful() || error?.trim())
                        console.warn(`Frosted Glass window styles: ${error?.trim()}`);
                } catch (error) {
                    console.warn(`Frosted Glass window styles: ${error}`);
                }
                this._busy = false;
                this._applied = request;
                // Never let an older enable finish after a newer disable.
                this._drain();
            });
        } catch (error) {
            this._busy = false;
            this._applied = request;
            console.warn(`Frosted Glass window styles: ${error}`);
        }
    }

    destroy() {
        this.refresh(false);
    }
}
