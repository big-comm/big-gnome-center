// SPDX-License-Identifier: GPL-2.0-or-later

import {CommunityDockRuntime} from '../community-dock@communitybig.org/extension.js';

import {ComponentHost} from './componentHost.js';

const DOCK_UUID = 'community-dock@communitybig.org';
const DOCK_SCHEMA = 'org.gnome.shell.extensions.dash-to-dock';
const PANEL_SCHEMA = 'org.communitybig.panel-and-dock';

export class DockRuntime {
    constructor(extension) {
        this._host = new ComponentHost(extension, DOCK_UUID, {
            name: 'Community Dock',
            version: 1,
        });
        this._runtime = new CommunityDockRuntime(this._host);
    }

    activate(profile, indicator) {
        this._profile = profile;
        if (this._active)
            return;

        this._applyIndicator(indicator);
        this._host.loadStylesheet();
        try {
            this._runtime.enable();
            this._active = true;
        } catch (error) {
            this._host.unloadStylesheet();
            throw error;
        }
    }

    deactivate() {
        if (this._active) {
            this._runtime.disable();
            this._active = false;
            this._host.unloadStylesheet();
        }
        this._profile = null;
    }

    _applyIndicator(indicator) {
        const style = ['dot', 'hybrid', 'desk-ux'].includes(indicator)
            ? indicator
            : 'dot';
        this._host.getSettings(DOCK_SCHEMA).set_enum('running-indicator-style', 0);
        this._host.getSettings(PANEL_SCHEMA).set_string('indicator-style', style);
    }
}
