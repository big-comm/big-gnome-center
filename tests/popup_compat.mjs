import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const file = new URL('../usr/share/gnome-shell/extensions/community-menu@communitybig.org/utils.js', import.meta.url);
const source = fs.readFileSync(file, 'utf8').split('Gio._promisify')[0]
    .replace(/^import .*;\n/gm, '').replaceAll('export ', '');
for (const version of ['50.4', '51.rc', '51.0']) {
    const convert = vm.runInNewContext(source + '\npopupAnimationParams;', {
        Config: {PACKAGE_VERSION: version}, PopupAnimation: {NONE: 0, FADE: 1, FULL: 3},
    });
    assert.equal(convert(undefined), undefined);
    const options = {animate: false, triggerEvent: {}};
    assert.equal(convert(options), options, 'Preserve new API options');
    for (const mode of [0, 1, 3]) {
        const result = convert(mode);
        if (version.startsWith('50')) {
            assert.equal(result, mode);
        } else {
            assert.equal(result.animate, mode !== 0);
            assert.equal(result.fadeOnly, mode === 1);
        }
    }
}
console.log('GNOME 50/51 popup animation semantics preserved');
