// SPDX-License-Identifier: GPL-2.0-or-later

import {DockSurfaceManager, State} from './dockSurface.js';

import {ComponentHost} from './componentHost.js';
import {DockActorFactory} from './dockActorFactory.js';
import {DockAppActions} from './dockAppActions.js';
import {DockAppMenuFactory} from './dockAppIconMenu.js';
import {DockAppMenuActions} from './dockAppMenuActions.js';
import {DockAppModel} from './dockAppModel.js';
import {DockHoverEffects} from './dockHoverEffects.js';
import {DockNotificationBadges} from './dockNotificationBadges.js';
import {DockNotificationMonitor} from './dockNotificationMonitor.js';
import {PanelController} from './dockPanelController.js';
import {DockPlacement} from './dockPlacement.js';
import {DockRunningIndicators} from './dockRunningIndicators.js';
import {DockVisibilityModes} from './dockVisibilityModes.js';

const DOCK_UUID = 'community-dock@communitybig.org';
const DOCK_SCHEMA = 'org.gnome.shell.extensions.dash-to-dock';

export class DockRuntime {
    constructor(extension) {
        this._managerGeneration = 0;
        this._host = new ComponentHost(extension, DOCK_UUID, {
            name: 'Layout Switcher Dock',
            version: 1,
        }, 'dock');
        this._actorFactory = new DockActorFactory();
        this._host.createDockActor = params => this._actorFactory.create(params);
        this._host.appActions = new DockAppActions();
        this._host.appMenuFactory = new DockAppMenuFactory();
        this._host.appMenuActions = new DockAppMenuActions();
        this._host.appModel = new DockAppModel();
        this._host.hoverEffects = new DockHoverEffects(
            dash => this._dockIsShown(dash),
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
                this._host.getSettings(DOCK_SCHEMA),
                manager,
                this._indicator,
            );
            return this._host.runningIndicators;
        };
        this._host.createPanelController = () => new PanelController(
            this._host,
            () => this._manager?._allDocks ?? [],
        );
    }

    activate(profile, indicator, hover, magnificationIntensity, opacity, iconSize, visibility,
        menuSide, skipStartupOverview) {
        this._profile = profile;
        this._indicator = indicator;
        this._hover = hover;
        this._magnificationIntensity = magnificationIntensity;
        this._opacity = opacity;
        this._iconSize = iconSize;
        this._visibility = visibility;
        this._menuSide = menuSide;
        this._skipStartupOverview = skipStartupOverview;
        this._host.layout = profile.layout;
        this._host.skipStartupOverview = skipStartupOverview;
        if (this._active) {
            this._applyIndicator(indicator);
            this._applyHover(hover, magnificationIntensity);
            this._applyOpacity(opacity);
            this._applyIconSize(iconSize);
            this._host.visibilityModes.apply(visibility);
            this._applyMenuSide(menuSide);
            return;
        }

        this._applyProfile(profile);
        this._applyIndicator(indicator);
        this._applyHover(hover, magnificationIntensity);
        this._applyOpacity(opacity);
        this._applyIconSize(iconSize);
        this._host.visibilityModes.apply(visibility);
        this._applyMenuSide(menuSide);
        this._host.notificationsMonitor = new DockNotificationMonitor(
            this._host.getSettings(DOCK_SCHEMA),
        );
        this._host.loadStylesheet();
        try {
            this._enableSurfaces();
            this._active = true;
        } catch (error) {
            this._host.unloadStylesheet();
            this._destroyNotificationsMonitor();
            throw error;
        }
    }

    deactivate() {
        if (this._active) {
            this._disableSurfaces();
            this._active = false;
            this._host.unloadStylesheet();
        }
        this._destroyNotificationsMonitor();
        delete this._host.runningIndicators;
        this._profile = null;
        this._indicator = null;
        this._hover = null;
        this._magnificationIntensity = null;
        this._opacity = null;
        this._iconSize = null;
        this._visibility = null;
        this._menuSide = null;
        this._skipStartupOverview = null;
        delete this._host.layout;
        delete this._host.menuSide;
        delete this._host.skipStartupOverview;
    }

    diagnostics() {
        const docks = this._manager?._allDocks ?? [];
        return {
            active: Boolean(this._active && this._manager),
            profile: this._profile?.layout ?? '',
            indicator: this._host.runningIndicators?.style() ?? this._indicator ?? '',
            hover: this._host.hoverEffects.effect(),
            magnificationIntensity: this._host.hoverEffects.intensity(),
            hoverState: this._host.hoverEffects.diagnostics(),
            opacity: this._opacity ?? null,
            iconSize: this._iconSize ?? null,
            managerGeneration: this._managerGeneration,
            visibility: this._host.visibilityModes.mode(),
            extended: this._host.placement.extended(),
            menuSide: this._menuSide,
            skipStartupOverview: this._skipStartupOverview,
            panel: this._panelController?.diagnostics() ?? {},
            desktopBridge:
                this._manager?.desktopIconsUsableArea?.diagnostics() ?? {},
            actors: docks.map(dock => this._actorDiagnostics(dock)),
        };
    }

    notificationBottomOffset(monitorIndex) {
        if (!this._active)
            return 0;
        const dock = this._manager?._allDocks?.find(candidate =>
            candidate?.monitorIndex === monitorIndex);
        if (dock?.position !== 2)
            return 0;
        return Math.max(0, Math.ceil(dock.height ?? 0));
    }

    _enableSurfaces() {
        if (this._manager)
            return;

        let manager = null;
        try {
            manager = new DockSurfaceManager(this._host);
            this._manager = manager;
            this._indicatorController =
                this._host.createIndicatorController(manager);
            this._panelController = this._host.createPanelController();
            this._managerGeneration++;
        } catch (error) {
            const partialManager = manager ?? DockSurfaceManager.getDefault();
            this._panelController?.destroy();
            this._panelController = null;
            this._indicatorController?.destroy();
            this._indicatorController = null;
            try {
                partialManager?.destroy();
            } catch (cleanupError) {
                console.warn(
                    `[layout-switcher] partial Dock cleanup failed: ${cleanupError}`,
                );
            }
            this._manager = null;
            throw error;
        }
    }

    _disableSurfaces() {
        const manager = this._manager;
        this._host.hoverEffects.releaseAll();
        this._panelController?.destroy();
        this._panelController = null;
        this._indicatorController?.destroy();
        this._indicatorController = null;
        manager?.destroy();
        this._manager = null;
    }

    _actorDiagnostics(dock) {
        const actor = dock?._box ?? dock;
        const background = dock?.dash?._background;
        const menu = dock?.dash?._showAppsIcon;
        const [menuX] = menu?.get_transformed_position?.() ?? [null];
        const [dockX] = actor?.get_transformed_position?.() ?? [null];
        const backgroundColor = background
            ? background.get_theme_node().get_background_color()
            : null;
        return {
            monitor: dock?.monitorIndex ?? -1,
            edge: this._sideName(dock?._position),
            x: Math.round(actor?.x ?? 0),
            y: Math.round(actor?.y ?? 0),
            width: Math.round(actor?.width ?? 0),
            height: Math.round(actor?.height ?? 0),
            visible: Boolean(actor?.visible),
            mapped: Boolean(actor?.mapped),
            opacity: backgroundColor
                ? Math.round(backgroundColor.alpha * 100 / 255)
                : null,
            iconSize: Math.round(dock?.dash?.iconSize ?? 0),
            menuX: Number.isFinite(menuX) ? Math.round(menuX) : null,
            menuSide: Number.isFinite(menuX) && Number.isFinite(dockX)
                ? menuX + menu.width / 2 < dockX + actor.width / 2
                    ? 'left'
                    : 'right'
                : '',
        };
    }

    _dockIsShown(dash) {
        const dock = this._manager?._allDocks
            ?.find(candidate => candidate?.dash === dash);
        return dock?.getDockState?.() === State.SHOWN;
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
        this._host.runningIndicators?.setStyle(style);
    }

    _applyHover(hover, magnificationIntensity) {
        const effect = ['lift', 'magnify'].includes(hover) ? hover : 'default';
        this._host.hoverEffects.setEffect(effect, magnificationIntensity);
        for (const dock of this._manager?._allDocks ?? [])
            this._host.hoverEffects.applyStyle(dock.dash);
    }

    _applyOpacity(opacity) {
        if (!Number.isInteger(opacity))
            return;
        const settings = this._host.getSettings(DOCK_SCHEMA);
        settings.set_boolean('custom-background-color', true);
        settings.set_enum('transparency-mode', 1);
        settings.set_double('background-opacity', opacity / 100);
    }

    _applyIconSize(iconSize) {
        if (Number.isInteger(iconSize))
            this._host.getSettings(DOCK_SCHEMA)
                .set_int('dash-max-icon-size', iconSize);
    }

    _applyProfile(profile) {
        this._host.placement.apply(profile?.edge, profile?.extended);
    }

    _applyMenuSide(menuSide) {
        this._host.menuSide = ['left', 'right'].includes(menuSide)
            ? menuSide
            : null;
        this._manager?.updateMenuSide();
    }

    _destroyNotificationsMonitor() {
        this._host.notificationsMonitor?.destroy();
        delete this._host.notificationsMonitor;
    }
}
