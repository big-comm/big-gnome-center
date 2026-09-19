// SPDX-License-Identifier: GPL-2.0-or-later
// Big Gnome Center ownership boundary for the inherited Taskbar/Panel surface.

import GLib from 'gi://GLib';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {EventEmitter} from 'resource:///org/gnome/shell/misc/signals.js';

import * as PanelManager from './taskbar/panelManager.js';
import * as PanelSettings from './taskbar/panelSettings.js';
import * as Context from './taskbar/runtimeContext.js';
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
        this._generation = 0;
        this._manager = null;
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
        if (this._enabling || this._destroying)
            throw new Error('Taskbar surface lifecycle operation already pending');
        if (this._manager)
            return;

        const generation = ++this._generation;
        this._enabling = true;
        try {
            Context.initializeRuntimeContext(this._host, this);
            this._ownsResources = true;
            this.statusFullscreen = new TaskbarStatusFullscreenIntegration(
                Context.SETTINGS);
            this.panelHost = new TaskbarPanelHost(
                this.statusAreaHost, this.statusFullscreen);
            this.appActions = new TaskbarAppActions(Context.SETTINGS);
            this.interactions = new TaskbarInteractions();
            this.indicatorRenderer = new TaskbarIndicatorRenderer(Context.SETTINGS);
            this._global = new EventEmitter();
            global.dashToPanel = this._global;
            await PanelSettings.init(Context.SETTINGS);
            if (generation !== this._generation)
                return;

            PanelSettings.adjustMonitorSettings(Context.SETTINGS);
            this.setPanelHeight(panelHeight);
            this.enableGlobalStyles();

            if (!await this._settleUbuntuDock(generation) || generation !== this._generation)
                return;
            this._createManager();
        } catch (error) {
            if (generation === this._generation && Context.DTP_EXTENSION === this)
                this.destroy();
            throw error;
        } finally {
            if (generation === this._generation)
                this._enabling = false;
        }
    }

    destroy() {
        if (this._destroying || (!this._ownsResources && Context.DTP_EXTENSION !== this))
            return;
        this._destroying = true;
        this._ownsResources = false;
        this._enabling = false;
        this._generation++;
        const manager = this._manager;
        this._manager = null;
        const cleanup = (name, action) => {
            try {
                action();
            } catch (error) {
                console.warn(`[layout-switcher-runtime] Taskbar ${name} cleanup failed: ${error}`);
            }
        };
        cleanup('delay', () => this._cancelUbuntuDockDelay());
        cleanup('monitors', () => this.monitorHost.destroy(manager));
        cleanup('manager', () => { manager?.disable(); });
        cleanup('services', () => this.serviceHost.destroy(manager));
        cleanup('hooks', () => this.shellHooks.destroy(manager));
        cleanup('panels', () => this.panelHost?.releaseAll());
        cleanup('fullscreen', () => this.statusFullscreen?.destroy());
        cleanup('status area', () => this.statusAreaHost.restore());
        if (Context.DTP_EXTENSION === this) {
            cleanup('cache', () => PanelSettings.clearCache());
            cleanup('styles', () => this.disableGlobalStyles());
        }
        cleanup('app actions', () => this.appActions?.destroy());
        cleanup('interactions', () => this.interactions?.destroy());
        cleanup('indicators', () => this.indicatorRenderer?.destroy());
        this.appActions = null;
        this.interactions = null;
        this.indicatorRenderer = null;
        this.panelHost = null;
        this.statusFullscreen = null;

        if (global.dashToPanel === this._global)
            delete global.dashToPanel;
        this._global = null;
        Context.clearRuntimeContext(this);
        this._destroying = false;
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
            rendererImplementation: this._manager
                ? 'layout-switcher-runtime'
                : '',
            rendererModules: this._manager ? 13 : 0,
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
            const id = GLib.timeout_add(
                GLib.PRIORITY_DEFAULT,
                UBUNTU_DOCK_SETTLE_MS,
                () => {
                    if (this._ubuntuDockDelayId !== id)
                        return GLib.SOURCE_REMOVE;
                    this._ubuntuDockDelayId = 0;
                    this._ubuntuDockDelayResolve = null;
                    resolve(generation === this._generation);
                    return GLib.SOURCE_REMOVE;
                },
            );
            this._ubuntuDockDelayId = id;
        });
    }

    _cancelUbuntuDockDelay() {
        const id = this._ubuntuDockDelayId;
        const resolve = this._ubuntuDockDelayResolve;
        this._ubuntuDockDelayId = 0;
        this._ubuntuDockDelayResolve = null;
        try {
            if (id)
                GLib.Source.remove(id);
        } finally {
            resolve?.(false);
        }
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
