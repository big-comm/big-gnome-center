// Run only in a disposable GNOME 51 Shell; verify captures with rounded_corner_pixels.py.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Cogl from 'gi://Cogl';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const pause = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    resolve(); return GLib.SOURCE_REMOVE;
}));

export default class extends Extension {
    enable() {
        this.run().catch(error => this.finish({passed: false, error: `${error}`, stack: error.stack}));
    }
    async capture(name) {
        await pause(300);
        const file = `${GLib.getenv('BGC_PROBE_DIRECTORY')}/${name}.png`;
        const stream = Gio.File.new_for_path(file).replace(null, false, Gio.FileCreateFlags.NONE, null);
        const shot = new Shell.Screenshot();
        try {
            await new Promise((resolve, reject) => shot.screenshot_area(100, 100, 720, 440, stream, (s, r) => {
                try { s.screenshot_area_finish(r); resolve(); } catch (error) { reject(error); }
            }));
        } finally { stream.close(null); }
    }
    async run() {
        await pause(1500);
        const path = GLib.getenv('BGC_FROSTED_DIRECTORY');
        const {RoundedCornersEffect} = await import(`file://${path}/roundedCorners.js`);
        const source = Shell.get_file_contents_utf8_sync(`${path}/roundedCorners.glsl`);
        const old = source.replace('color.a * coverage', 'min(coverage, color.a)');
        const start = old.indexOf('void main(void)');
        const Legacy = GObject.registerClass({GTypeName: 'BGCTestLegacyCorners'}, class extends RoundedCornersEffect {
            vfunc_get_static_snippet() {
                const snippet = Cogl.Snippet.new(Cogl.SnippetHook.FRAGMENT, old.slice(0, start), null);
                snippet.set_replace(old.slice(old.indexOf('{', start) + 1, old.lastIndexOf('}')));
                return snippet;
            }
        });
        this.board = new St.Widget({x: 100, y: 100, width: 720, height: 440});
        Main.uiGroup.add_child(this.board);
        const cases = [];
        const tiles = [];
        const colors = [[255, 0, 0], [0, 255, 0], [0, 90, 255], [220, 70, 180]];
        const radii = [0, 8, 20, 100];
        for (const [row, alpha] of [0, .1, .5, .9, 1].entries()) {
            for (let col = 0; col < 4; col++) {
                const item = {x: 8 + col * 180, y: 8 + row * 86, width: 72, height: 72,
                    alpha, color: colors[col], radius: radii[col]};
                cases.push(item);
                for (let version = 0; version < 2; version++) {
                    const actor = new St.Widget({x: item.x + version * 84, y: item.y, width: 72, height: 72});
                    this.board.add_child(actor);
                    actor.add_effect_with_name('corners', version ? new Legacy(item.radius) : new RoundedCornersEffect(item.radius));
                    tiles.push({actor, item});
                }
            }
        }
        const context = St.ThemeContext.get_for_stage(global.stage);
        this.context = context; this.originalScale = context.scale_factor;
        for (const scale of [1, 2]) {
            context.scale_factor = scale;
            for (const background of [255, 40]) {
                this.board.set_style(`background-color: rgb(${background}, ${background}, ${background});`);
                for (const opaque of [true, false]) {
                    for (const {actor, item} of tiles)
                        actor.set_style(`background-color: rgba(${item.color.join(',')}, ${opaque ? 1 : item.alpha});`);
                    await this.capture(`scale-${scale}-bg-${background}-${opaque ? 'opaque' : 'alpha'}`);
                }
            }
        }
        this.board.destroy(); this.board = null;
        context.scale_factor = this.originalScale;
        const {ShellBlurSurface} = await import(`file://${path}/shellBlurSurface.js`);
        let popupCycles = 0;
        for (const [kind, menu] of [['quick-settings', Main.panel.statusArea.quickSettings.menu],
            ['calendar', Main.panel.statusArea.dateMenu.menu]]) {
            this.menu = menu;
            for (const mode of ['static', 'dynamic', 'static', 'dynamic']) {
                menu.open(false);
                await pause(300);
                const target = menu.box;
                if (!target.mapped) throw new Error(`${kind} did not open`);
                const style = target.get_style();
                const surface = this.surface = new ShellBlurSurface(target, {kind, cornerRadius: 24});
                surface.update({enabled: true, mode, radius: 25, brightness: .9,
                    tintOpacity: .35, lightMode: false});
                await pause(200);
                if (!surface._overlay?.visible || (mode === 'static' && !surface._cornerEffect))
                    throw new Error(`${kind}/${mode} missing blur or mask`);
                menu.close(false);
                await pause(150);
                if (surface._overlay?.visible) throw new Error(`${kind} left visible blur`);
                surface.destroy(); this.surface = null;
                if (target.get_style() !== style) throw new Error(`${kind} style not restored`);
                popupCycles++;
            }
        }
        this.menu = null;
        this.finish({passed: true, cases, scales: [1, 2], backgrounds: [255, 40], popupCycles});
    }
    finish(result) {
        if (this.finished) return;
        this.finished = true;
        this.surface?.destroy();
        this.menu?.close(false);
        this.board?.destroy();
        if (this.context) this.context.scale_factor = this.originalScale;
        GLib.file_set_contents(GLib.getenv('BGC_PROBE_RESULT'), JSON.stringify(result));
        global.context.terminate();
    }
    disable() {}
}
