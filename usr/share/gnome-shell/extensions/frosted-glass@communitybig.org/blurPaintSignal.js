// SPDX-License-Identifier: GPL-3.0-or-later

import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';

const BlurPaintSignal = GObject.registerClass({
    GTypeName: 'CommunityBigBlurPaintSignal',
    Signals: {'update-blur': {}},
}, class BlurPaintSignal extends Clutter.Effect {
    vfunc_paint(node, paintContext, paintFlags) {
        this.emit('update-blur');
        super.vfunc_paint(node, paintContext, paintFlags);
    }
});

export function attachBlurRepaint(actor, getBlurEffect) {
    const paintSignal = new BlurPaintSignal();
    let counter = 0;
    paintSignal.connect('update-blur', () => {
        if (counter === 0) {
            counter = 2;
            try {
                getBlurEffect()?.queue_repaint();
            } catch (error) {
                // Effect may be disposed during actor teardown.
            }
        } else {
            counter--;
        }
    });
    actor.add_effect(paintSignal);
    return paintSignal;
}
