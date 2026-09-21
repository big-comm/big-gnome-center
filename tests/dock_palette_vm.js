// Run only inside a disposable GNOME Shell session.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GdkPixbuf from 'gi://GdkPixbuf';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Config from 'resource:///org/gnome/shell/misc/config.js';

const pause = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    resolve(); return GLib.SOURCE_REMOVE;
}));
const check = (condition, message) => { if (!condition) throw new Error(message); };

export default class extends Extension {
    enable() {
        this.run().catch(error => this.finish({passed: false, error: `${error}`, stack: error.stack}));
    }
    async run() {
        await pause(1500);
        const path = GLib.getenv('BGC_RUNTIME_DIRECTORY');
        const {DockRuntime} = await import(`file://${path}/dockRuntime.js`);
        const {DockSurfaceManager} = await import(`file://${path}/dockSurface.js`);
        const {profileForLayout} = await import(`file://${path}/layoutProfiles.js`);
        const {paletteFixtures, checkPalette} = await import(GLib.getenv('BGC_PALETTE_FIXTURES'));
        const system = Shell.AppSystem.get_default();
        const apps = system.get_installed().map(info => system.lookup_app(info.get_id()))
            .filter(Boolean).sort((a, b) => a.get_id().localeCompare(b.get_id()));
        global.settings.set_strv('favorite-apps', apps.slice(0, 20).map(app => app.get_id()));
        this.dock = new DockRuntime({path});
        this.dock.activate(profileForLayout('BigGnome'), 'dot', 'default', 40, 70,
            65, 48, 'always-visible', 'left', false);
        const manager = DockSurfaceManager.getDefault();
        const iconActors = () => manager.mainDock.dash._box.get_children()
            .map(item => item.child).filter(actor => actor?._indicator);
        for (let i = 0; i < 100 && iconActors().length < 10; i++) await pause(30);
        check(iconActors().length >= 10, 'too few real dock actors');
        const indicator = iconActors()[0]._indicator._indicators
            .find(item => item._dominantColorExtractor);
        check(indicator, 'native dock extractor unavailable');
        const Extractor = indicator._dominantColorExtractor.constructor;
        let sequence = 0;
        const extract = pixbuf => {
            const instance = new Extractor({get_id: () => `palette-probe-${++sequence}`});
            instance._getIconPixBuf = () => pixbuf;
            return instance._getColorPalette();
        };
        const fixtures = paletteFixtures();
        for (const fixture of fixtures) {
            const pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(new GLib.Bytes(fixture.pixels),
                GdkPixbuf.Colorspace.RGB, fixture.channels === 4, 8,
                fixture.width, fixture.height, fixture.rowstride);
            checkPalette(extract(pixbuf), fixture.expected, fixture.name);
        }
        const directory = GLib.getenv('BGC_PROBE_DIRECTORY');
        const files = [];
        for (const [extension, alpha] of [['png', false], ['png', true], ['jpeg', false]]) {
            const pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, alpha, 8, 3, 7);
            pixbuf.fill(0x00ff00ff);
            const file = `${directory}/fixture-${alpha}.${extension}`;
            pixbuf.savev(file, extension, [], []);
            files.push(file);
        }
        const svg = `${directory}/fixture.svg`;
        GLib.file_set_contents(svg, '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="192"><rect width="256" height="192" fill="#00ff00"/></svg>');
        files.push(svg);
        const textures = [];
        for (const file of files) {
            const app = {get_id: () => file, create_icon_texture: () => {
                const icon = new St.Icon({gicon: new Gio.FileIcon({file: Gio.File.new_for_path(file)})});
                textures.push(icon); return icon;
            }};
            const palette = new Extractor(app)._getColorPalette();
            if (file.endsWith('.jpeg')) {
                checkPalette(palette, palette?.original, file);
                const rgb = palette.original.slice(1).match(/../g).map(value => parseInt(value, 16));
                check(rgb.every((v, i) => Math.abs(v - [80, 230, 80][i]) <= 2), 'JPEG drift');
            } else checkPalette(palette, '#50e650', file);
        }
        for (const icon of textures) icon.destroy();

        const details = [];
        const skipped = [];
        for (const app of apps) {
            const instance = new Extractor(app);
            const pixbuf = instance._getIconPixBuf();
            if (!pixbuf) { skipped.push(app.get_id()); continue; }
            const width = pixbuf.get_width(), height = pixbuf.get_height();
            const pixels = pixbuf.get_pixels(), channels = pixbuf.get_n_channels();
            const stride = pixbuf.get_rowstride(), rgba = new Uint8Array(width * height * 4);
            for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
                const offset = y * stride + x * channels;
                rgba.set([pixels[offset], pixels[offset + 1], pixels[offset + 2],
                    pixbuf.get_has_alpha() ? pixels[offset + 3] : 255], (y * width + x) * 4);
            }
            const canonical = GdkPixbuf.Pixbuf.new_from_bytes(new GLib.Bytes(rgba),
                GdkPixbuf.Colorspace.RGB, true, 8, width, height, width * 4);
            const palette = instance._getColorPalette();
            check(JSON.stringify(palette) === JSON.stringify(extract(canonical)), `layout mismatch: ${app.get_id()}`);
            checkPalette(palette, palette?.original ?? null, app.get_id());
            details.push({app: app.get_id(), width, height, channels, stride, palette});
            if (details.length === 40) break;
        }
        check(details.length >= 20, 'too few installed icon samples');

        // Exercise the actual backlight consumer, including its transparent fallback.
        const original = indicator._dominantColorExtractor;
        try {
            for (const [fill, expected] of [[0x00ff00ff, '#50e650'], [0xff000000, '#e0e0e0']]) {
                const pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, true, 8, 3, 7);
                pixbuf.fill(fill);
                indicator._dominantColorExtractor = {_getColorPalette: () => extract(pixbuf)};
                indicator._enableBacklight();
                check(indicator._source._iconContainer.get_style().includes(expected), 'backlight fallback/color');
            }
        } finally {
            indicator._dominantColorExtractor = original;
            indicator._disableBacklight();
        }
        const settings = manager.settings;
        settings.set_boolean('apply-custom-theme', false);
        settings.set_boolean('running-indicator-dominant-color', true);
        for (let i = 0; i < 6; i++) {
            settings.set_boolean('unity-backlit-items', Boolean(i % 2));
            const style = ['dot', 'hybrid', 'desk-ux'][i % 3];
            this.dock._applyIndicator(style);
            await pause(100);
            check(this.dock.diagnostics().indicator === style, 'indicator style did not apply');
            for (const actor of iconActors()) {
                actor._indicator.update();
                const running = actor._indicator._indicators.find(item => item._dominantColorExtractor);
                const palette = running?._dominantColorExtractor._getColorPalette();
                checkPalette(palette, palette?.original ?? null, actor.app.get_id());
            }
        }
        this.dock.deactivate(); this.dock = null;
        check(!DockSurfaceManager.getDefault(), 'dock manager retained');
        await pause(300);
        this.finish({passed: true, gnome: Config.PACKAGE_VERSION, fixtures: fixtures.length,
            fileIcons: files.length, installedIcons: details.length, skipped,
            backlightCases: 2, styleCycles: 6, details});
    }
    finish(result) {
        if (this.finishing) return;
        this.finishing = true;
        this.dock?.deactivate();
        GLib.file_set_contents(GLib.getenv('BGC_PROBE_RESULT'), JSON.stringify(result));
        global.context.terminate();
    }
    disable() {}
}
