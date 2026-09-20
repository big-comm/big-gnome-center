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
import {MAX_REMOTE_ENTRIES, parseLauncherUpdate} from './launcherEntry.js';

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
        this._remoteMaps = new Map();
        this._remoteCount = 0;
        this._nameOwnerId = 0;
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.notifications'});
        this._dndMode = !this._settings.get_boolean('show-banners');
        this._settingsId = 0;

        try {
            this._settingsId = this._settings.connect('changed::show-banners', () => {
                if (this._destroyed) return;
                this._dndMode = !this._settings.get_boolean('show-banners');
                for (const appId of Object.keys(this._state))
                    this._recomputeTrayState(appId);
            });
            this._nameOwnerId = Gio.DBus.session.signal_subscribe(
                'org.freedesktop.DBus', 'org.freedesktop.DBus', 'NameOwnerChanged',
                '/org/freedesktop/DBus', null, Gio.DBusSignalFlags.NONE,
                (_connection, _sender, _path, _iface, _signal, parameters) => {
                    const [name, before, after] = parameters.deep_unpack();
                    if (name === before && !after) this._removeSender(before);
                });
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
        return this._state?.[app?.id] ?? this._defaultState();
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
        this._disconnect(this._settings, this._settingsId);
        this._settingsId = 0;
        this._settings?.run_dispose?.();
        this._settings = null;
        if (this._nameOwnerId) Gio.DBus.session.signal_unsubscribe(this._nameOwnerId);
        this._nameOwnerId = 0;
        this._remoteMaps.clear();
        this._remoteCount = 0;

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
        if (this._destroyed || !app || !this._state[app.id])
            return;
        this._updateState(app.id, this._defaultState(), true);
    }

    _handleLauncherUpdate(senderName, parameters) {
        if (this._destroyed || !parameters)
            return;
        let parsed;
        try { parsed = parseLauncherUpdate(senderName, ...parameters.deep_unpack()); } catch { return; }
        if (!parsed) return;
        const appId = this._normalizeAppId(parsed.appId);
        let records = this._remoteMaps.get(senderName);
        if (!records?.has(appId) && this._remoteCount >= MAX_REMOTE_ENTRIES) return;
        if (!records) this._remoteMaps.set(senderName, records = new Map());
        if (!records.has(appId)) this._remoteCount++;
        const state = {...records.get(appId), ...parsed.updates};
        records.set(appId, state);
        this._remoteMaps.delete(senderName);
        this._remoteMaps.set(senderName, records);
        this._recomputeRemote(appId);
    }

    _removeSender(sender) {
        if (this._destroyed) return;
        const records = this._remoteMaps.get(sender);
        if (!records) return;
        this._remoteMaps.delete(sender);
        this._remoteCount -= records.size;
        for (const appId of records.keys()) this._recomputeRemote(appId);
    }

    _recomputeRemote(appId) {
        let remote = {};
        for (const records of this._remoteMaps.values())
            if (records.has(appId)) remote = records.get(appId);
        this._updateState(appId, {count: 0, 'count-visible': false, urgent: false,
            progress: 0, 'progress-visible': false, updating: false, ...remote}, true);
    }

    _trackSource(source) {
        if (this._destroyed || !source || this._sourceRecords.has(source))
            return;

        const appId = this._sourceAppId(source);
        if (!appId)
            return;

        const record = {appId, signals: [], notifications: []};
        const refresh = () => {
            if (this._destroyed || this._sourceRecords.get(source) !== record) return;
            for (const [object, id] of record.notifications.splice(0)) this._disconnect(object, id);
            for (const notification of source.notifications ?? []) {
                for (const signal of ['notify::urgency', 'notify::acknowledged', 'notify::resident'])
                    record.notifications.push([notification, notification.connect(signal, () => {
                        if (!this._destroyed && this._sourceRecords.get(source) === record)
                            this._recomputeTrayState(appId);
                    })]);
            }
            this._recomputeTrayState(appId);
        };
        this._sourceRecords.set(source, record);
        for (const signal of ['notify::count', 'notification-added'])
            record.signals.push(source.connect(signal, refresh));
        refresh();
    }

    _untrackSource(source, updateState = true) {
        const record = this._sourceRecords.get(source);
        if (!record)
            return;
        this._sourceRecords.delete(source);
        for (const id of record.signals) this._disconnect(source, id);
        for (const [object, id] of record.notifications) this._disconnect(object, id);
        if (updateState)
            this._recomputeTrayState(record.appId);
    }

    _recomputeTrayState(appId) {
        if (this._destroyed) return;
        let trayCount = 0;
        let trayUrgent = false;
        for (const [source, record] of this._sourceRecords) {
            if (this._dndMode || record.appId !== appId)
                continue;
            const notifications = (source.notifications ?? []).filter(notification =>
                !notification.resident || !notification.acknowledged);
            trayCount += notifications.length;
            trayUrgent ||= notifications.some(notification =>
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
        if (this._destroyed) return;
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
            !this._dndMode && (state.unityUrgent || (state.trayUrgent && state.trayCount)));
        state.total = (state['count-visible'] ? Number(state.count) || 0 : 0) +
            (Number(state.trayCount) || 0);

        if (!state.total && !state.urgent && !state['progress-visible'] && !state.updating &&
            ![...this._sourceRecords.values()].some(record => record.appId === appId) &&
            ![...this._remoteMaps.values()].some(records => records.has(appId)))
            delete this._state[appId];
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
