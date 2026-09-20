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
        for (const [dash, record] of [...this._records]) {
            if (this._records.get(dash) === record)
                this._detach(dash, true);
        }
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
            pointerWatches: records.filter(record => record.pointerId > 0).length,
            pollSources: 0,
            animationSources: records.filter(record => record.sourceId > 0).length,
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
            dash,
            sourceId: 0,
            destroyId: 0,
            signals: [],
            pointerId: 0,
            pointerTracker: global.backend.get_cursor_tracker(),
            states: new Map(),
        };
        this._records.set(dash, record);
        try {
            record.destroyId = dash.connect('destroy', () => {
                if (this._records.get(dash) === record)
                    this._detach(dash, false, false);
            });
            const wake = () => this._wake(dash, record);
            record.pointerId = record.pointerTracker.connect('position-invalidated', () => {
                if (this._records.get(dash) !== record)
                    return;
                // Reading rearms native position invalidation for the next motion.
                record.pointerTracker.get_pointer();
                wake();
            });
            record.pointerTracker.get_pointer();
            const connect = (object, signal, callback) => {
                record.signals.push([object, object.connect(signal, callback)]);
            };
            connect(global.stage, 'captured-event', (_stage, event) => {
                if (this._records.get(dash) !== record)
                    return Clutter.EVENT_PROPAGATE;
                if ([Clutter.EventType.MOTION, Clutter.EventType.ENTER,
                    Clutter.EventType.LEAVE].includes(event.type())) wake();
                return Clutter.EVENT_PROPAGATE;
            });
            for (const signal of ['notify::mapped', 'notify::allocation'])
                connect(dash, signal, () => this._wake(dash, record, true));
            for (const signal of ['child-added', 'child-removed'])
                connect(dash._box, signal, () => this._wake(dash, record, true));
            if (dash.showAppsButton)
                connect(dash.showAppsButton, 'notify::visible', () => this._wake(dash, record, true));
            for (const adjustment of [
                dash._scrollView?.hadjustment ?? dash._scrollView?.hscroll?.adjustment,
                dash._scrollView?.vadjustment ?? dash._scrollView?.vscroll?.adjustment,
            ].filter(Boolean))
                connect(adjustment, 'notify::value', () => this._wake(dash, record, true));
            this._wake(dash, record, true);
        } catch (error) {
            if (this._records.get(dash) === record)
                this._detach(dash, true);
            throw error;
        }
    }

    refresh(dash) {
        const record = this._records.get(dash);
        if (record) this._wake(dash, record, true);
    }

    _wake(dash, record, force = false) {
        if (this._records.get(dash) !== record)
            return;
        if (!this._isDockShown(dash) || !dash.get_paint_visibility()) {
            this._suspend(record);
            const id = record.sourceId;
            record.sourceId = 0;
            record.frame = null;
            if (id) this._cleanup(() => GLib.source_remove(id));
            return;
        }
        if (this._records.get(dash) !== record || record.sourceId ||
            (!force && !this._pointerNear(dash) &&
                ![...record.states.values()].some(state => state.scale !== 1)))
            return;
        const frame = record.frame = {};
        record.sourceId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            FRAME_INTERVAL_MS,
            () => {
                if (this._records.get(dash) !== record || record.frame !== frame)
                    return GLib.SOURCE_REMOVE;
                let moving;
                try {
                    moving = this._tick(dash, record);
                } catch (error) {
                    console.warn(`[layout-switcher] Dock magnification update failed: ${error}`);
                    if (this._records.get(dash) === record)
                        this._detach(dash, true);
                    return GLib.SOURCE_REMOVE;
                }
                if (this._records.get(dash) !== record || record.frame !== frame)
                    return GLib.SOURCE_REMOVE;
                if (!moving) {
                    record.sourceId = 0;
                    record.frame = null;
                }
                return moving ? GLib.SOURCE_CONTINUE : GLib.SOURCE_REMOVE;
            },
        );
    }

    _detach(dash, reset, disconnect = true) {
        const record = this._records.get(dash);
        if (!record)
            return;
        this._records.delete(dash);
        const sourceId = record.sourceId;
        const destroyId = record.destroyId;
        record.sourceId = 0;
        record.frame = null;
        record.destroyId = 0;
        if (sourceId > 0)
            this._cleanup(() => GLib.source_remove(sourceId));
        if (disconnect && destroyId > 0)
            this._cleanup(() => dash.disconnect(destroyId));
        for (const [object, id] of record.signals.splice(0))
            this._cleanup(() => object.disconnect(id));
        const pointerId = record.pointerId;
        record.pointerId = 0;
        if (pointerId) this._cleanup(() => record.pointerTracker.disconnect(pointerId));
        const states = [...record.states];
        record.states.clear();
        for (const [actor, state] of states)
            this._destroyState(actor, state, reset);
        if (reset)
            this._resetCount++;
    }

    _tick(dash, record) {
        if (!this._isDockShown(dash)) {
            this._suspend(record);
            return;
        }
        record.suspended = false;

        const actors = this._iconActors(dash);
        const liveActors = new Set(actors);
        for (const [actor, state] of [...record.states]) {
            if (liveActors.has(actor))
                continue;
            record.states.delete(actor);
            this._destroyState(actor, state, true);
        }
        if (actors.length === 0)
            return;

        const [pointerX, pointerY] = global.get_pointer();
        const horizontal = dash._position === St.Side.TOP ||
            dash._position === St.Side.BOTTOM;
        const iconSize = Math.max(1, dash.iconSize ?? 1);
        const reach = iconSize * 2.6;
        const pointerAxis = horizontal ? pointerX : pointerY;
        const active = dash.get_paint_visibility() && this._pointerNear(dash);
        const maximum = 1 + this._intensity / 100;
        let moving = false;

        for (const actor of actors) {
            if (this._records.get(dash) !== record)
                return;
            let state = record.states.get(actor);
            if (!state) {
                state = this._createState(record, actor, maximum);
            }
            if (this._records.get(dash) !== record || state.retired)
                return;
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
            moving ||= state.scale !== target;
            this._updateClone(
                state, actor, dash._position,
                actorX, actorY, actorWidth, actorHeight,
            );
        }
        this._updateCount++;
        return moving;
    }

    _pointerNear(dash) {
        const [x, y] = global.get_pointer();
        const [dx, dy] = dash.get_transformed_position();
        const [width, height] = dash.get_transformed_size();
        const horizontal = dash._position === St.Side.TOP || dash._position === St.Side.BOTTOM;
        const size = Math.max(1, dash.iconSize ?? 1);
        const mx = size * (horizontal ? 2.6 : 0.8);
        const my = size * (horizontal ? 0.8 : 2.6);
        return x >= dx - mx && x <= dx + width + mx && y >= dy - my && y <= dy + height + my;
    }

    _suspend(record) {
        if (record.suspended)
            return;
        record.suspended = true;
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
        const state = {
            clone,
            scale: 1,
            sourceHidden: false,
            sourceOpacity: actor.opacity,
            baseIcon: null,
            originalCreateIcon: null,
            iconChildAddedId: 0,
            destroyId: 0,
            retired: false,
            signals: [],
            mappedIcon: null,
        };
        record.states.set(actor, state);
        try {
            clone.hide();
            Main.uiGroup.add_child(clone);
            if (!state.retired)
                this._enableHighResolutionSource(actor, state, maximum);
            if (!state.retired) {
                state.destroyId = actor.connect('destroy', () => {
                    if (record.states.get(actor) !== state)
                        return;
                    record.states.delete(actor);
                    this._destroyState(actor, state, false);
                });
                for (const signal of ['notify::allocation', 'notify::mapped',
                    'notify::translation-x', 'notify::translation-y']) {
                    state.signals.push(actor.connect(signal, () => {
                        if (!state.retired) this.refresh(record.dash);
                    }));
                }
            }
        } catch (error) {
            if (record.states.get(actor) === state)
                record.states.delete(actor);
            this._destroyState(actor, state, true);
            throw error;
        }
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
        if (state.retired)
            return;
        state.retired = true;
        const destroyId = state.destroyId;
        state.destroyId = 0;
        if (destroyId > 0)
            this._cleanup(() => actor.disconnect(destroyId));
        for (const id of state.signals.splice(0))
            this._cleanup(() => actor.disconnect(id));
        if (restore)
            this._cleanup(() => this._restoreSource(actor, state));
        this._disableHighResolutionSource(state, restore);
        this._cleanup(() => state.clone?.destroy());
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
        const original = state.originalCreateIcon;
        state.createIcon = function (size, ...args) {
            const requested = state.retired || state.baseIcon !== baseIcon
                ? size : Math.ceil(size * maximum);
            return original.call(this, requested, ...args);
        };
        baseIcon.createIcon = state.createIcon;
        state.iconChildAddedId = baseIcon._iconBin.connect('child-added', () => {
            if (!state.retired && state.baseIcon === baseIcon)
                this._constrainHighResolutionIcon(state);
        });
        baseIcon._createIconTexture(baseIcon.iconSize);
        if (!state.retired)
            this._constrainHighResolutionIcon(state);
    }

    _disableHighResolutionSource(state, refresh = true) {
        this._cancelIconMap(state);
        const {baseIcon} = state;
        if (!baseIcon)
            return;
        const id = state.iconChildAddedId;
        const original = state.originalCreateIcon;
        const owned = state.createIcon;
        state.baseIcon = null;
        state.originalCreateIcon = null;
        state.createIcon = null;
        state.iconChildAddedId = 0;
        if (id > 0)
            this._cleanup(() => baseIcon._iconBin.disconnect(id));
        this._cleanup(() => {
            if (baseIcon.createIcon !== owned)
                return;
            baseIcon.createIcon = original;
            if (refresh && baseIcon.get_stage())
                baseIcon._createIconTexture(baseIcon.iconSize);
        });
    }

    _cancelIconMap(state) {
        const pending = state.mappedIcon;
        state.mappedIcon = null;
        if (pending?.id)
            this._cleanup(() => pending.child.disconnect(pending.id));
    }

    _constrainHighResolutionIcon(state) {
        const {baseIcon} = state;
        if (state.retired || !baseIcon)
            return;
        const child = baseIcon._iconBin.child;
        if (state.mappedIcon?.child === child)
            return;
        this._cancelIconMap(state);
        if (!child)
            return;
        const scaleFactor = St.ThemeContext.get_for_stage(global.stage)
            .scale_factor || 1;
        const size = baseIcon.iconSize * scaleFactor;
        if (child.mapped) {
            child.set_size(size, size);
            return;
        }
        const pending = {child, id: 0};
        state.mappedIcon = pending;
        pending.id = child.connect('notify::mapped', () => {
            if (state.retired || state.mappedIcon !== pending ||
                state.baseIcon !== baseIcon || baseIcon._iconBin.child !== child)
                return;
            if (!child.mapped)
                return;
            this._cancelIconMap(state);
            child.set_size(size, size);
        });
    }

    _restoreSource(actor, state) {
        if (!state.sourceHidden)
            return;
        state.sourceHidden = false;
        if (actor.opacity === 0)
            actor.opacity = state.sourceOpacity;
    }

    _cleanup(callback) {
        try {
            callback();
        } catch (error) {
            console.warn(`[layout-switcher] Dock magnification cleanup failed: ${error}`);
        }
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
