// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';
import St from 'gi://St';

const STYLE_CLASSES = new Map([
    ['dot', 'community-indicator-dot'],
    ['hybrid', 'community-indicator-hybrid'],
    ['desk-ux', 'community-indicator-desk-ux'],
]);

const STYLE_GEOMETRY = new Map([
    ['dot', {inactive: [6, 6], active: [6, 6], radius: 99}],
    ['hybrid', {inactive: [18, 4], active: [18, 4], radius: 2}],
    ['desk-ux', {inactive: [8, 3], active: [18, 3], radius: 2}],
]);

export class DockRunningIndicators {
    constructor(dockSettings, dockManager, style = 'dot') {
        this._dockSettings = dockSettings;
        this._dockManager = dockManager;
        this._style = this._normalizeStyle(style);
        this._signals = [
            [dockSettings, dockSettings.connect(
                'changed::running-indicator-style', () => this._apply())],
            [dockManager, dockManager.connect('docks-ready', () => this._apply())],
        ];
        this._apply();
    }

    applyIconStyle(icon) {
        for (const styleClass of STYLE_CLASSES.values())
            icon.remove_style_class_name(styleClass);
        icon.add_style_class_name(this._styleClass());
    }

    applyAppearance(dot, focused, position) {
        const geometry = this._geometry();
        let [width, height] = focused ? geometry.active : geometry.inactive;
        if (position === St.Side.LEFT || position === St.Side.RIGHT)
            [width, height] = [height, width];

        dot.x_align = position === St.Side.LEFT
            ? Clutter.ActorAlign.START
            : position === St.Side.RIGHT
                ? Clutter.ActorAlign.END
                : Clutter.ActorAlign.CENTER;
        dot.y_align = position === St.Side.TOP
            ? Clutter.ActorAlign.START
            : position === St.Side.BOTTOM
                ? Clutter.ActorAlign.END
                : Clutter.ActorAlign.CENTER;
        dot.translationX = 0;
        dot.translationY = 0;
        dot.set_size(width, height);
        dot.set_style(
            `background-color: ${focused ? '-st-accent-color' : 'rgba(160, 160, 168, 0.72)'}; ` +
            `border-radius: ${geometry.radius}px; ` +
            'border-color: transparent; border-width: 0;');
    }

    setStyle(style) {
        this._style = this._normalizeStyle(style);
        this._apply();
    }

    style() {
        return this._style;
    }

    destroy() {
        for (const dock of this._dockManager?._allDocks ?? [])
            this._clearClasses(dock);
        for (const [object, id] of this._signals.splice(0))
            object.disconnect(id);
        this._dockSettings = null;
        this._dockManager = null;
    }

    _apply() {
        if (this._dockSettings.get_enum('running-indicator-style') !== 0) {
            this._dockSettings.set_enum('running-indicator-style', 0);
            return;
        }

        for (const dock of this._dockManager._allDocks) {
            this._clearClasses(dock);
            dock.add_style_class_name(this._styleClass());
            for (const icon of dock?.dash?._appIcons ?? [])
                icon._syncCommunityIndicatorStyle();
        }
    }

    _normalizeStyle(style) {
        return STYLE_CLASSES.has(style) ? style : 'dot';
    }

    _styleClass() {
        return STYLE_CLASSES.get(this._style);
    }

    _geometry() {
        return STYLE_GEOMETRY.get(this._style);
    }

    _clearClasses(actor) {
        for (const styleClass of STYLE_CLASSES.values())
            actor.remove_style_class_name(styleClass);
    }
}
