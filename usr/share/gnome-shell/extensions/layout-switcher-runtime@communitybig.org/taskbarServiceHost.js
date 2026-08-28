// SPDX-License-Identifier: GPL-2.0-or-later

import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {NotificationsMonitor} from '../community-panel@communitybig.org/notificationsMonitor.js';
import * as Overview from '../community-panel@communitybig.org/overview.js';
import * as Panel from '../community-panel@communitybig.org/panel.js';
import * as PanelSettings from '../community-panel@communitybig.org/panelSettings.js';
import * as Utils from '../community-panel@communitybig.org/utils.js';
import {DTP_EXTENSION, SETTINGS} from '../community-panel@communitybig.org/runtimeContext.js';
import {DesktopIconsUsableAreaClass} from './desktopIconsUsableArea.js';

const INTELLIHIDE_KEYBINDING = 'intellihide-key-toggle';
const TASKBAR_MARGIN_OWNER = 'community-panel@communitybig.org';

export class TaskbarServiceHost {
    constructor() {
        this._owner = null;
        this._overview = null;
        this._overviewActive = false;
        this._notificationsMonitor = null;
        this._desktopIconsUsableArea = null;
        this._signals = null;
        this._desktopMarginsIdleId = 0;
        this._desktopMargins = {};
        this._keybindingOwned = false;
        this._generation = 0;
        this._desktopMarginUpdates = 0;
        this._activationFailures = 0;
        this._lastError = '';
    }

    prepare(manager) {
        if (this._owner === manager)
            return;
        this.destroy();
        this._owner = manager;
        this._overview = new Overview.Overview(manager);
        manager.overview = this._overview;
        this._generation++;
    }

    activateOverview(manager, primaryPanel) {
        this._requireOwner(manager);
        if (this._overviewActive)
            return;
        try {
            this._overview.enable(primaryPanel);
            this._overviewActive = true;
            this._lastError = '';
        } catch (error) {
            this._activationFailures++;
            this._lastError = `${error}`;
            try {
                this._overview.disable();
            } catch (cleanupError) {
                console.warn(
                    `[layout-switcher-runtime] partial overview cleanup failed: ${cleanupError}`,
                );
            }
            throw error;
        }
    }

    activate(manager) {
        this._requireOwner(manager);
        if (this._notificationsMonitor || this._desktopIconsUsableArea)
            return;

        try {
            this._notificationsMonitor = new NotificationsMonitor();
            manager.notificationsMonitor = this._notificationsMonitor;
            this._desktopIconsUsableArea = new DesktopIconsUsableAreaClass(
                TASKBAR_MARGIN_OWNER);
            this.updateDesktopIconsMargins(manager);
            this._lastError = '';
        } catch (error) {
            this._activationFailures++;
            this._lastError = `${error}`;
            this._destroyNotifications(manager);
            this._destroyDesktopIcons();
            throw error;
        }
    }

    bind(manager) {
        this._requireOwner(manager);
        if (this._signals)
            return;

        try {
            this._signals = new Utils.GlobalSignalsHandler();
            manager._signalsHandler = this._signals;
            this._signals.add(
                [
                    SETTINGS,
                    'changed::global-border-radius',
                    () => DTP_EXTENSION.resetGlobalStyles(),
                ],
                [
                    SETTINGS,
                    'changed::panel-element-positions',
                    () => {
                        PanelSettings.clearCache('panel-element-positions');
                        manager._updatePanelElementPositions();
                    },
                ],
                [
                    SETTINGS,
                    'changed::intellihide-key-toggle-text',
                    () => this._setKeyBinding(manager, true),
                ],
                [
                    SETTINGS,
                    'changed::panel-sizes',
                    () => this._queueDesktopIconsMargins(manager),
                ],
            );

            for (const boxName of Panel.panelBoxes) {
                this._signals.add([
                    Main.panel[boxName],
                    'child-added',
                    (_parent, child) => {
                        if (manager.primaryPanel && child instanceof St.Bin) {
                            manager._adjustPanelMenuButton(
                                manager._getPanelMenuButton(
                                    child.get_first_child()),
                                manager.primaryPanel.monitor,
                                manager.primaryPanel.geom.position,
                            );
                        }
                    },
                ]);
            }

            this._setKeyBinding(manager, true);
            this._lastError = '';
        } catch (error) {
            this._activationFailures++;
            this._lastError = `${error}`;
            this.unbind(manager);
            throw error;
        }
    }

    releasePanels(manager) {
        if (manager !== this._owner || !this._overviewActive)
            return;
        this._overview.disable();
        this._overviewActive = false;
    }

    unbind(manager) {
        if (manager !== this._owner)
            return;
        this._cancelDesktopMarginsIdle();
        this._setKeyBinding(manager, false);
        this._destroyNotifications(manager);
        const signals = this._signals;
        signals?.destroy();
        this._signals = null;
        if (manager._signalsHandler === signals)
            manager._signalsHandler = null;
    }

    destroy(owner = null) {
        if (owner && owner !== this._owner)
            return;
        const manager = this._owner;
        if (manager) {
            try {
                this.releasePanels(manager);
            } catch (error) {
                console.warn(
                    `[layout-switcher-runtime] overview cleanup failed: ${error}`,
                );
            }
            this.unbind(manager);
        } else {
            this._cancelDesktopMarginsIdle();
        }
        this._destroyDesktopIcons();
        if (manager?.overview === this._overview)
            manager.overview = null;
        this._overview = null;
        this._overviewActive = false;
        this._owner = null;
        this._desktopMargins = {};
    }

    updateDesktopIconsMargins(manager) {
        if (manager !== this._owner)
            return;
        const margins = {};
        this._desktopIconsUsableArea?.resetMargins();
        for (const panel of manager.allPanels) {
            const values = {top: 0, bottom: 0, left: 0, right: 0};
            switch (panel.geom.position) {
            case St.Side.TOP:
                values.top = panel.geom.outerSize;
                break;
            case St.Side.BOTTOM:
                values.bottom = panel.geom.outerSize;
                break;
            case St.Side.LEFT:
                values.left = panel.geom.outerSize;
                break;
            case St.Side.RIGHT:
                values.right = panel.geom.outerSize;
                break;
            }
            margins[panel.monitor.index] = values;
            this._desktopIconsUsableArea?.setMargins(
                panel.monitor.index,
                values.top,
                values.bottom,
                values.left,
                values.right,
            );
        }
        this._desktopMargins = margins;
        if (this._desktopIconsUsableArea)
            this._desktopMarginUpdates++;
    }

    diagnostics() {
        return {
            available: true,
            owned: Boolean(this._owner),
            active: Boolean(
                this._overviewActive &&
                this._notificationsMonitor &&
                this._desktopIconsUsableArea &&
                this._signals &&
                this._keybindingOwned
            ),
            generation: this._generation,
            overviewOwned: Boolean(this._overview),
            overviewActive: this._overviewActive,
            notificationsOwned: Boolean(this._notificationsMonitor),
            launcherSubscriptionOwned:
                Boolean(this._notificationsMonitor?._launcherEntryId),
            unityBusOwned: Boolean(this._notificationsMonitor?._unityBusId),
            notificationApps:
                Object.keys(this._notificationsMonitor?._state ?? {}).length,
            desktopIconsOwned: Boolean(this._desktopIconsUsableArea),
            desktopMarginsPending: Boolean(this._desktopMarginsIdleId),
            desktopMargins: this._desktopMargins,
            desktopMarginUpdates: this._desktopMarginUpdates,
            desktopBridge:
                this._desktopIconsUsableArea?.diagnostics() ?? {},
            signalsOwned: Boolean(this._signals),
            signalGroups: this._signals ? 7 : 0,
            keybindingOwned: this._keybindingOwned,
            activationFailures: this._activationFailures,
            lastError: this._lastError,
        };
    }

    _queueDesktopIconsMargins(manager) {
        this._cancelDesktopMarginsIdle();
        this._desktopMarginsIdleId = GLib.idle_add(
            GLib.PRIORITY_LOW,
            () => {
                this._desktopMarginsIdleId = 0;
                this.updateDesktopIconsMargins(manager);
                return GLib.SOURCE_REMOVE;
            },
        );
    }

    _cancelDesktopMarginsIdle() {
        if (!this._desktopMarginsIdleId)
            return;
        GLib.Source.remove(this._desktopMarginsIdleId);
        this._desktopMarginsIdleId = 0;
    }

    _setKeyBinding(manager, enable) {
        Utils.removeKeybinding(INTELLIHIDE_KEYBINDING);
        this._keybindingOwned = false;
        if (!enable)
            return;
        Utils.addKeybinding(
            INTELLIHIDE_KEYBINDING,
            SETTINGS,
            () => manager.allPanels.forEach(panel =>
                panel.intellihide.toggle()),
            Shell.ActionMode.NORMAL,
        );
        this._keybindingOwned = true;
    }

    _destroyNotifications(manager) {
        const monitor = this._notificationsMonitor;
        try {
            monitor?.destroy();
        } catch (error) {
            console.warn(
                `[layout-switcher-runtime] notification monitor cleanup failed: ${error}`,
            );
        }
        this._notificationsMonitor = null;
        if (manager?.notificationsMonitor === monitor)
            manager.notificationsMonitor = null;
    }

    _destroyDesktopIcons() {
        try {
            this._desktopIconsUsableArea?.destroy();
        } catch (error) {
            console.warn(
                `[layout-switcher-runtime] desktop margins cleanup failed: ${error}`,
            );
        }
        this._desktopIconsUsableArea = null;
    }

    _requireOwner(manager) {
        if (manager !== this._owner)
            throw new Error('Taskbar services are not prepared for this manager');
    }
}
