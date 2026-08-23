// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';
import Pango from 'gi://Pango';
import St from 'gi://St';

export class DockNotificationBadges {
    textForCount(count) {
        if (count <= 9999)
            return count.toString();
        if (count < 1e5)
            return `${(count / 1e3).toFixed(1)}k`;
        if (count < 1e6)
            return `${(count / 1e3).toFixed(0)}k`;
        if (count < 1e8)
            return `${(count / 1e6).toFixed(1)}M`;
        if (count < 1e9)
            return `${(count / 1e6).toFixed(0)}M`;
        return `${(count / 1e9).toFixed(1)}B`;
    }

    create(text) {
        const badge = new St.Bin({
            child: new St.Label({
                styleClass: 'notification-badge',
                text,
            }),
            xAlign: Clutter.ActorAlign.END,
            yAlign: Clutter.ActorAlign.START,
            xExpand: true,
            yExpand: true,
        });
        badge.child.clutterText.ellipsize = Pango.EllipsizeMode.MIDDLE;
        return badge;
    }

    setText(badge, text) {
        badge.child.text = text;
    }
}
