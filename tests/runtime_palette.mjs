import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {paletteFixtures, checkPalette} from './palette_fixtures.js';

const root = process.env.BGC_RUNTIME_DIRECTORY;
const file = root ? `${root}/taskbar/utils.js`
    : new URL('../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/taskbar/utils.js', import.meta.url);
const source = fs.readFileSync(file, 'utf8');
const start = source.indexOf('let colorNs =');
const end = source.indexOf('export const drawRoundedLine');
assert(start >= 0 && end > start);
const {DominantColorExtractor} = vm.runInNewContext(
    source.slice(start, end).replace(/^export /gm, '') + '\n;({DominantColorExtractor})',
    {Clutter: {}, Cogl: {}});
let passed = 0, failed = 0;
function run(name, test) {
    try { test(); passed++; console.log(`PASS ${name}`); }
    catch (error) { failed++; console.error(`FAIL ${name}: ${error.message}`); }
}
for (const fixture of paletteFixtures()) {
    run(fixture.name, () => {
        const {width, height, channels, rowstride, pixels} = fixture;
        const reads = [];
        const guarded = new Proxy(pixels, {
            get(target, key) {
                if (/^\d+$/.test(String(key))) {
                    const index = Number(key);
                    assert(index < target.length, `read past last row: ${index}`);
                    assert(index % rowstride < width * channels, `read padding: ${index}`);
                    reads.push(index);
                }
                return Reflect.get(target, key, target);
            },
        });
        const extractor = new DominantColorExtractor({get_id: () => fixture.name});
        extractor._getIconPixBuf = () => ({
            get_pixels: () => guarded, get_width: () => width, get_height: () => height,
            get_n_channels: () => channels, get_rowstride: () => rowstride,
            get_has_alpha: () => channels === 4,
        });
        const palette = extractor._getColorPalette();
        checkPalette(palette, fixture.expected, fixture.name);
        assert(reads.length > 0);
        assert(reads.length <= 127 * 127 * channels, 'large icon sampling not bounded');
        if (palette) {
            extractor._getIconPixBuf = () => { throw new Error('cache missed'); };
            assert.strictEqual(extractor._getColorPalette(), palette);
        }
    });
}
run('missing icon fallback', () => {
    const extractor = new DominantColorExtractor({get_id: () => 'missing'});
    extractor._getIconPixBuf = () => null;
    assert.equal(extractor._getColorPalette(), null);
});
console.log(`${passed} passed, ${failed} failed`);
if (failed) process.exitCode = 1;
