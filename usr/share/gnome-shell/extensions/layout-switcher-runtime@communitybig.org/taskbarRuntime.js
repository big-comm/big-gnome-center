// SPDX-License-Identifier: GPL-2.0-or-later

import GLib from 'gi://GLib';
import Meta from 'gi://Meta';

import {ComponentHost} from './componentHost.js';
import {TaskbarSurfaceManager} from './taskbarSurface.js';
import {TaskbarVisibilityModes} from './taskbarVisibilityModes.js';

const PANEL_UUID = 'community-panel@communitybig.org';
const PANEL_SCHEMA = 'org.gnome.shell.extensions.dash-to-panel';

export class TaskbarRuntime {
    constructor(extension) {
        this._host = new ComponentHost(extension, PANEL_UUID, {
            name: 'Community Panel',
            version: 73,
            url: 'https://github.com/BigCommunity/layout-switcher',
        });
        this._surface = new TaskbarSurfaceManager(this._host);
        this._visibilityModes = new TaskbarVisibilityModes(
            this._host.getSettings(PANEL_SCHEMA));
        this._activationGeneration = 0;
        this._activating = false;
    }

    async activate(profile, indicator, hover, opacity, visibility, panelHeight) {
        const generation = ++this._activationGeneration;
        this._profile = profile;
        this._indicator = indicator;
        this._hover = hover;
        this._opacity = opacity;
        this._visibility = visibility;
        this._panelHeight = panelHeight;
        if (this._active) {
            this._applyIndicator(indicator);
            this._applyHover(hover);
            this._applyOpacity(opacity);
            this._visibilityModes.apply(visibility);
            this._surface.setPanelHeight(panelHeight);
            return;
        }

        this._applyIndicator(indicator);
        this._applyHover(hover);
        this._applyOpacity(opacity);
        this._visibilityModes.apply(visibility);
        this._host.loadStylesheet();
        this._activating = true;
        try {
            await this._surface.enable(panelHeight);
            if (generation !== this._activationGeneration)
                return;
            this._active = true;
        } catch (error) {
            this._surface.destroy();
            this._host.unloadStylesheet();
            throw error;
        } finally {
            if (generation === this._activationGeneration)
                this._activating = false;
        }
    }

    deactivate() {
        this._activationGeneration++;
        if (this._active || this._activating) {
            this._surface.destroy();
            this._active = false;
            this._activating = false;
            this._host.unloadStylesheet();
        }
        this._profile = null;
        this._indicator = null;
        this._hover = null;
        this._opacity = null;
        this._visibility = null;
        this._panelHeight = null;
    }

    diagnostics() {
        const panels = this._surface.panels();
        const settings = this._host.getSettings(PANEL_SCHEMA);
        return {
            active: Boolean(this._active && panels.length),
            profile: this._profile?.layout ?? '',
            indicator: this._indicator ?? '',
            hover: settings.get_boolean('animate-appicon-hover')
                ? 'lift'
                : 'default',
            opacity: this._opacity ?? null,
            visibility: this._visibilityModes.mode(),
            window: this._windowDiagnostics(),
            lifecycle: this._surface.diagnostics(),
            actors: panels.map(panel => this._panelDiagnostics(panel)),
        };
    }

    _panelDiagnostics(panel) {
        const actor = panel?.panelBox;
        return {
            monitor: panel?.monitor?.index ?? panel?.monitorIndex ?? -1,
            edge: {
                0: 'top',
                1: 'right',
                2: 'bottom',
                3: 'left',
            }[panel?.geom?.position] ?? 'unknown',
            x: Math.round(actor?.x ?? 0),
            y: Math.round(actor?.y ?? 0),
            width: Math.round(actor?.width ?? 0),
            height: Math.round(actor?.height ?? 0),
            visible: Boolean(actor?.visible),
            mapped: Boolean(actor?.mapped),
            grouped: Boolean(panel?.taskbar?.isGroupApps),
            opacity: Number.isFinite(panel?.dynamicTransparency?.alpha)
                ? Math.round(panel.dynamicTransparency.alpha * 100)
                : null,
            ...this._visibilityModes.panelState(panel),
        };
    }

    _windowDiagnostics() {
        const window = global.display.focus_window;
        if (!window)
            return {};
        const monitor = window.get_monitor();
        const workspace = window.get_workspace();
        const windowType = window.get_window_type();
        return {
            monitor,
            title: window.get_title() ?? '',
            wmClass: window.get_wm_class() ?? '',
            windowType,
            normal: windowType === Meta.WindowType.NORMAL,
            maximized: Boolean(
                window.maximized_horizontally && window.maximized_vertically),
            fullscreen: Boolean(window.fullscreen),
            frame: this._rect(window.get_frame_rect()),
            workArea: this._rect(workspace?.get_work_area_for_monitor(monitor)),
        };
    }

    _rect(rect) {
        if (!rect)
            return null;
        return {
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
        };
    }

    _applyIndicator(indicator) {
        const settings = this._host.getSettings(PANEL_SCHEMA);
        if (indicator === 'none') {
            settings.set_string('dot-style-focused', 'DOTS');
            settings.set_string('dot-style-unfocused', 'DOTS');
            settings.set_int('dot-size', 0);
            return;
        }

        const [focused, unfocused, size] = {
            dot: ['DOTS', 'DOTS', 6],
            hybrid: ['SEGMENTED', 'SEGMENTED', 3],
            'desk-ux': ['METRO', 'DASHES', 3],
        }[indicator] ?? ['DOTS', 'DOTS', 6];
        settings.set_string('dot-style-focused', focused);
        settings.set_string('dot-style-unfocused', unfocused);
        settings.set_int('dot-size', size);
    }

    _applyHover(hover) {
        const settings = this._host.getSettings(PANEL_SCHEMA);
        const lift = hover === 'lift';
        settings.set_boolean('animate-appicon-hover', lift);
        if (!lift)
            return;

        settings.set_string('animate-appicon-hover-animation-type', 'SIMPLE');
        const profile = [
            ['animate-appicon-hover-animation-convexity', 'a{sd}', 0.0],
            ['animate-appicon-hover-animation-duration', 'a{su}', 220],
            ['animate-appicon-hover-animation-extent', 'a{si}', 1],
            ['animate-appicon-hover-animation-rotation', 'a{si}', 0],
            ['animate-appicon-hover-animation-travel', 'a{sd}', 0.08],
            ['animate-appicon-hover-animation-zoom', 'a{sd}', 1.08],
        ];
        for (const [key, variantType, value] of profile) {
            const values = settings.get_value(key).deep_unpack();
            values.SIMPLE = value;
            settings.set_value(key, new GLib.Variant(variantType, values));
        }
    }

    _applyOpacity(opacity) {
        if (!Number.isInteger(opacity))
            return;
        const settings = this._host.getSettings(PANEL_SCHEMA);
        settings.set_boolean('trans-use-custom-opacity', true);
        settings.set_boolean('trans-use-dynamic-opacity', false);
        settings.set_double('trans-panel-opacity', opacity / 100);
    }
}
