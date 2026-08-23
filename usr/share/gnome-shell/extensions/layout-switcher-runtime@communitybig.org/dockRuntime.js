// SPDX-License-Identifier: GPL-2.0-or-later

import {CommunityDockRuntime} from '../community-dock@communitybig.org/extension.js';

import {ComponentHost} from './componentHost.js';
import {DockAppActions} from './dockAppActions.js';
import {DockAppMenuFactory} from './dockAppIconMenu.js';
import {DockAppMenuActions} from './dockAppMenuActions.js';
import {DockAppModel} from './dockAppModel.js';
import {DockHoverEffects} from './dockHoverEffects.js';
import {DockNotificationBadges} from './dockNotificationBadges.js';
import {DockNotificationMonitor} from './dockNotificationMonitor.js';
import {DockPlacement} from './dockPlacement.js';
import {DockRunningIndicators} from './dockRunningIndicators.js';
import {DockVisibilityModes} from './dockVisibilityModes.js';

const DOCK_UUID = 'community-dock@communitybig.org';
const DOCK_SCHEMA = 'org.gnome.shell.extensions.dash-to-dock';
const PANEL_SCHEMA = 'org.communitybig.panel-and-dock';

export class DockRuntime {
    constructor(extension) {
        this._host = new ComponentHost(extension, DOCK_UUID, {
            name: 'Community Dock',
            version: 1,
        });
        this._host.appActions = new DockAppActions();
        this._host.appMenuFactory = new DockAppMenuFactory();
        this._host.appMenuActions = new DockAppMenuActions();
        this._host.appModel = new DockAppModel();
        this._host.hoverEffects = new DockHoverEffects(
            this._host.getSettings(PANEL_SCHEMA),
        );
        this._host.notificationBadges = new DockNotificationBadges();
        this._host.placement = new DockPlacement(
            this._host.getSettings(DOCK_SCHEMA),
        );
        this._host.visibilityModes = new DockVisibilityModes(
            this._host.getSettings(DOCK_SCHEMA),
        );
        this._host.createIndicatorController = manager => {
            this._host.runningIndicators = new DockRunningIndicators(
                this._host.getSettings(PANEL_SCHEMA),
                this._host.getSettings(DOCK_SCHEMA),
                manager,
            );
            return this._host.runningIndicators;
        };
        this._engine = new CommunityDockRuntime(this._host);
    }

    activate(profile, indicator, hover, visibility) {
        this._profile = profile;
        this._indicator = indicator;
        this._hover = hover;
        this._visibility = visibility;
        if (this._active)
            return;

        this._applyProfile(profile);
        this._applyIndicator(indicator);
        this._applyHover(hover);
        this._host.visibilityModes.apply(visibility);
        this._host.notificationsMonitor = new DockNotificationMonitor(
            this._host.getSettings(DOCK_SCHEMA),
        );
        this._host.loadStylesheet();
        try {
            this._engine.enable();
            this._active = true;
        } catch (error) {
            this._host.unloadStylesheet();
            this._destroyNotificationsMonitor();
            throw error;
        }
    }

    deactivate() {
        if (this._active) {
            this._engine.disable();
            this._active = false;
            this._host.unloadStylesheet();
        }
        this._destroyNotificationsMonitor();
        delete this._host.runningIndicators;
        this._profile = null;
        this._indicator = null;
        this._hover = null;
        this._visibility = null;
    }

    diagnostics() {
        const docks = this._engine.docks;
        return {
            active: Boolean(this._active && this._engine.active),
            profile: this._profile?.layout ?? '',
            indicator: this._indicator ?? '',
            hover: this._hover ?? '',
            visibility: this._host.visibilityModes.mode(),
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
        this._host.hoverEffects.setEffect(effect);
        this._host.getSettings(PANEL_SCHEMA).set_string('dock-hover-effect', effect);
    }

    _applyProfile(profile) {
        this._host.placement.apply(profile?.edge);
    }

    _destroyNotificationsMonitor() {
        this._host.notificationsMonitor?.destroy();
        delete this._host.notificationsMonitor;
    }
}
