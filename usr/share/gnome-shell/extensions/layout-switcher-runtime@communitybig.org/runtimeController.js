// SPDX-License-Identifier: GPL-2.0-or-later

import Gio from 'gi://Gio';

import {DockRuntime} from './dockRuntime.js';
import {profileForLayout, RuntimeSurface} from './layoutProfiles.js';
import {StartupOverviewIntegration} from './startupOverviewIntegration.js';
import {TaskbarRuntime} from './taskbarRuntime.js';

const RUNTIME_SCHEMA = 'org.communitybig.layout-switcher.runtime';

export const RUNTIME_BUILD = 77;

export class RuntimeController {
    constructor(extension) {
        this._extension = extension;
    }

    enable() {
        if (this._settings)
            return;

        const source = Gio.SettingsSchemaSource.get_default();
        const schema = source.lookup(RUNTIME_SCHEMA, true);
        if (!schema) {
            console.error(`[layout-switcher-runtime] missing schema ${RUNTIME_SCHEMA}`);
            return;
        }

        this._dock = new DockRuntime(this._extension);
        this._taskbar = new TaskbarRuntime(this._extension);
        this._startupOverview = new StartupOverviewIntegration();
        this._enabled = true;
        this._syncPromise = Promise.resolve();
        this._settings = new Gio.Settings({settings_schema: schema});
        const startupProfile = profileForLayout(
            this._settings.get_string('active-layout'));
        this._startupOverview.apply(
            this._skipStartupOverviewForProfile(startupProfile));
        this._settingsChangedIds = [
            'active-layout',
            'dock-hover-overrides',
            'dock-menu-side-overrides',
            'dock-opacity-overrides',
            'dock-size-overrides',
            'dock-visibility-overrides',
            'indicator-style-overrides',
            'panel-height-overrides',
            'panel-opacity-overrides',
            'panel-visibility-overrides',
            'skip-startup-overview-overrides',
        ].map(key => this._settings.connect(
            `changed::${key}`,
            () => this._queueSync(),
        ));
        this._queueSync();
        console.info(`[layout-switcher-runtime] build ${RUNTIME_BUILD} ready`);
    }

    disable() {
        this._enabled = false;
        this._syncGeneration = (this._syncGeneration ?? 0) + 1;
        for (const id of this._settingsChangedIds ?? [])
            this._settings?.disconnect(id);
        this._settingsChangedIds = [];
        this._dock?.deactivate();
        this._taskbar?.deactivate();
        this._startupOverview?.destroy();
        this._activeProfile = null;
        this._dock = null;
        this._taskbar = null;
        this._startupOverview = null;
        this._settings = null;
        this._syncPromise = null;
    }

    _queueSync() {
        const generation = (this._syncGeneration ?? 0) + 1;
        this._syncGeneration = generation;
        this._syncPromise = this._syncPromise
            .then(() => this._syncProfile(generation))
            .catch(error => console.error(
                `[layout-switcher-runtime] profile activation failed: ${error.stack ?? error}`,
            ));
    }

    async _syncProfile(generation) {
        if (!this._enabled || !this._settings)
            return;

        const profile = profileForLayout(this._settings.get_string('active-layout'));
        const indicator = this._indicatorForProfile(profile);
        const hover = this._hoverForProfile(profile);
        const visibility = this._visibilityForProfile(profile);
        const dockOpacity = this._dockOpacityForProfile(profile);
        const dockSize = this._dockSizeForProfile(profile);
        const panelOpacity = this._panelOpacityForProfile(profile);
        const panelVisibility = this._panelVisibilityForProfile(profile);
        const panelHeight = this._panelHeightForProfile(profile);
        const menuSide = this._menuSideForProfile(profile);
        const skipStartupOverview = this._skipStartupOverviewForProfile(profile);
        const dockProfileChanged = this._activeProfile?.layout !== profile.layout;
        this._activeProfile = profile;
        this._startupOverview.apply(skipStartupOverview);

        if (profile.surface === RuntimeSurface.DOCK) {
            this._taskbar.deactivate();
            if (dockProfileChanged)
                this._dock.deactivate();
            this._dock.activate(
                profile, indicator, hover, dockOpacity, dockSize, visibility,
                menuSide, skipStartupOverview);
        } else if (profile.surface === RuntimeSurface.TASKBAR) {
            this._dock.deactivate();
            await this._taskbar.activate(
                profile, indicator, hover, panelOpacity,
                panelVisibility, panelHeight);
            if (!this._enabled || generation !== this._syncGeneration)
                this._taskbar.deactivate();
        } else if (profile.surface === RuntimeSurface.NATIVE) {
            this._dock.deactivate();
            this._taskbar.deactivate();
        } else {
            throw new Error(`Unsupported runtime surface: ${profile.surface}`);
        }
    }

    _indicatorForProfile(profile) {
        if (profile.indicator === 'none')
            return 'none';
        const overrides = this._settings
            .get_value('indicator-style-overrides')
            .deep_unpack();
        return overrides[profile.layout] ?? profile.indicator;
    }

    _hoverForProfile(profile) {
        const overrides = this._settings
            .get_value('dock-hover-overrides')
            .deep_unpack();
        return overrides[profile.layout] ?? profile.hover;
    }

    _visibilityForProfile(profile) {
        const overrides = this._settings
            .get_value('dock-visibility-overrides')
            .deep_unpack();
        return overrides[profile.layout] ?? profile.visibility ?? 'intelligent';
    }

    _dockOpacityForProfile(profile) {
        if (profile.dockOpacity === undefined)
            return undefined;
        const overrides = this._settings
            .get_value('dock-opacity-overrides')
            .deep_unpack();
        const opacity = overrides[profile.layout] ?? profile.dockOpacity;
        return Math.max(0, Math.min(100, opacity));
    }

    _dockSizeForProfile(profile) {
        if (profile.dockSize === undefined)
            return undefined;
        const overrides = this._settings
            .get_value('dock-size-overrides')
            .deep_unpack();
        const size = overrides[profile.layout] ?? profile.dockSize;
        return Math.max(28, Math.min(64, size));
    }

    _panelVisibilityForProfile(profile) {
        const overrides = this._settings
            .get_value('panel-visibility-overrides')
            .deep_unpack();
        return overrides[profile.layout] ?? profile.panelVisibility ?? 'always-visible';
    }

    _panelOpacityForProfile(profile) {
        if (profile.panelOpacity === undefined)
            return undefined;
        const overrides = this._settings
            .get_value('panel-opacity-overrides')
            .deep_unpack();
        const opacity = overrides[profile.layout] ?? profile.panelOpacity;
        return Math.max(0, Math.min(100, opacity));
    }

    _panelHeightForProfile(profile) {
        if (profile.panelHeight === undefined)
            return undefined;
        const overrides = this._settings
            .get_value('panel-height-overrides')
            .deep_unpack();
        const panelHeight = overrides[profile.layout] ?? profile.panelHeight;
        return Math.max(32, Math.min(56, panelHeight));
    }

    _menuSideForProfile(profile) {
        if (profile.layout !== 'BigGnome')
            return null;
        const overrides = this._settings
            .get_value('dock-menu-side-overrides')
            .deep_unpack();
        const side = overrides[profile.layout] ?? profile.menuSide;
        return ['left', 'right'].includes(side) ? side : 'right';
    }

    _skipStartupOverviewForProfile(profile) {
        const overrides = this._settings
            .get_value('skip-startup-overview-overrides')
            .deep_unpack();
        return overrides[profile.layout] ?? profile.skipStartupOverview;
    }

    _panelActorHeightForProfile(profile) {
        const panelHeight = this._panelHeightForProfile(profile);
        if (panelHeight === undefined)
            return profile.actorHeight;
        return panelHeight + profile.actorHeight - profile.panelHeight;
    }

    diagnostics() {
        const profile = this._activeProfile ??
            profileForLayout(this._settings?.get_string('active-layout') ?? '');
        return {
            build: RUNTIME_BUILD,
            enabled: Boolean(this._enabled),
            layout: profile.layout,
            expected: {
                surface: profile.surface,
                edge: profile.edge,
                extended: profile.extended,
                labels: profile.labels,
                indicator: this._indicatorForProfile(profile),
                hover: this._hoverForProfile(profile),
                opacity: profile.surface === RuntimeSurface.DOCK
                    ? this._dockOpacityForProfile(profile)
                    : this._panelOpacityForProfile(profile),
                iconSize: this._dockSizeForProfile(profile),
                visibility: profile.surface === RuntimeSurface.TASKBAR
                    ? this._panelVisibilityForProfile(profile)
                    : this._visibilityForProfile(profile),
                actorHeight: this._panelActorHeightForProfile(profile),
                menuSide: this._menuSideForProfile(profile),
                skipStartupOverview: this._skipStartupOverviewForProfile(profile),
            },
            startupOverview: this._startupOverview?.diagnostics() ?? {},
            dock: this._dock?.diagnostics() ?? {active: false, actors: []},
            taskbar: this._taskbar?.diagnostics() ?? {active: false, actors: []},
        };
    }
}
