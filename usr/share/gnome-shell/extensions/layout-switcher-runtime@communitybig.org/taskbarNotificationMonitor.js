/*
 * This file is part of the Dash-To-Panel extension for Gnome 3
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 */

import Gio from 'gi://Gio';
import Shell from 'gi://Shell';

import {EventEmitter} from 'resource:///org/gnome/shell/misc/signals.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';

const UNITY_BUS_NAME = 'com.canonical.Unity';
const UNITY_LAUNCHER_INTERFACE = 'com.canonical.Unity.LauncherEntry';
const UNITY_LAUNCHER_UPDATE = 'Update';

const KNOWN_ID_MAPPINGS = new Map([
    ['org.gnome.Evolution', [/^org\.gnome\.[eE]volution([.-].+)?$/]],
]);

export class TaskbarNotificationMonitor extends EventEmitter {
    constructor() {
        super();

        this._tracker = Shell.WindowTracker.get_default();
        this._state = Object.create(null);
        this._sourceRecords = new Map();
        this._focusSignalId = 0;
        this._traySignalIds = [];
        this._launcherEntryId = 0;
        this._unityBusId = 0;
        this._updateCount = 0;
        this._lastUpdateApp = '';
        this._destroyed = false;

        try {
            this._launcherEntryId = Gio.DBus.session.signal_subscribe(
                null,
                UNITY_LAUNCHER_INTERFACE,
                UNITY_LAUNCHER_UPDATE,
                null,
                null,
                Gio.DBusSignalFlags.NONE,
                (_connection, senderName, _objectPath, _interfaceName,
                    _signalName, parameters) =>
                    this._handleLauncherUpdate(senderName, parameters),
            );
            this._focusSignalId = this._tracker.connect(
                'notify::focus-app',
                () => this._handleFocusApp(),
            );
            this._traySignalIds = [
                Main.messageTray.connect(
                    'source-added',
                    (_tray, source) => this._trackSource(source),
                ),
                Main.messageTray.connect(
                    'source-removed',
                    (_tray, source) => this._untrackSource(source),
                ),
            ];
            this._unityBusId = Gio.DBus.session.own_name(
                UNITY_BUS_NAME,
                Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT,
                null,
                null,
            );
            for (const source of Main.messageTray.getSources())
                this._trackSource(source);
        } catch (error) {
            this.destroy();
            throw error;
        }
    }

    getState(app) {
        return this._state?.[app?.id];
    }

    diagnostics() {
        const states = Object.entries(this._state ?? {});
        return {
            implementation: 'layout-switcher-runtime',
            connected: Boolean(
                !this._destroyed &&
                this._focusSignalId &&
                this._traySignalIds.length === 2
            ),
            launcherSubscriptionOwned: Boolean(this._launcherEntryId),
            unityBusOwned: Boolean(this._unityBusId),
            trackedSources: this._sourceRecords.size,
            stateApps: states.length,
            totalNotifications: states.reduce(
                (total, [_appId, state]) => total + (Number(state.total) || 0),
                0,
            ),
            urgentApps: states
                .filter(([_appId, state]) => state.urgent)
                .map(([appId]) => appId),
            updateCount: this._updateCount,
            lastUpdateApp: this._lastUpdateApp,
        };
    }

    destroy() {
        if (this._destroyed)
            return;
        this._destroyed = true;

        for (const source of [...this._sourceRecords.keys()])
            this._untrackSource(source, false);
        this._sourceRecords.clear();

        for (const id of this._traySignalIds.splice(0))
            this._disconnect(Main.messageTray, id);
        if (this._focusSignalId) {
            this._disconnect(this._tracker, this._focusSignalId);
            this._focusSignalId = 0;
        }
        if (this._launcherEntryId) {
            Gio.DBus.session.signal_unsubscribe(this._launcherEntryId);
            this._launcherEntryId = 0;
        }
        if (this._unityBusId) {
            Gio.DBus.session.unown_name(this._unityBusId);
            this._unityBusId = 0;
        }

        this._tracker = null;
        this._state = null;
    }

    _handleFocusApp() {
        const app = this._tracker?.focus_app;
        if (!app || !this._state[app.id])
            return;
        this._updateState(app.id, this._defaultState(), true);
    }

    _handleLauncherUpdate(senderName, parameters) {
        if (!senderName || !parameters)
            return;

        const [appUri, properties] = parameters.deep_unpack();
        const appId = appUri.replace(/(^\w+:|^)\/\//, '');
        const updates = {};
        for (const property in properties)
            updates[property] = properties[property].unpack();
        this._updateState(appId, updates);
    }

    _trackSource(source) {
        if (!source || this._sourceRecords.has(source))
            return;

        const appId = this._sourceAppId(source);
        if (!appId)
            return;

        const signalId = source.connect(
            'notify::count',
            () => this._recomputeTrayState(appId),
        );
        this._sourceRecords.set(source, {appId, signalId});
        this._recomputeTrayState(appId);
    }

    _untrackSource(source, updateState = true) {
        const record = this._sourceRecords.get(source);
        if (!record)
            return;
        this._disconnect(source, record.signalId);
        this._sourceRecords.delete(source);
        if (updateState)
            this._recomputeTrayState(record.appId);
    }

    _recomputeTrayState(appId) {
        let trayCount = 0;
        let trayUrgent = false;
        for (const [source, record] of this._sourceRecords) {
            if (record.appId !== appId)
                continue;
            trayCount += Number(source.count) || 0;
            trayUrgent ||= (source.notifications ?? []).some(notification =>
                notification.urgency > MessageTray.Urgency.NORMAL ||
                source.constructor.name === 'WindowAttentionSource');
        }
        this._updateState(appId, {trayCount, trayUrgent}, true);
    }

    _sourceAppId(source) {
        const appId = source?._appId || source?.app?.id ||
            (source?.policy instanceof MessageTray.NotificationApplicationPolicy &&
                source.policy.id);
        return this._normalizeAppId(appId);
    }

    _updateState(rawAppId, updates, ignoreMapping = false) {
        const appId = this._normalizeAppId(rawAppId, !ignoreMapping);
        if (!appId)
            return;

        this._state[appId] ??= this._defaultState();
        const previous = JSON.stringify(this._state[appId]);
        const state = this._state[appId];
        if (Object.hasOwn(updates, 'urgent'))
            state.unityUrgent = Boolean(updates.urgent);
        Object.assign(state, updates);

        const focusedAppId = this._normalizeAppId(
            this._tracker?.focus_app?.id, false);
        if (focusedAppId === appId) {
            state.count = 0;
            state.trayCount = 0;
        }

        state.urgent = Boolean(
            state.unityUrgent || (state.trayUrgent && state.trayCount));
        state.total = (state['count-visible'] ? Number(state.count) || 0 : 0) +
            (Number(state.trayCount) || 0);

        if (previous === JSON.stringify(state))
            return;
        this._updateCount++;
        this._lastUpdateApp = appId;
        this.emit(`update-${appId}`);
    }

    _defaultState() {
        return {
            count: 0,
            trayCount: 0,
            trayUrgent: false,
            unityUrgent: false,
            urgent: false,
            total: 0,
        };
    }

    _normalizeAppId(rawAppId, applyMappings = true) {
        if (typeof rawAppId !== 'string' || !rawAppId)
            return '';
        let appId = rawAppId.replace(/\.desktop$/, '');
        if (applyMappings && !KNOWN_ID_MAPPINGS.has(appId)) {
            appId = [...KNOWN_ID_MAPPINGS].find(([_canonical, patterns]) =>
                patterns.some(pattern => pattern.test(appId)))?.[0] ?? appId;
        }
        return `${appId}.desktop`;
    }

    _disconnect(object, id) {
        if (!object || !id)
            return;
        try {
            object.disconnect(id);
        } catch (error) {
            console.debug(
                `[layout-switcher-runtime] notification signal cleanup: ${error}`,
            );
        }
    }
}
