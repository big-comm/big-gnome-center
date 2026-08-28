// SPDX-License-Identifier: GPL-2.0-or-later

import * as Utils from './taskbar/utils.js';

export class TaskbarIndicatorRenderer {
    constructor(settings) {
        this._settings = settings;
        this._drawCounts = {hybrid: 0, 'desk-ux': 0};
        this._lastStyle = '';
    }

    style() {
        const focused = this._settings.get_string('dot-style-focused');
        const unfocused = this._settings.get_string('dot-style-unfocused');
        if (focused === 'SEGMENTED' && unfocused === 'SEGMENTED')
            return 'hybrid';
        if (focused === 'METRO' && unfocused === 'DASHES')
            return 'desk-ux';
        return null;
    }

    draw(area, cr, params) {
        const style = this.style();
        if (!style)
            return false;

        const {isFocused, isHorizontal, areaSize, size, startX, startY, color} = params;
        const targetLength = (style === 'hybrid' || isFocused ? 18 : 8) *
            Utils.getScaleFactor();
        const length = Math.min(areaSize, targetLength);
        const offset = Math.floor((areaSize - length) / 2);
        const visualScale = length > 0 ? targetLength / length : 1;

        area.set_scale.apply(area, isHorizontal
            ? [visualScale, 1]
            : [1, visualScale]);
        cr.translate.apply(cr, isHorizontal
            ? [offset, startY]
            : [startX, offset]);
        cr.setSourceColor(color);
        cr.newSubPath();
        cr.rectangle.apply(cr, isHorizontal
            ? [0, 0, length, size]
            : [0, 0, size, length]);
        cr.fill();

        this._lastStyle = style;
        this._drawCounts[style]++;
        return true;
    }

    diagnostics() {
        return {
            style: this.style() ?? 'none',
            lastStyle: this._lastStyle,
            drawCounts: {...this._drawCounts},
        };
    }

    destroy() {
        this._settings = null;
    }
}
