// SPDX-License-Identifier: GPL-3.0-or-later

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Config from 'resource:///org/gnome/shell/misc/config.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {ConnectionManager} from './connectionManager.js';
import {OverviewController} from './overviewController.js';
import {PowerMonitor} from './powerMonitor.js';

// Meta.WindowActor background blur is gated until Mutter 51 repaints are
// artifact-free across GTK, Qt, and XWayland windows.
const WINDOW_FALLBACK_AVAILABLE = false;
const FULL_BACKEND_MINIMUM_SHELL_MAJOR = 51;
const SHELL_MAJOR = Number.parseInt(Config.PACKAGE_VERSION.split('.')[0], 10);
const FULL_BACKEND_AVAILABLE = SHELL_MAJOR >= FULL_BACKEND_MINIMUM_SHELL_MAJOR;
const COMMUNITY_MENU_UUID = 'community-menu@communitybig.org';
const LIVE_EXTENSION_STATES = new Set([1, 8]);
const LIGHT_SHELL_MENU_LAYOUTS = new Set([1, 4]);

export default class FrostedGlassExtension extends Extension {
    enable() {
        this._generation = (this._generation ?? 0) + 1;
        const generation = this._generation;
        this._settings = this.getSettings();
        this._interfaceSettings = new Gio.Settings({
            schema_id: 'org.gnome.desktop.interface',
        });
        this._communityMenuSettings = new Gio.Settings({
            schema_id: 'org.gnome.shell.extensions.community-menu',
        });
        this._connections = new ConnectionManager();
        this._power = new PowerMonitor(() => this._queueRefresh());
        this._overview = new OverviewController(() => this._config());
        this._windows = null;
        this._surfaces = null;

        this._connections.connect(this._settings, 'changed', () => this._queueRefresh());
        this._connections.connect(this._interfaceSettings,
            'changed::color-scheme', () => this._queueRefresh());
        this._connections.connect(this._communityMenuSettings,
            'changed::layout', () => this._queueRefresh());
        this._connections.connect(global.settings,
            'changed::enabled-extensions', () => this._queueRefresh());
        this._connections.connect(global.settings,
            'changed::disabled-extensions', () => this._queueRefresh());
        this._overview.enable();
        if (FULL_BACKEND_AVAILABLE)
            void this._enableFullBackend(generation);
    }

    disable() {
        this._generation = (this._generation ?? 0) + 1;
        if (this._refreshId) {
            GLib.source_remove(this._refreshId);
            this._refreshId = 0;
        }
        this._connections?.disconnectAll();
        this._windows?.destroy();
        this._surfaces?.destroy();
        this._overview?.destroy();
        this._power?.destroy();
        this._restoreNativeParameters();

        this._connections = null;
        this._windows = null;
        this._surfaces = null;
        this._overview = null;
        this._power = null;
        this._interfaceSettings = null;
        this._communityMenuSettings = null;
        this._settings = null;
    }

    async _enableFullBackend(generation) {
        try {
            const [{ShellSurfaces}, {WindowController}] = await Promise.all([
                import('./shellSurfaces.js'),
                import('./windowController.js'),
            ]);
            if (!this._settings || this._generation !== generation)
                return;

            this._windows = new WindowController(() => this._config());
            this._surfaces = new ShellSurfaces(() => this._config());
            this._windows.enable();
            this._surfaces.enable();
            this._applyNativeParameters();
        } catch (error) {
            this._windows?.destroy();
            this._surfaces?.destroy();
            this._windows = null;
            this._surfaces = null;
            console.error(`Frosted Glass: cannot load GNOME 51 backend: ${error}`);
        }
    }

    _config() {
        const powerBehavior = this._settings.get_string('power-save-behavior');
        const savingPower = this._power?.isSavingPower ?? false;
        const requestedMode = this._settings.get_string('blur-mode');
        let mode = requestedMode === 'automatic' ? 'dynamic' : requestedMode;
        let enabled = this._settings.get_boolean('enabled');

        if (savingPower && powerBehavior === 'static')
            mode = 'static';
        else if (savingPower && powerBehavior === 'disable')
            enabled = false;

        const strength = this._settings.get_int('blur-strength');
        const opacityPercent = this._settings.get_int('glass-opacity');
        const appLightMode = this._interfaceSettings.get_string('color-scheme') !==
            'prefer-dark';
        const communityMenuActive = LIVE_EXTENSION_STATES.has(
            Main.extensionManager.lookup(COMMUNITY_MENU_UUID)?.state);
        const communityLayout = this._communityMenuSettings.get_enum('layout');
        const lightMode = appLightMode && communityMenuActive &&
            LIGHT_SHELL_MENU_LAYOUTS.has(communityLayout);
        return {
            enabled,
            windowsEnabled: WINDOW_FALLBACK_AVAILABLE &&
                this._settings.get_boolean('windows-enabled'),
            panelEnabled: this._settings.get_boolean('panel-enabled'),
            dockEnabled: this._settings.get_boolean('dock-enabled'),
            layoutMenusEnabled: this._settings.get_boolean('layout-menus-enabled'),
            quickSettingsEnabled: this._settings.get_boolean('quick-settings-enabled'),
            calendarEnabled: this._settings.get_boolean('calendar-enabled'),
            systemDialogsEnabled: this._settings.get_boolean('system-dialogs-enabled'),
            overviewEnabled: this._settings.get_boolean('overview-enabled'),
            radius: Math.max(0, strength * 1.6),
            brightness: lightMode ? 1.0 : 0.9,
            opacity: Math.round(255 * opacityPercent / 100),
            tintOpacity: 0.60 * opacityPercent / 100,
            lightMode,
            appLightMode,
            mode,
            exclusions: this._settings.get_strv('application-exclusions'),
            maximizedBehavior: this._settings.get_string('maximized-behavior'),
            fullscreenBehavior: this._settings.get_string('fullscreen-behavior'),
        };
    }

    _queueRefresh() {
        if (this._refreshId)
            return;
        this._refreshId = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._refreshId = 0;
            this._applyNativeParameters();
            this._windows?.refresh();
            this._surfaces?.refresh();
            this._overview?.refresh();
            return GLib.SOURCE_REMOVE;
        });
    }

    _applyNativeParameters() {
        if (!FULL_BACKEND_AVAILABLE)
            return;
        const setter = global.compositor?.set_background_blur_params;
        if (typeof setter !== 'function')
            return;

        const config = this._config();
        if (!config.enabled) {
            this._restoreNativeParameters();
            return;
        }

        if (!this._nativeParametersChanged) {
            try {
                this._nativeParameters = global.compositor.get_background_blur_params();
            } catch (error) {
                this._nativeParameters = null;
            }
            this._nativeParametersChanged = true;
        }
        try {
            const nativeRadius = config.windowsEnabled ? Math.round(config.radius) : 0;
            setter.call(global.compositor, nativeRadius, 1.15, 0.008);
        } catch (error) {
            console.debug(`Frosted Glass: native blur parameters unavailable: ${error}`);
        }
    }

    _restoreNativeParameters() {
        if (!this._nativeParametersChanged)
            return;
        try {
            if (Array.isArray(this._nativeParameters))
                global.compositor?.set_background_blur_params?.(...this._nativeParameters);
        } catch (error) {
            // Compositor API is optional despite the GNOME 51 target.
        }
        this._nativeParametersChanged = false;
        this._nativeParameters = null;
    }
}
