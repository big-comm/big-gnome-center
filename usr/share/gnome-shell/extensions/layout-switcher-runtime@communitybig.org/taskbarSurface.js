// SPDX-License-Identifier: GPL-2.0-or-later
// Layout Switcher ownership boundary for the inherited Taskbar/Panel surface.

import GLib from 'gi://GLib';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {EventEmitter} from 'resource:///org/gnome/shell/misc/signals.js';

import * as PanelManager from '../community-panel@communitybig.org/panelManager.js';
import * as PanelSettings from '../community-panel@communitybig.org/panelSettings.js';
import * as Context from '../community-panel@communitybig.org/runtimeContext.js';
import {TaskbarAppActions} from './taskbarAppActions.js';
import {TaskbarInteractions} from './taskbarInteractions.js';
import {TaskbarIndicatorRenderer} from './taskbarIndicatorRenderer.js';
import {TaskbarMonitorHost} from './taskbarMonitorHost.js';
import {TaskbarPanelHost} from './taskbarPanelHost.js';
import {TaskbarServiceHost} from './taskbarServiceHost.js';
import {TaskbarShellHooks} from './taskbarShellHooks.js';
import {TaskbarStatusAreaHost} from './taskbarStatusArea.js';
import {TaskbarStatusFullscreenIntegration} from './taskbarStatusFullscreenIntegration.js';

const UBUNTU_DOCK_UUID = 'ubuntu-dock@ubuntu.com';
const UBUNTU_DOCK_SETTLE_MS = 200;

export class TaskbarSurfaceManager {
    constructor(host) {
        this._host = host;
        this._realHasOverview = Main.sessionMode.hasOverview;
        this._realStartInOverview = Main.layoutManager.startInOverview;
        this._generation = 0;
        this._manager = null;
        this._startupCompleteHandler = 0;
        this._ubuntuDockDelayId = 0;
        this._ubuntuDockDelayResolve = null;
        this._global = null;
        this.appActions = null;
        this.interactions = null;
        this.indicatorRenderer = null;
        this.statusAreaHost = new TaskbarStatusAreaHost();
        this.statusFullscreen = null;
        this.panelHost = null;
        this.monitorHost = new TaskbarMonitorHost();
        this.serviceHost = new TaskbarServiceHost();
        this.shellHooks = new TaskbarShellHooks();
    }

    async enable(panelHeight) {
        if (this._manager)
            return;

        const generation = ++this._generation;
        Context.initializeRuntimeContext(this._host, this);
        this.statusFullscreen = new TaskbarStatusFullscreenIntegration(
            Context.SETTINGS);
        this.panelHost = new TaskbarPanelHost(
            this.statusAreaHost, this.statusFullscreen);
        this.appActions = new TaskbarAppActions(Context.SETTINGS);
        this.interactions = new TaskbarInteractions();
        this.indicatorRenderer = new TaskbarIndicatorRenderer(Context.SETTINGS);
        this._global = new EventEmitter();
        global.dashToPanel = this._global;

        try {
            await PanelSettings.init(Context.SETTINGS);
            if (generation !== this._generation)
                return;

            PanelSettings.adjustMonitorSettings(Context.SETTINGS);
            this.setPanelHeight(panelHeight);
            this._configureOverview();
            this.enableGlobalStyles();

            if (!await this._settleUbuntuDock(generation))
                return;
            this._createManager();
        } catch (error) {
            this.destroy();
            throw error;
        }
    }

    destroy() {
        this._generation++;
        this._cancelUbuntuDockDelay();

        const manager = this._manager;
        this._manager = null;
        this.monitorHost.destroy(manager);
        try {
            manager?.disable();
        } catch (error) {
            console.warn(
                `[layout-switcher-runtime] Taskbar manager cleanup failed: ${error}`,
            );
        } finally {
            this.serviceHost.destroy(manager);
            this.shellHooks.destroy(manager);
            this.panelHost?.releaseAll();
            this.statusFullscreen?.destroy();
            this.statusAreaHost.restore();
        }

        PanelSettings.clearCache();
        this.disableGlobalStyles();
        this.appActions?.destroy();
        this.appActions = null;
        this.interactions?.destroy();
        this.interactions = null;
        this.indicatorRenderer?.destroy();
        this.indicatorRenderer = null;
        this.panelHost = null;
        this.statusFullscreen = null;

        if (this._startupCompleteHandler) {
            try {
                Main.layoutManager.disconnect(this._startupCompleteHandler);
            } catch (error) {
                // Shell teardown may dispose the layout manager first.
            }
            this._startupCompleteHandler = 0;
        }
        Main.sessionMode.hasOverview = this._realHasOverview;
        Main.layoutManager.startInOverview = this._realStartInOverview;

        if (global.dashToPanel === this._global)
            delete global.dashToPanel;
        this._global = null;
        Context.clearRuntimeContext(this);
    }

    panels() {
        return this._manager?.allPanels ?? [];
    }

    setPanelHeight(panelHeight) {
        if (!Number.isInteger(panelHeight))
            return;
        const indexes = this._manager
            ? this._manager.allPanels.map(panel => panel.monitor.index)
            : Main.layoutManager.monitors.map((_monitor, index) => index);
        for (const index of new Set(indexes))
            PanelSettings.setPanelSize(Context.SETTINGS, index, panelHeight);
    }

    diagnostics() {
        return {
            managerOwned: Boolean(this._manager),
            appActionsOwned: Boolean(this.appActions),
            appActions: this.appActions?.diagnostics() ?? {},
            interactionsOwned: Boolean(this.interactions),
            interactions: this.interactions?.diagnostics() ?? {},
            indicatorRendererOwned: Boolean(this.indicatorRenderer),
            indicatorRenderer: this.indicatorRenderer?.diagnostics() ?? {},
            panelHost: this.panelHost?.diagnostics() ?? {},
            monitorHost: this.monitorHost.diagnostics(),
            serviceHost: this.serviceHost.diagnostics(),
            shellHooks: this.shellHooks.diagnostics(),
            statusFullscreen: this.statusFullscreen?.diagnostics() ?? {},
            statusArea: this.statusAreaHost.diagnostics(
                this.panels().map(panel => panel.panelBox)),
            activationPending: Boolean(this._ubuntuDockDelayId),
            globalOwned: Boolean(
                this._global && global.dashToPanel === this._global),
        };
    }

    resetGlobalStyles() {
        this.disableGlobalStyles();
        this.enableGlobalStyles();
    }

    enableGlobalStyles() {
        const radius = Context.SETTINGS?.get_int('global-border-radius') ?? 0;
        if (radius) {
            Main.layoutManager.uiGroup.add_style_class_name(
                `br${radius * 4}`,
            );
        }
    }

    disableGlobalStyles() {
        for (const name of ['br4', 'br8', 'br12', 'br16', 'br20'])
            Main.layoutManager.uiGroup.remove_style_class_name(name);
    }

    _configureOverview() {
        const hideOverview = Context.SETTINGS.get_boolean(
            'hide-overview-on-startup');
        Main.layoutManager.startInOverview = !hideOverview;
        if (!hideOverview || !Main.layoutManager._startingUp)
            return;

        Main.sessionMode.hasOverview = false;
        this._startupCompleteHandler = Main.layoutManager.connect(
            'startup-complete',
            () => {
                const id = this._startupCompleteHandler;
                this._startupCompleteHandler = 0;
                Main.sessionMode.hasOverview = this._realHasOverview;
                Main.layoutManager.disconnect(id);
            },
        );
    }

    async _settleUbuntuDock(generation) {
        if (!Main.extensionManager._extensionOrder.includes(UBUNTU_DOCK_UUID))
            return true;

        const disabled = global.settings.get_strv('disabled-extensions');
        if (disabled.includes(UBUNTU_DOCK_UUID))
            return true;

        global.settings.set_strv(
            'disabled-extensions',
            [...disabled, UBUNTU_DOCK_UUID],
        );
        return await new Promise(resolve => {
            this._ubuntuDockDelayResolve = resolve;
            this._ubuntuDockDelayId = GLib.timeout_add(
                GLib.PRIORITY_DEFAULT,
                UBUNTU_DOCK_SETTLE_MS,
                () => {
                    this._ubuntuDockDelayId = 0;
                    this._ubuntuDockDelayResolve = null;
                    resolve(generation === this._generation);
                    return GLib.SOURCE_REMOVE;
                },
            );
        });
    }

    _cancelUbuntuDockDelay() {
        if (this._ubuntuDockDelayId) {
            GLib.Source.remove(this._ubuntuDockDelayId);
            this._ubuntuDockDelayId = 0;
        }
        this._ubuntuDockDelayResolve?.(false);
        this._ubuntuDockDelayResolve = null;
    }

    _createManager() {
        const manager = new PanelManager.PanelManager(
            this.panelHost, this.monitorHost, this.shellHooks,
            this.serviceHost);
        this._manager = manager;
        manager.enable();
        this.monitorHost.bind(manager);
        for (const panel of manager.allPanels)
            this.interactions.adoptPreviewMenu(panel, panel.taskbar.previewMenu);
    }
}
