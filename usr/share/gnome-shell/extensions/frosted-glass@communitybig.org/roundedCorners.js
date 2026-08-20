// SPDX-License-Identifier: GPL-3.0-or-later
// Adapted from Blur My Shell's CornerEffect and yilozt/rounded-window-corners.

import Clutter from 'gi://Clutter';
import Cogl from 'gi://Cogl';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Shell from 'gi://Shell';
import St from 'gi://St';

function shaderSource() {
    const uri = GLib.uri_resolve_relative(
        import.meta.url, 'roundedCorners.glsl', GLib.UriFlags.NONE);
    const [path] = GLib.filename_from_uri(uri);
    return Shell.get_file_contents_utf8_sync(path);
}

function shaderParts() {
    const source = shaderSource();
    const mainIndex = source.search(/void\s+main\s*\([^)]*\)\s*\{/);
    const braceIndex = source.indexOf('{', mainIndex);
    let depth = 0;
    for (let index = braceIndex; index < source.length; index++) {
        if (source[index] === '{')
            depth++;
        else if (source[index] === '}') {
            depth--;
            if (depth === 0) {
                return {
                    declarations: source.slice(0, mainIndex).trim(),
                    body: source.slice(braceIndex + 1, index).trim(),
                };
            }
        }
    }
    throw new Error('Invalid rounded-corner shader source');
}

export const RoundedCornersEffect = GObject.registerClass({
    GTypeName: 'CommunityBigRoundedCornersEffect',
}, class RoundedCornersEffect extends Clutter.ShaderEffect {
    constructor(radius = 0) {
        super();
        this._radius = radius;
        this._sizeId = 0;
        St.ThemeContext.get_for_stage(global.stage).connectObject(
            'notify::scale-factor', () => this._updateUniforms(), this);
    }

    vfunc_get_static_snippet() {
        const {declarations, body} = shaderParts();
        const snippet = Cogl.Snippet.new(
            Cogl.SnippetHook.FRAGMENT,
            declarations,
            null
        );
        snippet.set_replace(body);
        return snippet;
    }

    set radius(value) {
        this._radius = Math.max(0, value);
        this._updateUniforms();
    }

    get radius() {
        return this._radius;
    }

    vfunc_set_actor(actor) {
        const previous = this.get_actor();
        if (previous && this._sizeId) {
            previous.disconnect(this._sizeId);
            this._sizeId = 0;
        }

        super.vfunc_set_actor(actor);
        if (actor) {
            this._sizeId = actor.connect('notify::size',
                () => this._updateUniforms());
            this._updateUniforms();
        }
    }

    _updateUniforms() {
        const actor = this.get_actor();
        if (!actor)
            return;
        const width = Math.max(1, actor.width);
        const height = Math.max(1, actor.height);
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const radius = Math.min(
            this._radius * scale, width / 2, height / 2);
        this.set_uniform_value('width', parseFloat(width + 3 - 1e-6));
        this.set_uniform_value('height', parseFloat(height + 3 - 1e-6));
        this.set_uniform_value('radius', parseFloat(radius - 1e-6));
    }
});
