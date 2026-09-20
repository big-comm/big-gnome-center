// SPDX-License-Identifier: GPL-3.0-or-later
import Gio from 'gi://Gio';

export class WindowStyles {
    constructor(helperPath) {
        this._helperPath = helperPath;
        this._desired = null;
        this._applied = null;
        this._busy = false;
        this._revision = 0;
        this._process = null;
        this._failedProcess = null;
        this._waitRetry = null;
    }

    refresh(enabled, opacity = 37) {
        this._desired = JSON.stringify([enabled, enabled ? opacity : 37]);
        this._revision++;
        this._waitRetry?.();
        this._drain();
    }

    _drain() {
        if (this._busy || this._desired === this._applied)
            return;
        const request = this._desired;
        const revision = this._revision;
        const [enabled, opacity] = JSON.parse(request);
        const argv = ['/usr/bin/python3', this._helperPath];
        if (enabled)
            argv.push('--enable', '--opacity', `${opacity}`);
        this._busy = true;
        try {
            const process = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDERR_PIPE);
            this._process = process;
            process.communicate_utf8_async(null, null, (source, result) => {
                if (this._process !== source)
                    return;
                let success = false;
                try {
                    const [completed, , error] = source.communicate_utf8_finish(result);
                    if (!completed)
                        throw new Error('Incomplete helper communication');
                    success = completed && source.get_successful();
                    if (!success || error?.trim())
                        console.warn(`Frosted Glass window styles: ${error?.trim()}`);
                } catch (error) {
                    console.warn(`Frosted Glass window styles: ${error}`);
                    this._retireFailedProcess(source, request, revision);
                    return;
                }
                this._finish(source, request, revision, success);
            });
        } catch (error) {
            this._applied = null;
            console.warn(`Frosted Glass window styles: ${error}`);
            if (!this._process) {
                this._busy = false;
                return;
            }
            this._retireFailedProcess(this._process, request, revision);
        }
    }

    _retireFailedProcess(process, request, revision) {
        // Confirm exit before allowing another writer to start.
        this._applied = null;
        this._failedProcess = process;
        try {
            process.force_exit();
        } catch (error) {
            console.warn(`Frosted Glass window styles: ${error}`);
        }
        this._waitForFailedProcess(process, request, revision);
    }

    _waitForFailedProcess(process, request, revision) {
        this._waitRetry = null;
        const retry = error => {
            if (this._process !== process)
                return;
            console.warn(`Frosted Glass window styles: ${error}`);
            this._waitRetry = () => this._waitForFailedProcess(process, request, revision);
        };
        try {
            process.wait_async(null, (source, result) => {
                if (this._process !== source)
                    return;
                try {
                    source.wait_finish(result);
                    this._finish(source, request, revision, false);
                } catch (error) {
                    retry(error);
                }
            });
        } catch (error) {
            retry(error);
        }
    }

    _finish(process, request, revision, success) {
        if (this._process !== process)
            return;
        success &&= this._failedProcess !== process;
        this._busy = false;
        this._process = null;
        this._failedProcess = null;
        this._waitRetry = null;
        this._applied = success ? request : null;
        // Failed requests retry only after an explicit refresh, never in a loop.
        if (success || this._revision !== revision)
            this._drain();
    }

    destroy() {
        this.refresh(false);
    }
}
