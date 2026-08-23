// SPDX-License-Identifier: GPL-2.0-or-later

import Gio from 'gi://Gio';
import GObject from 'gi://GObject';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const DESKTOP_NOTIFICATIONS_SCHEMA = 'org.gnome.desktop.notifications';
const COUNTER_KEY = 'show-icons-notifications-counter';

export const DockNotificationMonitor = GObject.registerClass({
    Signals: {
        changed: {},
        'state-changed': {},
    },
}, class DockNotificationMonitor extends GObject.Object {
    _init(dockSettings) {
        super._init();

        this._dockSettings = dockSettings;
        this._settings = new Gio.Settings({
            schema_id: DESKTOP_NOTIFICATIONS_SCHEMA,
        });
        this._settingsConnections = [];
        this._sourceConnections = [];
        this._notificationConnections = [];
        this._appNotifications = Object.create(null);
        this._dndMode = !this._settings.get_boolean('show-banners');
        this._enabled = this._isCounterEnabled();

        this._connect(this._settingsConnections, this._settings,
            'changed::show-banners', () => this._updateEnabledState());
        this._connect(this._settingsConnections, this._dockSettings,
            `changed::${COUNTER_KEY}`, () => this._updateEnabledState());
        this._rebuild();
    }

    get enabled() {
        return this._enabled;
    }

    get dndMode() {
        return this._dndMode;
    }

    getAppNotificationsCount(appId) {
        return this._appNotifications?.[appId] ?? 0;
    }

    getBadgeCount(appId, remoteEntry, remoteOverridesNotifications) {
        const remoteCount = remoteEntry?.['count-visible']
            ? remoteEntry.count ?? 0
            : 0;
        if (remoteCount > 0 && remoteOverridesNotifications)
            return remoteCount;

        return remoteCount + this.getAppNotificationsCount(appId);
    }

    destroy() {
        this._disconnect(this._notificationConnections);
        this._disconnect(this._sourceConnections);
        this._disconnect(this._settingsConnections);
        this._appNotifications = null;
        this._dockSettings = null;
        this._settings = null;
    }

    _isCounterEnabled() {
        return !this._dndMode &&
            this._dockSettings.get_boolean(COUNTER_KEY);
    }

    _updateEnabledState() {
        this._dndMode = !this._settings.get_boolean('show-banners');
        const enabled = this._isCounterEnabled();
        const stateChanged = enabled !== this._enabled;
        this._enabled = enabled;
        if (stateChanged)
            this.emit('state-changed');
        this._rebuild();
    }

    _rebuild() {
        this._disconnect(this._notificationConnections);
        this._disconnect(this._sourceConnections);
        this._appNotifications = Object.create(null);

        if (this._enabled) {
            this._connect(this._sourceConnections, Main.messageTray,
                'source-added', () => this._rebuild());
            this._connect(this._sourceConnections, Main.messageTray,
                'source-removed', () => this._rebuild());

            for (const source of Main.messageTray.getSources()) {
                this._connect(this._sourceConnections, source,
                    'notification-added', () => this._rebuild());
                for (const notification of source.notifications)
                    this._recordNotification(notification);
            }
        }

        this.emit('changed');
    }

    _recordNotification(notification) {
        const app = notification.source?.app ?? notification.source?._app;
        const appId = app?.id ?? app?._appId;
        if (!appId)
            return;

        if (notification.resident) {
            if (notification.acknowledged)
                return;
            this._connect(this._notificationConnections, notification,
                'notify::acknowledged', () => this._rebuild());
        }

        this._connect(this._notificationConnections, notification,
            'destroy', () => this._rebuild());
        this._appNotifications[appId] =
            (this._appNotifications[appId] ?? 0) + 1;
    }

    _connect(bucket, object, signal, callback) {
        if (!object)
            return;
        bucket.push([object, object.connect(signal, callback)]);
    }

    _disconnect(bucket) {
        for (const [object, id] of bucket.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                console.debug(`[layout-switcher-runtime] signal cleanup: ${error}`);
            }
        }
    }
});
