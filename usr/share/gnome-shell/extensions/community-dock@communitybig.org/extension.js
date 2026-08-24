// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-
// Community Dock fork, 2026-08-19: distinct bundled extension identity.

import {DockManager} from './docking.js';
import {PanelController} from './panelController.js';
import {Extension} from './dependencies/shell/extensions/extension.js';

// We export this so it can be accessed by other extensions
export let dockManager;

export class CommunityDockRuntime {
    constructor(extension) {
        this._extension = extension;
        this._manager = null;
    }

    enable() {
        if (this._manager)
            return;
        if (dockManager)
            throw new Error('Community Dock lifecycle already owned');
        if (!this._extension.notificationsMonitor)
            throw new Error('Layout Switcher notification monitor is required');
        if (!this._extension.createIndicatorController)
            throw new Error('Layout Switcher indicator controller is required');

        let manager = null;
        try {
            manager = new DockManager(this._extension);
            this._manager = manager;
            dockManager = manager;
            this._indicatorController = this._extension.createIndicatorController(manager);
            this._panelController = new PanelController(this._extension);
        } catch (error) {
            const partialManager = manager ?? DockManager.getDefault();
            this._panelController?.destroy();
            this._panelController = null;
            this._indicatorController?.destroy();
            this._indicatorController = null;
            try {
                partialManager?.destroy();
            } catch (cleanupError) {
                console.warn(`[community-dock] partial startup cleanup failed: ${cleanupError}`);
            }
            if (dockManager === manager)
                dockManager = null;
            this._manager = null;
            throw error;
        }
    }

    disable() {
        const manager = this._manager;
        this._panelController?.destroy();
        this._panelController = null;
        this._indicatorController?.destroy();
        this._indicatorController = null;
        manager?.destroy();
        this._manager = null;
        if (dockManager === manager)
            dockManager = null;
    }

    get active() {
        return Boolean(this._manager);
    }

    get docks() {
        return this._manager?._allDocks ?? [];
    }
}

export default class CommunityDockExtension extends Extension.Extension {
    enable() {
        // TODO: Remove this when upstream will disable extensions on shutdown
        // See: https://gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/4214
        this._shutdownID = global.connect('shutdown', () => this.disable());
        this._runtime = new CommunityDockRuntime(this);
        this._runtime.enable();
    }

    disable() {
        if (this._shutdownID) {
            global.disconnect(this._shutdownID);
            delete this._shutdownID;
        }
        this._runtime?.disable();
        this._runtime = null;
    }
}
