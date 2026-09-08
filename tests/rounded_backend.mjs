import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const file = new URL('../usr/share/gnome-shell/extensions/frosted-glass@communitybig.org/roundedBackend.js', import.meta.url);
const source = fs.readFileSync(file, 'utf8')
    .replace(/^import .*;\n/gm, '').replaceAll('export ', '')
    .replace("await import('gi://Blur')", 'await loadBlur()');
for (const outcome of ['ok', 'failed', 'timeout', 'missing-tool']) {
    let imports = 0;
    let spawns = 0;
    let callback;
    let killed = false;
    const environment = new Map();
    const process = {
        wait_check_async(_cancel, done) {
            callback = () => done(this, {});
            if (outcome !== 'timeout') queueMicrotask(callback);
        },
        wait_check_finish() {
            if (outcome !== 'ok') throw Error(outcome);
        },
        force_exit() { killed = true; queueMicrotask(callback); },
    };
    const api = vm.runInNewContext(source + '\n({prepareRoundedBackend, createBackgroundEffect});', {
        console: {warn() {}},
        GIRepository: {Repository: {dup_default: () => ({
            get_version: () => '51',
            get_search_path: () => ['/typelib'],
            get_library_path: () => ['/library'],
        })}},
        GLib: {
            getenv: () => null, PRIORITY_DEFAULT: 0, SOURCE_REMOVE: false,
            timeout_add(_priority, delay, expire) {
                assert.equal(delay, 3000);
                if (outcome === 'timeout') queueMicrotask(expire);
                return 42;
            },
            source_remove(id) { assert.equal(id, 42); },
        },
        Gio: {
            SubprocessFlags: {STDOUT_SILENCE: 1, STDERR_SILENCE: 2},
            SubprocessLauncher: class {
                setenv(name, value) { environment.set(name, value); }
                spawnv(argv) {
                    spawns++;
                    assert.equal(argv[0], 'gjs');
                    assert.match(argv[2], /versions.Shell = "51"/);
                    if (outcome === 'missing-tool') throw Error('gjs unavailable');
                    return process;
                }
            },
        },
        Shell: {BlurEffect: class {kind = 'shell';}, BlurMode: {BACKGROUND: 1}},
        loadBlur: async () => {
            imports++;
            assert.equal(outcome, 'ok', 'Never import a rejected library into Shell');
            return {default: {BlurEffect: class {kind = 'rounded';}, BlurMode: {BACKGROUND: 1}}};
        },
    });
    await Promise.all([api.prepareRoundedBackend(), api.prepareRoundedBackend()]);
    assert.equal(spawns, 1, 'Coalesce concurrent enables');
    assert.equal(imports, outcome === 'ok' ? 1 : 0);
    assert.equal(api.createBackgroundEffect().kind, outcome === 'ok' ? 'rounded' : 'shell');
    assert.equal(environment.get('LD_BIND_NOW'), '1');
    assert.equal(environment.get('GI_TYPELIB_PATH'), '/typelib');
    assert.equal(environment.get('LD_LIBRARY_PATH'), '/library');
    assert.equal(killed, outcome === 'timeout');
}
console.log('Rounded library ABI rejection, timeout, success and native fallback passed');
