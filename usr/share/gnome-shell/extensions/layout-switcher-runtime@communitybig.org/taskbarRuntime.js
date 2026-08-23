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

    async activate(profile, indicator) {
        this._profile = profile;
        if (this._active)
            return;

        this._applyIndicator(indicator);
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
}
