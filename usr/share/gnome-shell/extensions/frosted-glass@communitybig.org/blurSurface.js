// SPDX-License-Identifier: GPL-3.0-or-later

import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Background from 'resource:///org/gnome/shell/ui/background.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {attachBlurRepaint} from './blurPaintSignal.js';
import {RoundedCornersEffect} from './roundedCorners.js';

const EFFECT_NAME = 'communitybig-frosted-glass';
const CORNER_EFFECT_NAME = 'communitybig-frosted-glass-corners';

function transformedPosition(actor) {
    try {
        const [x, y] = actor.get_transformed_position();
        return [Math.round(x), Math.round(y)];
    } catch (error) {
        return [actor.x ?? 0, actor.y ?? 0];
    }
}

export class BlurSurface {
    constructor(actor, options = {}) {
        this.actor = actor;
        this._container = options.container ?? actor;
        this._kind = options.kind ?? 'surface';
        this._contentOpacity = options.contentOpacity ?? false;
        this._styleClass = options.styleClass ?? null;
        this._geometryProvider = options.geometryProvider ?? null;
        this._cornerRadius = options.cornerRadius ?? 0;
        this._maskCorners = options.maskCorners ?? true;
        this._background = null;
        this._host = null;
        this._effect = null;
        this._cornerEffect = null;
        this._tint = null;
        this._manager = null;
        this._mode = null;
        this._destroyId = 0;
        this._geometryIds = [];
        this._originalOpacity = new Map();
        this._destroyed = false;

        this._destroyId = this.actor.connect('destroy', () => {
            this._disconnectGeometry();
            this._destroyManager();
            this._removeBackground();
            this._destroyed = true;
            this._background = null;
            this._host = null;
            this._manager = null;
            this._effect = null;
            this._cornerEffect = null;
            this._tint = null;
        });
    }

    update(config) {
        if (this._destroyed)
            return;
        if (!this._hasUsableSize())
            return;

        const monitor = Main.layoutManager.findMonitorForActor(this.actor) ??
            Main.layoutManager.primaryMonitor;
        const monitorChanged = config.mode === 'static' && this._background &&
            monitor && this._monitorIndex !== monitor.index;
        if (!this._background || this._mode !== config.mode || monitorChanged)
            this._rebuild(config.mode);

        if (!this._background)
            return;

        this._syncRootGeometry();

        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        this._effect.radius = Math.max(0, Math.round(config.radius * scale));
        this._effect.brightness = config.brightness;
        if (this._cornerEffect)
            this._cornerEffect.radius = this._cornerRadius;
        const material = this._tint ?? this._background;
        material.set_style([
            `background-color: rgba(24, 25, 31, ${config.tintOpacity.toFixed(3)})`,
            this._cornerRadius > 0
                ? `border-radius: ${this._cornerRadius}px`
                : '',
            this._cornerRadius > 0
                ? 'border: 1px solid rgba(255, 255, 255, 0.16)'
                : '',
        ].filter(Boolean).join('; ') + ';');

        if (this._contentOpacity)
            this._setContentOpacity(config.opacity);

        if (this._mode === 'static')
            this._syncStaticGeometry();
    }

    setOpaque(opaque) {
        if (!this._contentOpacity || this._destroyed)
            return;
        if (opaque)
            this._setContentOpacity(255);
    }

    destroy() {
        if (this._destroyed)
            return;

        this._restoreContentOpacity();
        this._disconnectGeometry();
        this._destroyManager();
        if (this._styleClass &&
            typeof this.actor.remove_style_class_name === 'function')
            this.actor.remove_style_class_name(this._styleClass);
        this._removeBackground();
        if (this._destroyId) {
            try {
                this.actor.disconnect(this._destroyId);
            } catch (error) {
                // Actor may already be disposed.
            }
        }
        this._destroyed = true;
        this.actor = null;
        this._background = null;
        this._host = null;
        this._effect = null;
        this._cornerEffect = null;
        this._tint = null;
    }

    _rebuild(mode) {
        this._disconnectGeometry();
        this._destroyManager();
        this._removeBackground();
        this._mode = mode;
        this._background = new St.Widget({
            name: `frosted-glass-${this._kind}`,
            reactive: false,
            x_expand: true,
            y_expand: true,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.FILL,
            clip_to_allocation: true,
        });
        if (this._geometryProvider) {
            this._syncRootGeometry();
        } else {
            this._background.set_size(this.actor.width, this.actor.height);
            this._background.add_constraint(new Clutter.BindConstraint({
                source: this.actor,
                coordinate: Clutter.BindCoordinate.SIZE,
            }));
        }

        try {
            if (this._container === this.actor) {
                this._container.insert_child_at_index(this._background, 0);
            } else {
                this._host = new Meta.BackgroundGroup({
                    name: `frosted-glass-${this._kind}-host`,
                    reactive: false,
                    width: 0,
                    height: 0,
                });
                this._host.add_child(this._background);
                const siblings = this._container.get_children();
                const index = siblings.indexOf(this.actor);
                this._container.insert_child_at_index(this._host,
                    index >= 0 ? index : 0);
            }
            if (this._styleClass &&
                typeof this.actor.add_style_class_name === 'function')
                this.actor.add_style_class_name(this._styleClass);
        } catch (error) {
            console.warn(`Frosted Glass: cannot attach to ${this._kind}: ${error}`);
            this._removeBackground();
            return;
        }

        if (mode === 'static') {
            this._effect = new Shell.BlurEffect({mode: Shell.BlurMode.ACTOR});
            this._createStaticWallpaper();
        } else {
            this._effect = new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND});
            this._background.add_effect_with_name(EFFECT_NAME, this._effect);
            attachBlurRepaint(this._background, () => this._effect);
        }

        if (this._maskCorners && this._cornerRadius > 0) {
            this._cornerEffect = new RoundedCornersEffect(this._cornerRadius);
            this._background.add_effect_with_name(
                CORNER_EFFECT_NAME, this._cornerEffect);
        }
    }

    _hasUsableSize() {
        try {
            if (this._geometryProvider) {
                const geometry = this._geometryProvider();
                return geometry.width >= 1 && geometry.height >= 1;
            }
            return this.actor.width >= 1 && this.actor.height >= 1;
        } catch (error) {
            return false;
        }
    }

    _createStaticWallpaper() {
        const monitor = Main.layoutManager.findMonitorForActor(this.actor) ??
            Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;

        const wallpaper = new Meta.BackgroundGroup({reactive: false});
        wallpaper.add_effect_with_name(EFFECT_NAME, this._effect);
        this._background.add_child(wallpaper);
        this._tint = new St.Widget({
            reactive: false,
            x_expand: true,
            y_expand: true,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.FILL,
        });
        this._background.add_child(this._tint);
        this._wallpaper = wallpaper;
        this._monitorIndex = monitor.index;
        this._manager = new Background.BackgroundManager({
            container: wallpaper,
            monitorIndex: monitor.index,
            controlPosition: false,
        });

        for (const signal of ['notify::allocation', 'notify::x', 'notify::y']) {
            try {
                this._geometryIds.push([this.actor, this.actor.connect(signal,
                    () => this._syncStaticGeometry())]);
            } catch (error) {
                // Not all actor implementations expose every notify signal.
            }
        }
        this._syncStaticGeometry();
    }

    _syncStaticGeometry() {
        if (!this._wallpaper || !this.actor)
            return;
        const monitor = Main.layoutManager.monitors[this._monitorIndex] ??
            Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;
        const [x, y] = transformedPosition(this._background);
        this._wallpaper.set_position(monitor.x - x, monitor.y - y);
        this._wallpaper.set_size(monitor.width, monitor.height);
        this._tint?.set_size(this._background.width, this._background.height);
    }

    _syncRootGeometry() {
        if (!this._geometryProvider || !this._background)
            return;
        try {
            const geometry = this._geometryProvider();
            this._background.set_position(geometry.x, geometry.y);
            this._background.set_size(geometry.width, geometry.height);
        } catch (error) {
            console.debug(`Frosted Glass: cannot update ${this._kind} geometry: ${error}`);
        }
    }

    _setContentOpacity(opacity) {
        const targetOpacity = opacity ?? 255;
        for (const child of this.actor.get_children()) {
            if (child === this._background)
                continue;
            if (!this._originalOpacity.has(child))
                this._originalOpacity.set(child, child.opacity);
            child.opacity = targetOpacity;
        }
    }

    _restoreContentOpacity() {
        for (const [child, opacity] of this._originalOpacity) {
            try {
                child.opacity = opacity;
            } catch (error) {
                // Child may already be disposed.
            }
        }
        this._originalOpacity.clear();
    }

    _disconnectGeometry() {
        for (const [actor, id] of this._geometryIds.splice(0)) {
            try {
                actor.disconnect(id);
            } catch (error) {
                // Actor may already be disposed.
            }
        }
        this._wallpaper = null;
    }

    _destroyManager() {
        try {
            this._manager?.destroy?.();
        } catch (error) {
            console.debug(`Frosted Glass: cannot destroy ${this._kind} background: ${error}`);
        }
        this._manager = null;
    }

    _removeBackground() {
        if (!this._background)
            return;
        try {
            const root = this._host ?? this._background;
            if (root.get_parent() === this._container)
                this._container.remove_child(root);
            root.destroy();
        } catch (error) {
            // Actor hierarchy may already be gone.
        }
        this._background = null;
        this._host = null;
        this._effect = null;
        this._cornerEffect = null;
        this._tint = null;
        this._wallpaper = null;
    }
}
