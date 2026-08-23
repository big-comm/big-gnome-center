// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';
import St from 'gi://St';

const LIFT_STYLE_CLASS = 'community-dock-hover-lift';

export class DockHoverEffects {
    constructor(settings) {
        this._settings = settings;
        this._effect = 'default';
    }

    setEffect(effect) {
        this._effect = effect === 'lift' ? 'lift' : 'default';
    }

    applyStyle(actor) {
        if (this._currentEffect() === 'lift')
            actor.add_style_class_name(LIFT_STYLE_CLASS);
        else
            actor.remove_style_class_name(LIFT_STYLE_CLASS);
    }

    animate(actor, position, iconSize) {
        const lift = actor.hover && this._currentEffect() === 'lift';
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

    _currentEffect() {
        const configured = this._settings?.get_string('dock-hover-effect');
        if (configured === 'lift' || configured === 'default')
            return configured;
        return this._effect;
    }
}
