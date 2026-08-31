// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const LIFT_STYLE_CLASS = 'community-dock-hover-lift';
const MAGNIFY_STYLE_CLASS = 'community-dock-hover-magnify';
const FRAME_INTERVAL_MS = 16;
const LERP_FACTOR = 0.28;
const VISIBLE_SCALE_THRESHOLD = 1.002;

export class DockHoverEffects {
    constructor(isDockShown = () => true) {
        this._effect = 'default';
        this._intensity = 40;
        this._isDockShown = isDockShown;
        this._records = new Map();
        this._updateCount = 0;
        this._resetCount = 0;
    }

    setEffect(effect, intensity = 40) {
        const next = ['lift', 'magnify'].includes(effect) ? effect : 'default';
        const nextIntensity = Math.max(20, Math.min(60, intensity ?? 40));
        const resolutionChanged = this._effect === 'magnify' &&
            next === 'magnify' && this._intensity !== nextIntensity;
        this._effect = next;
        this._intensity = nextIntensity;
        if (next !== 'magnify' || resolutionChanged)
            this.releaseAll();
    }

    effect() {
        return this._effect;
    }

    intensity() {
        return this._intensity;
    }

    labelClearance(iconSize) {
        if (this._effect !== 'magnify')
            return 0;
        return Math.ceil(Math.max(0, iconSize) * this._intensity / 100);
    }

    applyStyle(dash) {
        dash.remove_style_class_name(LIFT_STYLE_CLASS);
        dash.remove_style_class_name(MAGNIFY_STYLE_CLASS);
        if (this._effect === 'lift')
            dash.add_style_class_name(LIFT_STYLE_CLASS);
        else if (this._effect === 'magnify')
            dash.add_style_class_name(MAGNIFY_STYLE_CLASS);

        if (this._effect === 'magnify')
            this._attach(dash);
        else
            this._detach(dash, true);
    }

    animate(actor, position, iconSize) {
        if (this._effect === 'magnify')
            return;

        const lift = actor.hover && this._effect === 'lift';
        const distance = lift ? Math.max(3, Math.round(iconSize * 0.1)) : 0;
        let translationX = 0;
        let translationY = 0;
        if (position === St.Side.BOTTOM)
            translationY = -distance;
        else if (position === St.Side.TOP)
            translationY = distance;
        else if (position === St.Side.LEFT)
            translationX = distance;
        else if (position === St.Side.RIGHT)
            translationX = -distance;

        actor.set_pivot_point(0.5, 0.5);
        actor.ease({
            translation_x: translationX,
            translation_y: translationY,
            scale_x: lift ? 1.08 : 1,
            scale_y: lift ? 1.08 : 1,
            duration: 160,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
        });
    }

    releaseAll() {
        for (const dash of [...this._records.keys()])
            this._detach(dash, true);
    }

    diagnostics() {
        const records = [...this._records.values()];
        const states = records.flatMap(record => [...record.states.values()]);
        return {
            implementation: 'layout-switcher-runtime',
            renderer: 'ui-group-clone',
            effect: this._effect,
            intensity: this._intensity,
            maxScale: 1 + this._intensity / 100,
            connectedDocks: records.length,
            pollSources: records.filter(record => record.sourceId > 0).length,
            trackedActors: states.length,
            cloneActors: states.filter(state => state.clone).length,
            highResolutionSources: states.filter(state => state.baseIcon).length,
            visibleClones: states.filter(state => state.clone?.visible).length,
            scaledActors: states.filter(state =>
                Math.abs(state.scale - 1) > 0.01).length,
            hiddenSources: states.filter(state => state.sourceHidden).length,
            updateCount: this._updateCount,
            resetCount: this._resetCount,
        };
    }

    _attach(dash) {
        if (this._records.has(dash))
            return;

        const record = {
            sourceId: 0,
            destroyId: 0,
            states: new Map(),
        };
        this._records.set(dash, record);
        record.destroyId = dash.connect('destroy', () => {
            this._detach(dash, false, false);
        });
        record.sourceId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            FRAME_INTERVAL_MS,
            () => {
                if (!this._records.has(dash))
                    return GLib.SOURCE_REMOVE;
                try {
                    this._tick(dash, record);
                } catch (error) {
                    console.warn(
                        `[layout-switcher] Dock magnification update failed: ${error}`,
                    );
                    this._detach(dash, true);
                    return GLib.SOURCE_REMOVE;
                }
                return GLib.SOURCE_CONTINUE;
            },
        );
    }

    _detach(dash, reset, disconnect = true) {
        const record = this._records.get(dash);
        if (!record)
            return;
        this._records.delete(dash);
        if (record.sourceId > 0) {
            GLib.source_remove(record.sourceId);
            record.sourceId = 0;
        }
        if (disconnect && record.destroyId > 0)
            dash.disconnect(record.destroyId);
        for (const [actor, state] of record.states)
            this._destroyState(actor, state, reset);
        record.states.clear();
        if (reset)
            this._resetCount++;
    }

    _tick(dash, record) {
        if (!this._isDockShown(dash)) {
            this._suspend(record);
            return;
        }

        const actors = this._iconActors(dash);
        const liveActors = new Set(actors);
        for (const [actor, state] of [...record.states]) {
            if (liveActors.has(actor))
                continue;
            this._destroyState(actor, state, true);
            record.states.delete(actor);
        }
        if (actors.length === 0)
            return;

        const [pointerX, pointerY] = global.get_pointer();
        const [dashX, dashY] = dash.get_transformed_position();
        const [dashWidth, dashHeight] = dash.get_transformed_size();
        const horizontal = dash._position === St.Side.TOP ||
            dash._position === St.Side.BOTTOM;
        const iconSize = Math.max(1, dash.iconSize ?? 1);
        const reach = iconSize * 2.6;
        const crossMargin = iconSize * 0.8;
        const pointerAxis = horizontal ? pointerX : pointerY;
        const withinCrossAxis = horizontal
            ? pointerY >= dashY - crossMargin &&
                pointerY <= dashY + dashHeight + crossMargin
            : pointerX >= dashX - crossMargin &&
                pointerX <= dashX + dashWidth + crossMargin;
        const withinMainAxis = horizontal
            ? pointerX >= dashX - reach && pointerX <= dashX + dashWidth + reach
            : pointerY >= dashY - reach && pointerY <= dashY + dashHeight + reach;
        const active = dash.get_paint_visibility() &&
            withinCrossAxis && withinMainAxis;
        const maximum = 1 + this._intensity / 100;

        for (const actor of actors) {
            let state = record.states.get(actor);
            if (!state) {
                state = this._createState(record, actor, maximum);
                record.states.set(actor, state);
            }
            const [actorX, actorY] = actor.get_transformed_position();
            const [actorWidth, actorHeight] = actor.get_transformed_size();
            const center = horizontal
                ? actorX + actorWidth / 2
                : actorY + actorHeight / 2;
            const distance = active ? Math.abs(pointerAxis - center) : reach;
            const proximity = Math.max(0, 1 - distance / reach);
            const smooth = proximity * proximity * (3 - 2 * proximity);
            const target = 1 + (maximum - 1) * smooth;
            const next = state.scale + (target - state.scale) * LERP_FACTOR;
            state.scale = Math.abs(next - target) < 0.001 ? target : next;
            this._updateClone(
                state, actor, dash._position,
                actorX, actorY, actorWidth, actorHeight,
            );
        }
        this._updateCount++;
    }

    _suspend(record) {
        for (const [actor, state] of record.states) {
            state.scale = 1;
            state.clone?.hide();
            this._restoreSource(actor, state);
        }
    }

    _iconActors(dash) {
        const actors = (dash._box?.get_children() ?? [])
            .map(item => item.child)
            .filter(actor => actor?.visible && actor.icon);
        const showApps = dash.showAppsButton;
        if (showApps?.visible)
            actors.push(showApps);
        return actors;
    }

    _createState(record, actor, maximum) {
        const clone = new Clutter.Clone({
            source: actor,
            reactive: false,
            opacity: 255,
        });
        clone.hide();
        Main.uiGroup.add_child(clone);
        const state = {
            clone,
            scale: 1,
            sourceHidden: false,
            sourceOpacity: actor.opacity,
            baseIcon: null,
            originalCreateIcon: null,
            iconChildAddedId: 0,
            destroyId: 0,
        };
        this._enableHighResolutionSource(actor, state, maximum);
        state.destroyId = actor.connect('destroy', () => {
            record.states.delete(actor);
            clone.destroy();
        });
        return state;
    }

    _updateClone(state, actor, position, x, y, width, height) {
        const {clone} = state;
        clone.set_position(x, y);
        clone.set_size(width, height);
        this._setPivot(clone, position);
        clone.scale_x = state.scale;
        clone.scale_y = state.scale;
        if (state.scale > VISIBLE_SCALE_THRESHOLD) {
            if (!state.sourceHidden) {
                state.sourceOpacity = actor.opacity;
                actor.opacity = 0;
                state.sourceHidden = true;
            }
            clone.show();
        } else {
            clone.hide();
            this._restoreSource(actor, state);
        }
    }

    _destroyState(actor, state, restore) {
        if (state.destroyId > 0)
            actor.disconnect(state.destroyId);
        if (restore) {
            this._restoreSource(actor, state);
            this._disableHighResolutionSource(state);
        }
        state.clone?.destroy();
        state.clone = null;
    }

    _enableHighResolutionSource(actor, state, maximum) {
        const baseIcon = actor.icon ?? actor._delegate?.icon ??
            actor.get_parent()?.icon;
        if (!baseIcon?._iconBin || !baseIcon.createIcon ||
            !baseIcon._createIconTexture)
            return;

        state.baseIcon = baseIcon;
        state.originalCreateIcon = baseIcon.createIcon;
        baseIcon.createIcon = size =>
            state.originalCreateIcon.call(
                baseIcon, Math.ceil(size * maximum));
        state.iconChildAddedId = baseIcon._iconBin.connect('child-added', () =>
            this._constrainHighResolutionIcon(baseIcon));
        baseIcon._createIconTexture(baseIcon.iconSize);
        this._constrainHighResolutionIcon(baseIcon);
    }

    _disableHighResolutionSource(state) {
        const {baseIcon} = state;
        if (!baseIcon)
            return;
        if (state.iconChildAddedId > 0)
            baseIcon._iconBin.disconnect(state.iconChildAddedId);
        baseIcon.createIcon = state.originalCreateIcon;
        if (baseIcon.get_stage())
            baseIcon._createIconTexture(baseIcon.iconSize);
        state.baseIcon = null;
        state.originalCreateIcon = null;
        state.iconChildAddedId = 0;
    }

    _constrainHighResolutionIcon(baseIcon) {
        const child = baseIcon._iconBin.child;
        if (!child)
            return;
        const scaleFactor = St.ThemeContext.get_for_stage(global.stage)
            .scale_factor || 1;
        const size = baseIcon.iconSize * scaleFactor;
        if (child.mapped) {
            child.set_size(size, size);
            return;
        }
        const mappedId = child.connect('notify::mapped', () => {
            if (!child.mapped)
                return;
            child.set_size(size, size);
            child.disconnect(mappedId);
        });
    }

    _restoreSource(actor, state) {
        if (!state.sourceHidden)
            return;
        actor.opacity = state.sourceOpacity;
        state.sourceHidden = false;
    }

    _setPivot(actor, position) {
        if (position === St.Side.TOP)
            actor.set_pivot_point(0.5, 0);
        else if (position === St.Side.LEFT)
            actor.set_pivot_point(0, 0.5);
        else if (position === St.Side.RIGHT)
            actor.set_pivot_point(1, 0.5);
        else
            actor.set_pivot_point(0.5, 1);
    }
}
