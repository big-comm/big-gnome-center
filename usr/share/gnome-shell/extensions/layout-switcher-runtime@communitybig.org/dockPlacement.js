// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';
import St from 'gi://St';

const POSITIONS = new Map([
    ['top', St.Side.TOP],
    ['right', St.Side.RIGHT],
    ['bottom', St.Side.BOTTOM],
    ['left', St.Side.LEFT],
]);

export class DockPlacement {
    constructor(settings) {
        this._settings = settings;
    }

    apply(edge, extended) {
        const position = POSITIONS.get(edge);
        if (position !== undefined)
            this._settings.set_enum('dock-position', position);
        this._settings.set_boolean('extend-height', Boolean(extended));
    }

    position() {
        const position = this._settings.get_enum('dock-position');
        if (Clutter.get_default_text_direction() !== Clutter.TextDirection.RTL)
            return position;
        if (position === St.Side.LEFT)
            return St.Side.RIGHT;
        if (position === St.Side.RIGHT)
            return St.Side.LEFT;
        return position;
    }

    edge() {
        const position = this._settings.get_enum('dock-position');
        return [...POSITIONS].find(([, value]) => value === position)?.[0] ?? 'bottom';
    }

    extended() {
        return this._settings.get_boolean('extend-height');
    }
}
