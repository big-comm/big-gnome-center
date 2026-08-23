// SPDX-License-Identifier: GPL-2.0-or-later

import {
    CommunityDockRuntime,
    dockManager,
} from '../community-dock@communitybig.org/extension.js';

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

    activate(profile, indicator, hover) {
        this._profile = profile;
        this._indicator = indicator;
        this._hover = hover;
        if (this._active)
            return;

        this._applyProfile(profile);
        this._applyIndicator(indicator);
        this._applyHover(hover);
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
        this._indicator = null;
        this._hover = null;
    }

    diagnostics() {
        const docks = dockManager?._allDocks ?? [];
        return {
            active: Boolean(this._active),
            profile: this._profile?.layout ?? '',
            indicator: this._indicator ?? '',
            hover: this._hover ?? '',
            actors: docks.map(dock => this._actorDiagnostics(dock)),
        };
    }

    _actorDiagnostics(dock) {
        const actor = dock?._box ?? dock;
        return {
            monitor: dock?.monitorIndex ?? -1,
            edge: this._sideName(dock?._position),
            x: Math.round(actor?.x ?? 0),
            y: Math.round(actor?.y ?? 0),
            width: Math.round(actor?.width ?? 0),
            height: Math.round(actor?.height ?? 0),
            visible: Boolean(actor?.visible),
            mapped: Boolean(actor?.mapped),
        };
    }

    _sideName(side) {
        return {
            0: 'top',
            1: 'right',
            2: 'bottom',
            3: 'left',
        }[side] ?? 'unknown';
    }

    _applyIndicator(indicator) {
        const style = ['dot', 'hybrid', 'desk-ux'].includes(indicator)
            ? indicator
            : 'dot';
        this._host.getSettings(DOCK_SCHEMA).set_enum('running-indicator-style', 0);
        this._host.getSettings(PANEL_SCHEMA).set_string('indicator-style', style);
    }

    _applyHover(hover) {
        const effect = hover === 'lift' ? 'lift' : 'default';
        this._host.getSettings(PANEL_SCHEMA).set_string('dock-hover-effect', effect);
    }

    _applyProfile(profile) {
        const position = {
            top: 0,
            right: 1,
            bottom: 2,
            left: 3,
        }[profile?.edge];
        if (position !== undefined)
            this._host.getSettings(DOCK_SCHEMA).set_enum('dock-position', position);
    }
}
