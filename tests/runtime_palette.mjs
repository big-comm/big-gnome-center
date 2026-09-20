import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {paletteFixtures, checkPalette} from './palette_fixtures.js';

const root = process.env.BGC_RUNTIME_DIRECTORY;
const implementation = process.argv[2] ?? 'taskbar';
assert(['taskbar', 'dock'].includes(implementation));
const read = name => fs.readFileSync(root ? `${root}/${name}`
    : new URL(`../usr/share/gnome-shell/extensions/layout-switcher-runtime@communitybig.org/${name}`, import.meta.url), 'utf8');
let code, context;
if (implementation === 'dock') {
    const utilities = read('dock/utils.js');
    const start = utilities.indexOf('export class ColorUtils');
    const end = utilities.indexOf('export class InjectionsHandler');
    assert(start >= 0 && end > start);
    const {ColorUtils} = vm.runInNewContext(utilities.slice(start, end)
        .replace(/^export /gm, '') + '\n;({ColorUtils})');
    const source = read('dock/appIconIndicators.js');
    assert(source.includes('const iconCacheMap'));
    code = source.slice(source.indexOf('const iconCacheMap'));
    context = {Utils: {ColorUtils}};
} else {
    const source = read('taskbar/utils.js');
    const start = source.indexOf('let colorNs =');
    const end = source.indexOf('export const drawRoundedLine');
    assert(start >= 0 && end > start);
    code = source.slice(start, end).replace(/^export /gm, '');
    context = {Clutter: {}, Cogl: {}};
}
const {DominantColorExtractor, iconCacheMap} = vm.runInNewContext(
    code + '\n;({DominantColorExtractor, iconCacheMap})', context);
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
const pixel = (channels = 4, padding = 0, alpha = 255) => ({
    get_pixels: () => new Uint8Array(channels === 4 ? [0, 255, 0, alpha] : [0, 255, 0]),
    get_width: () => 1, get_height: () => 1,
    get_n_channels: () => channels, get_rowstride: () => channels + padding,
    get_has_alpha: () => channels === 4,
});
run('transparent fallback permits a later visible icon', () => {
    const extractor = new DominantColorExtractor({get_id: () => 'transparent-retry'});
    extractor._getIconPixBuf = () => pixel(4, 0, 0);
    assert.equal(extractor._getColorPalette(), null);
    extractor._getIconPixBuf = () => pixel();
    checkPalette(extractor._getColorPalette(), '#50e650', 'visible retry');
});
run('missing icon permits a later successful decode', () => {
    const extractor = new DominantColorExtractor({get_id: () => 'missing-retry'});
    extractor._getIconPixBuf = () => null;
    assert.equal(extractor._getColorPalette(), null);
    extractor._getIconPixBuf = () => pixel(3);
    checkPalette(extractor._getColorPalette(), '#50e650', 'missing retry');
});
run('cache shares successful palettes and evicts oldest entries in bounded batches', () => {
    iconCacheMap.clear();
    for (let i = 0; i < 1100; i++) {
        const extractor = new DominantColorExtractor({get_id: () => `cache-${i}`});
        extractor._getIconPixBuf = () => pixel();
        checkPalette(extractor._getColorPalette(), '#50e650', `cache-${i}`);
        assert(iconCacheMap.size <= 1000);
    }
    assert(!iconCacheMap.has('cache-0'));
    assert(iconCacheMap.has('cache-1099'));
    const extractor = new DominantColorExtractor({get_id: () => 'cache-1099'});
    extractor._getIconPixBuf = () => { throw new Error('shared cache missed'); };
    assert.strictEqual(extractor._getColorPalette(), iconCacheMap.get('cache-1099'));
    iconCacheMap.clear();
});
console.log(`${passed} passed, ${failed} failed`);
if (failed) process.exitCode = 1;
