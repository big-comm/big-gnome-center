// SPDX-License-Identifier: GPL-3.0-or-later
// Optional native corners. Never load an unchecked binary into GNOME Shell.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GIRepository from 'gi://GIRepository';
import Shell from 'gi://Shell';

let roundedBackend = null;
let pending = null;

export async function prepareRoundedBackend() {
    pending ??= probeRoundedBackend();
    await pending;
}

async function probeRoundedBackend() {
    let process;
    let timeout = 0;
    try {
        const repository = GIRepository.Repository.dup_default();
        const launcher = new Gio.SubprocessLauncher({
            flags: Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE,
        });
        for (const [variable, paths] of [
            ['GI_TYPELIB_PATH', repository.get_search_path()],
            ['LD_LIBRARY_PATH', repository.get_library_path()],
        ]) {
            const inherited = GLib.getenv(variable);
            const value = [...paths, ...(inherited ? [inherited] : [])].filter(Boolean).join(':');
            if (value)
                launcher.setenv(variable, value, true);
        }
        launcher.setenv('LD_BIND_NOW', '1', true);
        const version = JSON.stringify(repository.get_version('Shell'));
        process = launcher.spawnv(['gjs', '-c',
            `imports.gi.versions.Shell = ${version}; void imports.gi.Shell; ` +
            'void imports.gi.Blur.BlurEffect.$gtype;']);
        timeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 3000, () => {
            timeout = 0;
            process.force_exit();
            return GLib.SOURCE_REMOVE;
        });
        await new Promise((resolve, reject) => {
            process.wait_check_async(null, (child, result) => {
                try {
                    child.wait_check_finish(result);
                    resolve();
                } catch (error) {
                    reject(error);
                }
            });
        });
        roundedBackend = (await import('gi://Blur')).default;
    } catch (error) {
        console.warn(`Frosted Glass: optional rounded blur unavailable; using Shell.BlurEffect: ${error}`);
    } finally {
        if (timeout)
            GLib.source_remove(timeout);
    }
}

export function createBackgroundEffect() {
    return roundedBackend
        ? new roundedBackend.BlurEffect({mode: roundedBackend.BlurMode.BACKGROUND})
        : new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND});
}
