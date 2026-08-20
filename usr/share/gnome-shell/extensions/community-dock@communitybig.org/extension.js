// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-
// Community Dock fork, 2026-08-19: distinct bundled extension identity.

import {DockManager} from './docking.js';
import {IndicatorController} from './indicatorController.js';
import {PanelController} from './panelController.js';
import {Extension} from './dependencies/shell/extensions/extension.js';

// We export this so it can be accessed by other extensions
export let dockManager;

export default class CommunityDockExtension extends Extension.Extension {
    enable() {
        // TODO: Remove this when upstream will disable extensions on shutdown
        // See: https://gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/4214
        this._shutdownID = global.connect('shutdown', () => this.disable());
        dockManager = new DockManager(this);
        this._indicatorController = new IndicatorController(this, dockManager);
        this._panelController = new PanelController(this);
    }

    disable() {
        global.disconnect(this._shutdownID);
        delete this._shutdownID;
        this._panelController?.destroy();
        this._panelController = null;
        this._indicatorController?.destroy();
        this._indicatorController = null;
        dockManager?.destroy();
        dockManager = null;
    }
}
