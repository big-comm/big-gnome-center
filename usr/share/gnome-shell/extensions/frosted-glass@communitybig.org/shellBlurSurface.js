// SPDX-License-Identifier: GPL-3.0-or-later

import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Background from 'resource:///org/gnome/shell/ui/background.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {RoundedCornersEffect} from './roundedCorners.js';
import {createBackgroundEffect} from './roundedBackend.js';

const EFFECT_NAME = 'communitybig-frosted-glass-shell';
const CORNER_EFFECT_NAME = 'communitybig-frosted-glass-shell-corners';
const STYLE_CLASS = 'frosted-glass-shell-surface';
const LIGHT_STYLE_CLASS = 'frosted-glass-light';
const MINIMAL_PANEL_CLASS = 'layout-switcher-minimal-panel';
const GUNITY_PANEL_CLASS = 'layout-switcher-g-unity-panel';
const GUNITY_DOCK_CLASS = 'layout-switcher-g-unity-dock';
const POINTER_KINDS = new Set(['quick-settings', 'date-menu']);
const DOCK_TRANSPARENT_STYLE = [
    'background-color: transparent',
    'border-width: 0px',
    'border-color: transparent',
    'box-shadow: none',
].join('; ') + ';';
const PANEL_TRANSPARENT_STYLE = [
    'background-color: transparent',
    'background-image: none',
    'border-width: 0px',
    'border-color: transparent',
    'box-shadow: none',
].join('; ') + ';';
const DASH_TO_PANEL_TRANSPARENT_STYLE = [
    'background-color: transparent',
    'background-image: none',
    'background-gradient-start: transparent',
    'background-gradient-end: transparent',
    'border-color: transparent',
    'box-shadow: none',
].join('; ') + ';';
const DASH_TO_PANEL_CONTENT_TRANSPARENT_STYLE = [
    'background: none',
    'background-image: none',
    'background-gradient-start: transparent',
    'background-gradient-end: transparent',
    'border: 0 solid transparent',
    'border-image: none',
    'box-shadow: none',
].join('; ') + ';';
const QUICK_SETTINGS_TRANSPARENT_STYLE = [
    'background-color: transparent',
    'background-image: none',
    'border-width: 0px',
    'border-color: transparent',
    'box-shadow: none',
].join('; ') + ';';
const QUICK_SETTINGS_POINTER_STYLE = [
    '-arrow-background-color: transparent',
    '-arrow-border-color: transparent',
    '-arrow-border-width: 0px',
    'box-shadow: none',
].join('; ') + ';';

function normalizeStyle(style) {
    return style?.replace(/\s+/g, '') ?? '';
}

function topLevelAnchor(actor) {
    let anchor = actor;
    while (anchor?.get_parent?.() && anchor.get_parent() !== Main.uiGroup)
        anchor = anchor.get_parent();
    return anchor?.get_parent?.() === Main.uiGroup ? anchor : null;
}

function findDockSlider(actor) {
    let current = actor?.get_parent?.();
    while (current && current !== Main.uiGroup) {
        if (typeof current.slideX === 'number')
            return current;
        current = current.get_parent?.();
    }
    return null;
}

function findStyledAncestor(actor, styleClass) {
    let current = actor?.get_parent?.();
    while (current && current !== Main.uiGroup) {
        if (current.has_style_class_name?.(styleClass))
            return current;
        current = current.get_parent?.();
    }
    return null;
}

function intersectRect(first, second) {
    const x = Math.max(first.x, second.x);
    const y = Math.max(first.y, second.y);
    const right = Math.min(first.x + first.width, second.x + second.width);
    const bottom = Math.min(first.y + first.height, second.y + second.height);
    return {
        x,
        y,
        width: Math.max(0, right - x),
        height: Math.max(0, bottom - y),
    };
}

export class ShellBlurSurface {
    constructor(actor, options) {
        this.actor = actor;
        this._kind = options.kind;
        this._cornerRadius = options.cornerRadius ?? 0;
        this._themeCornerRadius = options.themeCornerRadius ?? false;
        this._signals = [];
        this._mode = null;
        this._monitorIndex = -1;
        this._destroyed = false;
        this._lastConfig = null;
        this._pendingUpdate = false;
        this._materialApplied = false;
        this._styles = new Map();
        this._classes = new Map();
        this._styleMutationDepth = new Map();
        this._borderVisibility = null;
        this._dockSlider = this._kind === 'dash-to-dock'
            ? findDockSlider(this.actor)
            : null;
        this._panelContent = this._kind === 'dash-to-panel'
            ? this.actor?.panel ?? null
            : null;
        this._boxPointer = POINTER_KINDS.has(this._kind)
            ? findStyledAncestor(this.actor, 'popup-menu-boxpointer')
            : null;
        this._pointerBorder = this._boxPointer?._border ?? null;

        try {
            this._connectTargets();
        } catch (error) {
            this.destroy();
            throw error;
        }
    }

    _connectTargets() {
        this._connectGeometryHierarchy();
        if (this._kind === 'panel') {
            this._connect(this.actor, 'style-changed', () => {
                if (this._materialApplied && !this._destroyed &&
                    !this._isStyleMutation(this.actor))
                    this._applyTransparentStyle(
                        this.actor, PANEL_TRANSPARENT_STYLE);
            });
        }
        if (this._kind === 'dash-to-panel') {
            this._connect(this.actor, 'style-changed', () => {
                if (!this._isStyleMutation(this.actor))
                    this._applyDashToPanelStyles();
            });
            if (this._panelContent) {
                this._connect(this._panelContent, 'style-changed', () => {
                    if (!this._isStyleMutation(this._panelContent))
                        this._applyDashToPanelStyles();
                });
            }
        }
        for (const object of [this._boxPointer, this._pointerBorder]) {
            if (object)
                this._watchLifetime(object);
        }
    }

    update(config) {
        if (this._destroyed)
            return;
        this._lastConfig = config;
        if (!this._isReady()) {
            this._pendingUpdate = true;
            if (this._overlay)
                this._overlay.visible = false;
            return;
        }
        this._pendingUpdate = false;
        this._cornerRadius = this._resolveCornerRadius();
        const borderless = this._isBorderlessSurface();
        this._setClass(this.actor, LIGHT_STYLE_CLASS, config.lightMode);
        const monitor = Main.layoutManager.findMonitorForActor(this.actor) ??
            Main.layoutManager.primaryMonitor;
        const monitorChanged = config.mode === 'static' && monitor &&
            monitor.index !== this._monitorIndex;
        const cornerMaskChanged = config.mode === 'static' &&
            Boolean(this._cornerEffect) !== (this._cornerRadius > 0);
        if (!this._overlay || this._mode !== config.mode || monitorChanged ||
            cornerMaskChanged)
            this._rebuild(config.mode, monitor);
        if (!this._overlay || !this._syncGeometry())
            return;

        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        this._effect.radius = Math.max(0, Math.round(config.radius * scale));
        this._effect.brightness = config.brightness;
        if (this._mode === 'dynamic' && 'corner_radius' in this._effect)
            this._effect.corner_radius = this._cornerRadius * scale;
        if (this._cornerEffect)
            this._cornerEffect.radius = this._cornerRadius;
        const tintColor = config.lightMode ? '247, 248, 252' : '24, 25, 31';
        const borderColor = config.lightMode
            ? 'rgba(0, 0, 0, 0.18)'
            : 'rgba(255, 255, 255, 0.07)';
        this._tint.set_style(
            `background-color: rgba(${tintColor}, ${config.tintOpacity.toFixed(3)}); ` +
            (borderless ? 'border: none; ' : `border: 1px solid ${borderColor}; `) +
            `border-radius: ${this._cornerRadius}px;`);
        this._applyTargetStyle();
        this._effect.queue_repaint();
    }

    destroy(actorDestroyed = false) {
        if (this._destroyed)
            return;
        this._destroyed = true;
        for (const [object, id] of this._signals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Actor may already be disposed.
            }
        }
        this._restoreTargetStyle(actorDestroyed ? this.actor : null);
        this._removeOverlay();
        this._lastConfig = null;
        this.actor = null;
    }

    _restoreTargetStyle(disposed = null) {
        for (const [actor, record] of this._styles) {
            if (actor === disposed)
                continue;
            try {
                if (normalizeStyle(actor.get_style()) === normalizeStyle(record.applied))
                    actor.set_style(record.original);
            } catch (error) {
                console.debug(`Frosted Glass: cannot restore surface style: ${error}`);
            }
        }
        this._styles.clear();
        this._styleMutationDepth.clear();
        for (const [actor, classes] of this._classes) {
            if (actor === disposed)
                continue;
            for (const [name, record] of classes) {
                try {
                    if (actor.has_style_class_name(name) === record.applied) {
                        if (record.original)
                            actor.add_style_class_name(name);
                        else
                            actor.remove_style_class_name(name);
                    }
                } catch (error) {
                    console.debug(`Frosted Glass: cannot restore surface class: ${error}`);
                }
            }
        }
        this._classes.clear();
        const border = this._borderVisibility;
        this._borderVisibility = null;
        try {
            if (border && border.actor !== disposed && border.actor.visible === false)
                border.actor.visible = border.original;
        } catch (error) {
            console.debug(`Frosted Glass: cannot restore pointer border: ${error}`);
        }
        this._materialApplied = false;
    }

    _setClass(actor, name, enabled) {
        if (!actor)
            return;
        try {
            const current = actor.has_style_class_name(name);
            if (current === enabled)
                return;
            let classes = this._classes.get(actor);
            if (!classes) {
                classes = new Map();
                this._classes.set(actor, classes);
            }
            const previous = classes.get(name);
            classes.set(name, {
                original: previous && current === previous.applied ? previous.original : current,
                applied: enabled,
            });
            this._mutateStyle(actor, () => {
                if (enabled)
                    actor.add_style_class_name(name);
                else
                    actor.remove_style_class_name(name);
            });
        } catch (error) {
            console.debug(`Frosted Glass: cannot apply surface class: ${error}`);
        }
    }

    _applyTargetStyle() {
        if (!this._materialApplied) {
            this._materialApplied = true;
            this._setClass(this.actor, STYLE_CLASS, true);
        }
        const transparentStyle = this._kind === 'panel'
            ? PANEL_TRANSPARENT_STYLE
            : this._kind === 'dash-to-panel'
            ? DASH_TO_PANEL_TRANSPARENT_STYLE
            : this._kind === 'dash-to-dock'
                ? DOCK_TRANSPARENT_STYLE
                : null;
        if (transparentStyle)
            this._applyTransparentStyle(this.actor, transparentStyle);
        if (this._kind === 'dash-to-panel')
            this._applyDashToPanelStyles();
        if (POINTER_KINDS.has(this._kind))
            this._applyTransparentStyle(this.actor, QUICK_SETTINGS_TRANSPARENT_STYLE);
        this._applyTransparentStyle(this._boxPointer, QUICK_SETTINGS_POINTER_STYLE);
        if (this._pointerBorder) {
            try {
                if (this._pointerBorder.visible) {
                    this._borderVisibility = {actor: this._pointerBorder, original: true};
                    this._pointerBorder.hide();
                }
            } catch (error) {
                // BoxPointer can be replaced while the menu is closing.
            }
        }
    }

    _applyDashToPanelStyles() {
        if (this._destroyed || !this._materialApplied || this._kind !== 'dash-to-panel')
            return;
        this._applyTransparentStyle(
            this.actor, DASH_TO_PANEL_TRANSPARENT_STYLE);
        this._applyTransparentStyle(this._panelContent,
            DASH_TO_PANEL_CONTENT_TRANSPARENT_STYLE);
    }

    _applyTransparentStyle(actor, transparentStyle) {
        if (!actor)
            return;
        try {
            const style = actor.get_style?.() ?? null;
            if (normalizeStyle(style) === normalizeStyle(transparentStyle))
                return;
            this._styles.set(actor, {original: style, applied: transparentStyle});
            this._mutateStyle(actor, () =>
                actor.set_style?.(transparentStyle));
        } catch (error) {
            // Extension actors may be replaced while their layout is rebuilt.
        }
    }

    _isStyleMutation(actor) {
        return (this._styleMutationDepth.get(actor) ?? 0) > 0;
    }

    _mutateStyle(actor, action) {
        const depth = this._styleMutationDepth.get(actor) ?? 0;
        this._styleMutationDepth.set(actor, depth + 1);
        try {
            action();
        } finally {
            if (depth)
                this._styleMutationDepth.set(actor, depth);
            else
                this._styleMutationDepth.delete(actor);
        }
    }

    _resolveCornerRadius() {
        if (this._isBorderlessSurface())
            return 0;
        if (!this._themeCornerRadius || !this.actor)
            return this._cornerRadius;
        try {
            this.actor.ensure_style?.();
            const radius = this.actor.get_theme_node?.()
                ?.get_border_radius(St.Corner.TOPLEFT);
            const scale = St.ThemeContext.get_for_stage(global.stage)
                .scale_factor;
            return Number.isFinite(radius)
                ? radius / Math.max(1, scale)
                : this._cornerRadius;
        } catch (error) {
            return this._cornerRadius;
        }
    }

    _isBorderlessSurface() {
        if (this._kind === 'panel') {
            return this.actor?.has_style_class_name?.(MINIMAL_PANEL_CLASS) ||
                this.actor?.has_style_class_name?.(GUNITY_PANEL_CLASS);
        }
        return this._kind === 'dash-to-dock' && (
            this.actor?.has_style_class_name?.(GUNITY_DOCK_CLASS) ||
            Boolean(findStyledAncestor(this.actor, GUNITY_DOCK_CLASS))
        );
    }

    _connectGeometryHierarchy() {
        let current = this.actor;
        while (current && current !== Main.uiGroup) {
            for (const signal of [
                'notify::allocation',
                'notify::mapped',
                'notify::opacity',
                'notify::visible',
                'notify::translation-x',
                'notify::translation-y',
            ]) {
                this._connect(current, signal, () => this._geometryChanged());
            }
            current = current.get_parent?.();
        }
        if (this._dockSlider)
            this._connect(this._dockSlider, 'notify::slide-x',
                () => this._syncGeometry());
    }

    _rebuild(mode, monitor) {
        this._removeOverlay();
        try {
            this._buildOverlay(mode, monitor);
        } catch (error) {
            this._removeOverlay();
            throw error;
        }
    }

    _newOverlayChild(property) {
        const actor = new St.Widget({reactive: false});
        this[property] = actor;
        actor.connect('destroy', () => {
            if (this[property] === actor)
                this[property] = null;
        });
        return actor;
    }

    _buildOverlay(mode, monitor) {
        this._mode = mode;
        this._monitorIndex = monitor?.index ?? -1;
        this._overlay = new St.Widget({
            name: `frosted-glass-${this._kind}`,
            reactive: false,
            clip_to_allocation: true,
        });
        const overlay = this._overlay;
        overlay.connect('destroy', () => {
            if (this._overlay === overlay)
                this._removeOverlay(overlay);
        });
        Main.uiGroup.add_child(this._overlay);

        if (mode === 'static' && this._cornerRadius > 0) {
            this._cornerEffect = new RoundedCornersEffect(this._cornerRadius);
            this._overlay.add_effect_with_name(
                CORNER_EFFECT_NAME, this._cornerEffect);
        }

        if (mode === 'static' && monitor) {
            this._newOverlayChild('_wallpaper');
            this._effect = new Shell.BlurEffect({mode: Shell.BlurMode.ACTOR});
            this._wallpaper.add_effect_with_name(EFFECT_NAME, this._effect);
            this._overlay.add_child(this._wallpaper);
            this._manager = new Background.BackgroundManager({
                container: this._wallpaper,
                monitorIndex: monitor.index,
                controlPosition: false,
            });
        } else {
            this._effect = createBackgroundEffect();
            this._overlay.add_effect_with_name(EFFECT_NAME, this._effect);
        }

        this._newOverlayChild('_tint');
        this._overlay.add_child(this._tint);
        this._ensureStacking();
    }

    _syncGeometry() {
        if (this._destroyed || !this._overlay || !this.actor)
            return false;
        try {
            const [stageX, stageY] = this.actor.get_transformed_position();
            const [stageWidth, stageHeight] = this.actor.get_transformed_size();
            const [groupX, groupY] = Main.uiGroup.get_transformed_position();
            if (![stageX, stageY, stageWidth, stageHeight, groupX, groupY]
                .every(Number.isFinite))
                return false;
            const width = Math.round(stageWidth);
            const height = Math.round(stageHeight);
            if (width < 1 || height < 1)
                return false;

            const x = Math.round(stageX - groupX);
            const y = Math.round(stageY - groupY);
            this._overlay.set_position(x, y);
            this._overlay.set_size(width, height);
            const visibleClip = this._visibleDockClip({
                x: stageX,
                y: stageY,
                width: stageWidth,
                height: stageHeight,
            });
            if (visibleClip) {
                this._overlay.set_clip(
                    Math.round(visibleClip.x - stageX),
                    Math.round(visibleClip.y - stageY),
                    Math.round(visibleClip.width),
                    Math.round(visibleClip.height));
            } else {
                this._overlay.remove_clip();
            }
            const hasVisibleArea = !visibleClip ||
                (visibleClip.width >= 1 && visibleClip.height >= 1);
            this._overlay.visible = this.actor.visible && this.actor.mapped &&
                hasVisibleArea;
            this._overlay.opacity = this.actor.get_paint_opacity?.() ??
                this.actor.opacity;
            this._tint?.set_size(width, height);

            if (this._wallpaper) {
                const monitor = Main.layoutManager.monitors[this._monitorIndex] ??
                    Main.layoutManager.primaryMonitor;
                if (monitor) {
                    this._wallpaper.set_position(monitor.x - stageX,
                        monitor.y - stageY);
                    this._wallpaper.set_size(monitor.width, monitor.height);
                }
            }
            this._ensureStacking();
            return true;
        } catch (error) {
            return false;
        }
    }

    _visibleDockClip(actorRect) {
        if (!this._dockSlider)
            return null;
        try {
            const [x, y] = this._dockSlider.get_transformed_position();
            const [width, height] = this._dockSlider.get_transformed_size();
            return intersectRect(actorRect, {x, y, width, height});
        } catch (error) {
            return null;
        }
    }

    _isReady() {
        if (!this.actor?.mapped)
            return false;
        try {
            const [width, height] = this.actor.get_transformed_size();
            return Number.isFinite(width) && Number.isFinite(height) &&
                width >= 1 && height >= 1;
        } catch (error) {
            return false;
        }
    }

    _geometryChanged() {
        if (this._destroyed)
            return;
        if ((!this._overlay || this._pendingUpdate) && this._lastConfig && this._isReady())
            this.update(this._lastConfig);
        else
            this._syncGeometry();
    }

    _ensureStacking() {
        const anchor = topLevelAnchor(this.actor);
        if (!anchor || this._overlay?.get_parent() !== Main.uiGroup)
            return;
        try {
            Main.uiGroup.set_child_below_sibling(this._overlay, anchor);
        } catch (error) {
            // The target may be moving between popup groups.
        }
    }

    _removeOverlay(destroying = null) {
        const overlay = this._overlay;
        const manager = this._manager;
        const children = [this._tint, this._wallpaper].filter(Boolean);
        const effects = [this._cornerEffect,
            this._wallpaper ? null : this._effect].filter(Boolean);
        this._manager = null;
        this._overlay = null;
        this._wallpaper = null;
        this._tint = null;
        this._effect = null;
        this._cornerEffect = null;
        this._mode = null;
        this._monitorIndex = -1;
        const cleanup = action => {
            try {
                action();
            } catch (error) {
                console.debug(`Frosted Glass: cannot release ${this._kind} resource: ${error}`);
            }
        };
        cleanup(() => manager?.destroy());
        if (overlay !== destroying) {
            for (const effect of effects)
                cleanup(() => overlay?.remove_effect(effect));
            for (const child of children)
                cleanup(() => child.destroy());
            cleanup(() => {
                if (overlay?.get_parent() === Main.uiGroup)
                    Main.uiGroup.remove_child(overlay);
            });
            cleanup(() => overlay?.destroy());
        }
    }

    _connect(object, signal, callback) {
        try {
            this._watchLifetime(object);
            this._signals.push([object, object.connect(signal, (...args) => {
                if (!this._destroyed)
                    callback(...args);
            })]);
        } catch (error) {
            // Optional notify signals differ between actor implementations.
        }
    }

    _watchLifetime(object) {
        try {
            if (!this._signals.some(([target]) => target === object)) {
                const destroyId = object.connect('destroy', () => {
                    // Disconnect while the emitter is still alive, not after disposal.
                    const owned = this._signals.filter(([target]) => target === object);
                    this._signals = this._signals.filter(([target]) => target !== object);
                    for (const [, id] of owned) {
                        try {
                            object.disconnect(id);
                        } catch (error) {
                            console.debug(`Frosted Glass: cannot disconnect retired actor: ${error}`);
                        }
                    }
                    this._styles.delete(object);
                    this._classes.delete(object);
                    if (this._borderVisibility?.actor === object)
                        this._borderVisibility = null;
                    for (const key of ['_panelContent', '_boxPointer', '_pointerBorder', '_dockSlider']) {
                        if (this[key] === object)
                            this[key] = null;
                    }
                    if (this.actor === object)
                        this.destroy(true);
                });
                this._signals.push([object, destroyId]);
            }
        } catch (error) {
            // Only live actors expose the destroy signal.
        }
    }
}
