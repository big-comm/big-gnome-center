// SPDX-License-Identifier: GPL-2.0-or-later

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import * as PanelSettings from '../community-panel@communitybig.org/panelSettings.js';
import * as Utils from '../community-panel@communitybig.org/utils.js';
import {SETTINGS} from '../community-panel@communitybig.org/runtimeContext.js';

const TOPOLOGY_SETTINGS = [
    'changed::primary-monitor',
    'changed::multi-monitors',
    'changed::isolate-monitors',
    'changed::panel-positions',
    'changed::panel-lengths',
    'changed::panel-anchors',
    'changed::stockgs-keep-top-panel',
];

export class TaskbarMonitorHost {
    constructor() {
        this._owner = null;
        this._signals = null;
        this._generation = 0;
        this._resetCount = 0;
        this._resetting = false;
        this._primaryMonitor = -1;
        this._panelMonitors = [];
        this._multiMonitors = false;
        this._refreshGeneration = 0;
        this._resetFailures = 0;
        this._lastError = '';
    }

    createPanels(manager) {
        const primaryIndex = PanelSettings.getPrimaryIndex(
            SETTINGS.get_string('primary-monitor'));
        const primaryMonitor = Main.layoutManager.monitors[primaryIndex] ??
            Main.layoutManager.primaryMonitor;

        manager.allPanels = [];
        manager.primaryPanel = null;
        manager.dtpPrimaryMonitor = primaryMonitor;
        this._multiMonitors = SETTINGS.get_boolean('multi-monitors');

        if (primaryMonitor) {
            manager.primaryPanel = manager._createPanel(
                primaryMonitor,
                SETTINGS.get_boolean('stockgs-keep-top-panel'),
            );
            manager.allPanels.push(manager.primaryPanel);
            manager.serviceHost.activateOverview(
                manager, manager.primaryPanel);
            manager.setFocusedMonitor(primaryMonitor);
        }

        if (this._multiMonitors) {
            for (const monitor of Main.layoutManager.monitors) {
                if (monitor !== primaryMonitor)
                    manager.allPanels.push(manager._createPanel(monitor, true));
            }
        }

        global.dashToPanel.panels = manager.allPanels;
        global.dashToPanel.emit('panels-created');
        this._primaryMonitor = primaryMonitor?.index ?? -1;
        this._panelMonitors = manager.allPanels
            .map(panel => panel.monitor.index);
        this._generation++;
    }

    bind(manager) {
        if (this._owner === manager)
            return;
        this.destroy();
        this._owner = manager;
        this._signals = new Utils.GlobalSignalsHandler();
        this._signals.add(
            [
                SETTINGS,
                TOPOLOGY_SETTINGS,
                (_settings, settingChanged) => {
                    PanelSettings.clearCache(settingChanged);
                    this._reset();
                },
            ],
            [
                Utils.DisplayWrapper.getMonitorManager(),
                'monitors-changed',
                async () => {
                    const owner = this._owner;
                    const refreshGeneration = ++this._refreshGeneration;
                    if (!owner || !Main.layoutManager.primaryMonitor)
                        return;
                    try {
                        await PanelSettings.setMonitorsInfo(SETTINGS);
                    } catch (error) {
                        console.warn(
                            `[layout-switcher-runtime] monitor map refresh failed: ${error}`,
                        );
                    }
                    if (this._owner === owner &&
                        refreshGeneration === this._refreshGeneration) {
                        this._reset();
                    }
                },
            ],
        );
    }

    destroy(owner = null) {
        if (owner && owner !== this._owner)
            return;
        this._signals?.destroy();
        this._signals = null;
        this._owner = null;
        this._resetting = false;
        this._refreshGeneration++;
    }

    diagnostics() {
        return {
            available: true,
            owned: Boolean(this._owner),
            generation: this._generation,
            resetCount: this._resetCount,
            resetting: this._resetting,
            signalGroups: this._signals ? 2 : 0,
            monitorCount: Main.layoutManager.monitors.length,
            primaryMonitor: this._primaryMonitor,
            panelMonitors: this._panelMonitors,
            multiMonitors: this._multiMonitors,
            resetFailures: this._resetFailures,
            lastError: this._lastError,
        };
    }

    _reset() {
        const manager = this._owner;
        if (!manager || this._resetting)
            return;
        this._resetting = true;
        try {
            manager.disable(true);
            manager.enable(true);
            this._resetCount++;
            this._lastError = '';
        } catch (error) {
            this._resetFailures++;
            this._lastError = `${error}`;
            throw error;
        } finally {
            this._resetting = false;
        }
    }
}
