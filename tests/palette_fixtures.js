// Shared Node/GJS fixtures. Last rows deliberately omit trailing padding.
export function paletteFixtures() {
    const fixtures = [];
    const green = [0, 255, 0, 255];
    const blue = [0, 0, 255, 255];
    function add(name, width, height, channels, padding, pixel, expected) {
        const rowstride = width * channels + padding;
        const pixels = new Uint8Array((height - 1) * rowstride + width * channels);
        pixels.fill(253);
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const rgba = pixel(x, y);
                pixels.set(rgba.slice(0, channels), y * rowstride + x * channels);
            }
        }
        fixtures.push({name, width, height, channels, rowstride, pixels, expected});
    }
    for (const channels of [3, 4]) {
        for (const [width, height] of [[1, 1], [3, 5], [127, 7], [128, 128],
            [129, 131], [255, 257], [256, 192], [1025, 3]]) {
            for (const padding of [0, 13]) {
                add(`${channels} channels ${width}x${height} padding ${padding}`,
                    width, height, channels, padding, () => green, '#50e650');
            }
        }
        // Correct two-dimensional sampling sees green. Linear skipping sees blue.
        for (const [width, height, stepX, stepY] of [[256, 192, 4, 3], [5, 192, 1, 3], [192, 5, 3, 1]]) {
            add(`spatial sampling ${channels} channels ${width}x${height}`,
                width, height, channels, 7,
                (x, y) => x % stepX === 0 && y % stepY === 0 ? green : blue,
                '#50e650');
        }
    }
    add('transparent colored pixels ignored', 21, 9, 4, 11,
        (x, y) => x === 0 && y === 0 ? green : [255, 0, 255, 0], '#50e650');
    add('fully transparent fallback', 3, 5, 4, 12, () => [255, 0, 255, 0], null);
    add('transparent black fallback', 129, 131, 4, 4, () => [0, 0, 0, 0], null);
    add('opaque black remains valid', 3, 5, 3, 4, () => [0, 0, 0, 255], '#e6e6e6');
    add('opaque gray remains valid', 2, 2, 4, 5, () => [128, 128, 128, 255], '#e6e6e6');
    add('equal red and green', 2, 1, 3, 0,
        x => x ? [255, 0, 0, 255] : green, '#e6e650');
    add('alpha weights gray contribution', 2, 1, 4, 0,
        x => x ? [255, 255, 255, 1] : [220, 255, 220, 255], '#c6e6c6');
    return fixtures;
}

export function checkPalette(palette, expected, name) {
    if (expected === null) {
        if (palette !== null) throw new Error(`${name}: expected theme fallback`);
        return;
    }
    if (!palette || palette.original !== expected)
        throw new Error(`${name}: expected ${expected}, got ${JSON.stringify(palette)}`);
    for (const key of ['lighter', 'original', 'darker']) {
        if (!/^#[0-9a-f]{6}$/.test(palette[key]))
            throw new Error(`${name}: invalid ${key}: ${palette[key]}`);
    }
}
