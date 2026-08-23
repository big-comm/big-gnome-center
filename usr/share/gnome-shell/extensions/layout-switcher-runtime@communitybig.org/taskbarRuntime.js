// SPDX-License-Identifier: GPL-2.0-or-later

import {CommunityPanelRuntime} from '../community-panel@communitybig.org/extension.js';

import {ComponentHost} from './componentHost.js';

const PANEL_UUID = 'community-panel@communitybig.org';
const PANEL_SCHEMA = 'org.gnome.shell.extensions.dash-to-panel';

export class TaskbarRuntime {
    constructor(extension) {
        this._host = new ComponentHost(extension, PANEL_UUID, {
            name: 'Community Panel',
            version: 73,
            url: 'https://github.com/BigCommunity/layout-switcher',
        });
        this._runtime = new CommunityPanelRuntime(this._host);
    }

    async activate(profile, indicator, hover) {
        this._profile = profile;
        this._indicator = indicator;
        this._hover = hover;
        if (this._active)
            return;

        this._applyIndicator(indicator);
        this._applyHover(hover);
        this._host.loadStylesheet();
        try {
            await this._runtime.enable();
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
        const panels = global.dashToPanel?.panels ?? [];
        return {
            active: Boolean(this._active),
            profile: this._profile?.layout ?? '',
            indicator: this._indicator ?? '',
            hover: this._hover ?? '',
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
        };
    }

    _applyIndicator(indicator) {
        const settings = this._host.getSettings(PANEL_SCHEMA);
        if (indicator === 'none') {
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
        settings.set_boolean('animate-appicon-hover', hover === 'lift');
    }
}
