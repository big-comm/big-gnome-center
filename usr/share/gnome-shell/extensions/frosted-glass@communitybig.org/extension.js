// SPDX-License-Identifier: GPL-3.0-or-later

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Config from 'resource:///org/gnome/shell/misc/config.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {ConnectionManager} from './connectionManager.js';
import {OverviewController} from './overviewController.js';
import {PowerMonitor} from './powerMonitor.js';
import {WindowStyles} from './windowStyles.js';

const FULL_BACKEND_MINIMUM_SHELL_MAJOR = 51;
const SHELL_MAJOR = Number.parseInt(Config.PACKAGE_VERSION.split('.')[0], 10);
const FULL_BACKEND_AVAILABLE = SHELL_MAJOR >= FULL_BACKEND_MINIMUM_SHELL_MAJOR;
const COMMUNITY_MENU_UUID = 'community-menu@communitybig.org';
const LIVE_EXTENSION_STATES = new Set([1, 8]);
const LIGHT_SHELL_MENU_LAYOUTS = new Set([1, 4]);
const MATERIAL_OPACITY_EXPONENT = 1.8;

export default class FrostedGlassExtension extends Extension {
    enable() {
        if (this._settings || this._disabling)
            return;
        this._generation = (this._generation ?? 0) + 1;
        const generation = this._generation;
        const queueRefresh = () => {
            if (generation === this._generation)
                this._queueRefresh();
        };
        this._settings = this.getSettings();
        this._interfaceSettings = new Gio.Settings({
            schema_id: 'org.gnome.desktop.interface',
        });
        this._communityMenuSettings = new Gio.Settings({
            schema_id: 'org.gnome.shell.extensions.community-menu',
        });
        this._connections = new ConnectionManager();
        this._power = new PowerMonitor(queueRefresh);
        this._overview = new OverviewController(() => this._config());
        this._surfaces = null;

        this._connections.connect(this._settings, 'changed', queueRefresh);
        this._connections.connect(this._interfaceSettings,
            'changed::color-scheme', queueRefresh);
        this._connections.connect(this._communityMenuSettings,
            'changed::layout', queueRefresh);
        this._connections.connect(global.settings,
            'changed::enabled-extensions', queueRefresh);
        this._connections.connect(global.settings,
            'changed::disabled-extensions', queueRefresh);
        this._overview.enable();
        if (FULL_BACKEND_AVAILABLE)
            void this._enableFullBackend(generation);
        this._syncWindowStyles();
    }

    disable() {
        if (this._disabling)
            return;
        this._disabling = true;
        this._generation = (this._generation ?? 0) + 1;
        const refreshId = this._refreshId;
        this._refreshId = 0;
        const connections = this._connections;
        const surfaces = this._surfaces;
        const overview = this._overview;
        const power = this._power;
        this._connections = null;
        this._surfaces = null;
        this._overview = null;
        this._power = null;
        this._interfaceSettings = null;
        this._communityMenuSettings = null;
        this._settings = null;
        const cleanup = (name, action) => {
            try {
                action();
            } catch (error) {
                console.warn(`Frosted Glass: ${name} cleanup failed: ${error}`);
            }
        };
        try {
            cleanup('refresh', () => {
                if (refreshId)
                    GLib.source_remove(refreshId);
            });
            cleanup('connections', () => connections?.disconnectAll());
            // Keep this shared writer: it serializes disable and re-enable requests.
            cleanup('window styles', () => this._windowStyles?.destroy());
            cleanup('surfaces', () => surfaces?.destroy());
            cleanup('overview', () => overview?.destroy());
            cleanup('power', () => power?.destroy());
            cleanup('native parameters', () => this._restoreNativeParameters());
        } finally {
            this._disabling = false;
        }
    }

    async _enableFullBackend(generation) {
        let surfaces = null;
        try {
            const {prepareRoundedBackend} = await import('./roundedBackend.js');
            if (!this._settings || this._generation !== generation)
                return;
            await prepareRoundedBackend();
            if (!this._settings || this._generation !== generation)
                return;
            const {ShellSurfaces} = await import('./shellSurfaces.js');
            if (!this._settings || this._generation !== generation)
                return;

            surfaces = new ShellSurfaces(() => this._config());
            this._surfaces = surfaces;
            surfaces.enable();
            this._applyNativeParameters();
        } catch (error) {
            if (surfaces && this._surfaces === surfaces && this._generation === generation) {
                this._surfaces = null;
                try {
                    surfaces.destroy();
                } catch (cleanupError) {
                    console.warn(`Frosted Glass: backend cleanup failed: ${cleanupError}`);
                }
            }
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
        const materialOpacity = Math.pow(opacityPercent / 100, MATERIAL_OPACITY_EXPONENT);
        const appLightMode = this._interfaceSettings.get_string('color-scheme') !==
            'prefer-dark';
        const communityMenuActive = LIVE_EXTENSION_STATES.has(
            Main.extensionManager.lookup(COMMUNITY_MENU_UUID)?.state);
        const communityLayout = this._communityMenuSettings.get_enum('layout');
        const lightMode = appLightMode && communityMenuActive &&
            LIGHT_SHELL_MENU_LAYOUTS.has(communityLayout);
        return {
            enabled,
            windowsEnabled: FULL_BACKEND_AVAILABLE &&
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
            tintOpacity: materialOpacity,
            materialOpacity,
            windowOpacity: opacityPercent,
            useAccentColor: this._settings.settings_schema.has_key('use-accent-color') &&
                this._settings.get_boolean('use-accent-color'),
            lightMode,
            appLightMode,
            mode,
        };
    }

    _queueRefresh() {
        if (!this._settings || this._disabling || this._refreshId)
            return;
        const generation = this._generation;
        const id = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            if (!this._settings || this._generation !== generation || this._refreshId !== id)
                return GLib.SOURCE_REMOVE;
            this._refreshId = 0;
            this._applyNativeParameters();
            this._syncWindowStyles();
            this._surfaces?.refresh();
            this._overview?.refresh();
            return GLib.SOURCE_REMOVE;
        });
        this._refreshId = id;
    }

    _applyNativeParameters() {
        // Tune client-requested blur; never change window content or opacity.
        if (!FULL_BACKEND_AVAILABLE)
            return;
        const setter = global.compositor?.set_background_blur_params;
        if (typeof setter !== 'function')
            return;

        const config = this._config();
        if (!config.enabled || !config.windowsEnabled || config.mode !== 'dynamic') {
            this._restoreNativeParameters();
            return;
        }

        if (!this._nativeParametersChanged) {
            try {
                this._nativeParameters = global.compositor.get_background_blur_params();
            } catch (error) {
                return;
            }
            if (!Array.isArray(this._nativeParameters) ||
                this._nativeParameters.length !== 3 ||
                !this._nativeParameters.every(Number.isFinite))
                return;
            this._nativeParametersChanged = true;
        }
        try {
            const nativeRadius = Math.round(config.radius);
            setter.call(global.compositor, nativeRadius, 1.15, 0.008);
        } catch (error) {
            console.debug(`Frosted Glass: native blur parameters unavailable: ${error}`);
        }
    }

    _syncWindowStyles() {
        try {
            this._windowStyles ??= new WindowStyles(GLib.build_filenamev([
                this.path, '..', '..', '..', 'big-gnome-center', 'window_material.py',
            ]));
            const config = this._config();
            // Mutter 51 removed Meta.is_wayland_compositor().
            const wayland = Boolean(global.context?.get_wayland_compositor?.());
            this._windowStyles.refresh(FULL_BACKEND_AVAILABLE && wayland &&
                config.enabled && config.windowsEnabled && config.mode === 'dynamic' &&
                config.radius > 0, config.windowOpacity);
        } catch (error) {
            // GTK integration must never interrupt Shell surface rendering.
            console.warn(`Frosted Glass window styles unavailable: ${error}`);
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
