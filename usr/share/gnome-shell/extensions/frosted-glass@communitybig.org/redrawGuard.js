// SPDX-License-Identifier: GPL-3.0-or-later
// Repaint a dynamic blur whole after GNOME Shell redrew only part of it.
//
// Mutter repaints only the damaged part of the screen. A background blur
// redrawn inside that clip samples a partial backdrop, so it no longer matches
// the blur around it: hovering a dock icon or a calendar day leaves square
// blocks until the next full redraw. When a paint does not cover the surface,
// queue the whole surface, and every blurred surface overlapping it, once. The
// next paint covers them, so this never repaints in a loop and does nothing
// while the screen is idle. Blur My Shell (src/render/backdrop/) does the same.
import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import Mtk from 'gi://Mtk';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Partial paints in a row before giving up, so a clip that can never cover
// the surface cannot keep the compositor busy.
const MAX_REQUEUES = 3;
const guards = new Set();

function extents(actor) {
    const [x, y] = actor.get_transformed_position();
    const [width, height] = actor.get_transformed_size();
    if (![x, y, width, height].every(Number.isFinite) || width < 1 || height < 1)
        return null;
    return {
        x: Math.floor(x),
        y: Math.floor(y),
        right: Math.ceil(x + width),
        bottom: Math.ceil(y + height),
    };
}

function overlaps(a, b) {
    return a.x < b.right && b.x < a.right && a.y < b.bottom && b.y < a.bottom;
}

// The part of the surface on screen; the redraw clip never covers the rest.
function visibleRegion(bounds) {
    const region = Mtk.Region.create();
    for (const monitor of Main.layoutManager.monitors ?? []) {
        const x = Math.max(bounds.x, monitor.x);
        const y = Math.max(bounds.y, monitor.y);
        const right = Math.min(bounds.right, monitor.x + monitor.width);
        const bottom = Math.min(bounds.bottom, monitor.y + monitor.height);
        if (right > x && bottom > y) {
            region.union_rectangle(new Mtk.Rectangle({
                x, y, width: right - x, height: bottom - y,
            }));
        }
    }
    return region;
}

function coveredBy(clip, bounds) {
    const uncovered = visibleRegion(bounds);
    uncovered.subtract(clip);
    return uncovered.is_empty();
}

function queueOverlapping(actor, bounds) {
    const affected = [{actor, bounds}];
    const candidates = new Map();
    for (const guard of guards) {
        const other = guard.get_actor();
        const otherBounds = other && other !== actor && other.mapped ? extents(other) : null;
        if (otherBounds)
            candidates.set(other, otherBounds);
    }
    for (let index = 0; index < affected.length; index++) {
        for (const [other, otherBounds] of candidates) {
            if (!overlaps(affected[index].bounds, otherBounds))
                continue;
            affected.push({actor: other, bounds: otherBounds});
            candidates.delete(other);
        }
    }
    for (const surface of affected)
        surface.actor.queue_redraw();
}

const PartialRedrawGuard = GObject.registerClass({
    GTypeName: 'CommunityBigFrostedPartialRedrawGuard',
}, class PartialRedrawGuard extends Clutter.Effect {
    _init() {
        super._init();
        this._requeues = 0;
    }

    vfunc_set_actor(actor) {
        super.vfunc_set_actor(actor);
        if (actor)
            guards.add(this);
        else
            guards.delete(this);
    }

    vfunc_paint_node(node, paintContext) {
        const actor = this.get_actor();
        node.add_child(new Clutter.ActorNode(actor, -1));
        try {
            this._check(actor, paintContext.get_redraw_clip());
        } catch (error) {
            // A missed repaint only leaves the old artifact; never break painting.
        }
    }

    _check(actor, clip) {
        const bounds = clip ? extents(actor) : null;
        if (!bounds || coveredBy(clip, bounds)) {
            this._requeues = 0;
            return;
        }
        if (this._requeues >= MAX_REQUEUES)
            return;
        this._requeues++;
        queueOverlapping(actor, bounds);
    }
});

export function createRedrawGuard() {
    return new PartialRedrawGuard();
}
