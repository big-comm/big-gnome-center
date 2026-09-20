// Run through a supervisor with private D-Bus, XDG directories and dconf.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import System from 'system';

const mode = ARGV[0];
const directory = GLib.getenv('BGC_STRESS_DIRECTORY');
if (!directory || !GLib.get_user_config_dir().startsWith(`${directory}/`))
    throw new Error('Private configuration directory required');
const loop = GLib.MainLoop.new(null, false);
const make = () => new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
const key = 'enable-animations';
const limit = Number(GLib.getenv('BGC_STRESS_ROUNDS') ?? 1000);
if (mode === 'writer') {
    const settings = make();
    let value = false;
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 15, () => {
        loop.quit(); return GLib.SOURCE_REMOVE;
    });
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 5, () => {
        settings.set_boolean(key, value = !value);
        return GLib.SOURCE_CONTINUE;
    });
    loop.run();
} else {
    const [, stat] = GLib.file_get_contents('/proc/self/stat');
    GLib.file_set_contents(`${directory}/pid`, new TextDecoder().decode(stat).split(' ')[0]);
    const writer = Gio.Subprocess.new(['gjs', '-m', System.programPath, 'writer'],
        Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE);
    const pool = new Map();
    let rounds = 0, created = 0, maxPool = 0, connected = 0;
    const values = new Set();
    const rss = [];
    const start = GLib.get_monotonic_time();
    const step = () => {
        for (let i = 0; i < 20; i++) {
            const id = mode === 'evict' ? (rounds * 20 + i) % 64 : i;
            const reuse = ['reuse', 'release', 'evict'].includes(mode);
            let settings = reuse ? pool.get(id) : null;
            if (!settings) {
                settings = make(); created++;
                if (reuse) {
                    if (mode === 'evict' && pool.size === 32)
                        pool.delete(pool.keys().next().value);
                    pool.set(id, settings);
                    maxPool = Math.max(maxPool, pool.size);
                }
            }
            const signal = settings.connect(`changed::${key}`, () => {});
            connected++;
            values.add(settings.get_boolean(key));
            settings.disconnect(signal); connected--;
            if (mode === 'dispose') settings.run_dispose();
        }
        rounds++;
        if (mode === 'release' && rounds % 100 === 0) pool.clear();
        if (rounds % 10 === 0) System.gc();
        if (rounds % 100 === 0) {
            const [, bytes] = GLib.file_get_contents('/proc/self/status');
            const memory = new TextDecoder().decode(bytes).match(/VmRSS:\s+(\d+)/);
            rss.push(Number(memory[1]));
            print(JSON.stringify({rounds, created, pool: pool.size, rssKiB: rss.at(-1)}));
        }
        if (rounds < limit) return GLib.SOURCE_CONTINUE;
        loop.quit(); return GLib.SOURCE_REMOVE;
    };
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1, step);
    loop.run();
    writer.send_signal(15); writer.wait(null);
    const result = {completed: true, mode, rounds, created, maxPool, connected,
        observedValues: values.size, rssKiB: rss,
        seconds: (GLib.get_monotonic_time() - start) / 1e6};
    GLib.file_set_contents(`${directory}/result.json`, JSON.stringify(result));
    print(JSON.stringify(result));
}
