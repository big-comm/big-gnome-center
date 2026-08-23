// SPDX-License-Identifier: GPL-3.0-or-later

import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Background from 'resource:///org/gnome/shell/ui/background.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {ConnectionManager} from './connectionManager.js';
import {OverviewMaterialStylesheet} from './overviewMaterial.js';

const EFFECT_NAME = 'communitybig-frosted-glass-overview';
const STYLE_CLASS = 'frosted-glass-overview';
const LIGHT_STYLE_CLASS = 'frosted-glass-light';

export class OverviewController {
    constructor(getConfig) {
        this._getConfig = getConfig;
        this._connections = new ConnectionManager();
        this._group = new Meta.BackgroundGroup({
            name: 'communitybig-frosted-glass-overview-group',
        });
        this._managers = [];
        this._materialStylesheet = new OverviewMaterialStylesheet();
        this._enabled = false;
        this._reinserting = false;
    }

    enable() {
        this._connections.connect(Main.layoutManager, 'monitors-changed',
            () => this.refresh(true));
        this._connections.connect(Main.layoutManager.overviewGroup, 'child-added',
            (group, child) => this._keepAtBottom(group, child));
        this.refresh(true);
    }

    refresh(rebuild = false) {
        const config = this._getConfig();
        const enabled = config.enabled && config.overviewEnabled;
        if (!enabled) {
            this._detach();
            return;
        }

        if (!this._enabled || rebuild)
            this._rebuild(config);
        else
            this._updateEffects(config);
    }

    destroy() {
        this._connections.disconnectAll();
        this._detach();
        this._materialStylesheet.destroy();
        this._materialStylesheet = null;
        this._group.destroy();
        this._group = null;
    }

    _rebuild(config) {
        this._clearActors();
        for (const monitor of Main.layoutManager.monitors) {
            const actor = new St.Widget({
                name: 'communitybig-frosted-glass-overview',
                x: monitor.x,
                y: monitor.y,
                width: monitor.width,
                height: monitor.height,
                reactive: false,
            });
            const effect = new Shell.BlurEffect({mode: Shell.BlurMode.ACTOR});
            actor.add_effect_with_name(EFFECT_NAME, effect);
            const manager = new Background.BackgroundManager({
                container: actor,
                monitorIndex: monitor.index,
                controlPosition: false,
            });
            actor._frostedGlass = {effect};
            this._group.add_child(actor);
            this._managers.push(manager);
        }

        this._attach();
        this._updateEffects(config);
    }

    _updateEffects(config) {
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        for (const actor of this._group.get_children()) {
            const record = actor._frostedGlass;
            if (!record)
                continue;
            record.effect.radius = Math.max(0, Math.round(config.radius * scale));
            record.effect.brightness = config.brightness;
        }
        this._materialStylesheet.update(config);
        if (config.lightMode)
            Main.uiGroup.add_style_class_name(LIGHT_STYLE_CLASS);
        else
            Main.uiGroup.remove_style_class_name(LIGHT_STYLE_CLASS);
    }

    _attach() {
        const overviewGroup = Main.layoutManager.overviewGroup;
        if (this._group.get_parent() !== overviewGroup) {
            this._group.get_parent()?.remove_child(this._group);
            overviewGroup.insert_child_at_index(this._group, 0);
        }
        Main.uiGroup.add_style_class_name(STYLE_CLASS);
        this._enabled = true;
    }

    _detach() {
        if (!this._enabled)
            return;
        this._clearActors();
        if (this._group.get_parent())
            this._group.get_parent().remove_child(this._group);
        Main.uiGroup.remove_style_class_name(STYLE_CLASS);
        Main.uiGroup.remove_style_class_name(LIGHT_STYLE_CLASS);
        this._enabled = false;
    }

    _clearActors() {
        for (const manager of this._managers.splice(0)) {
            try {
                manager.destroy();
            } catch (error) {
                console.debug(`Frosted Glass: cannot destroy overview background: ${error}`);
            }
        }
        this._group.remove_all_children();
    }

    _keepAtBottom(group, child) {
        if (!this._enabled || child === this._group || this._reinserting)
            return;
        this._reinserting = true;
        try {
            group.remove_child(this._group);
            group.insert_child_at_index(this._group, 0);
        } finally {
            this._reinserting = false;
        }
    }
}
