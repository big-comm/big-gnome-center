// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import * as Panel from '../community-panel@communitybig.org/panel.js';
import * as Utils from '../community-panel@communitybig.org/utils.js';

export class TaskbarPanelHost {
    constructor(statusAreaHost) {
        this._statusAreaHost = statusAreaHost;
        this._panels = new Set();
        this._generation = 0;
    }

    create(panelManager, monitor, isStandalone) {
        const clipContainer = new Clutter.Actor();
        let panelBox;
        let panel = null;
        if (isStandalone) {
            panelBox = new Utils.createBoxLayout({name: 'panelBox'});
        } else {
            panelBox = Main.layoutManager.panelBox;
            Main.layoutManager._untrackActor(panelBox);
            panelBox.remove_child(Main.panel);
            Main.layoutManager.removeChrome(panelBox);
        }

        Utils.addChrome(clipContainer, {affectsInputRegion: false});
        clipContainer.add_child(panelBox);

        try {
            panel = new Panel.Panel(
                panelManager,
                monitor,
                clipContainer,
                panelBox,
                isStandalone,
                isStandalone ? null : this._statusAreaHost,
            );
            panelBox.add_child(panel);
            panel.enable();

            panelBox._dtpIndex = monitor.index;
            panelBox.set_position(0, 0);
            panelBox.set_width(-1);
            Utils.trackChrome(panel, {
                affectsInputRegion: true,
                affectsStruts: false,
            });
            Utils.trackChrome(panelBox, {
                trackFullscreen: true,
                affectsStruts: true,
            });
            panel.intellihide.init();

            this._panels.add(panel);
            this._generation++;
            return panel;
        } catch (error) {
            this._rollbackCreate(panel, panelBox, clipContainer, isStandalone);
            throw error;
        }
    }

    release(panel) {
        try {
            Main.layoutManager._untrackActor(panel);
            Main.layoutManager._untrackActor(panel.panelBox);

            if (panel.isStandalone) {
                panel.panelBox.destroy();
            } else {
                panel.panelBox.remove_child(panel);
                panel.remove_child(panel.panel);
                panel.panelBox.add_child(panel.panel);
                panel.panelBox.set_position(
                    panel.clipContainer.x, panel.clipContainer.y);
                delete panel.panelBox._dtpIndex;
                panel.clipContainer.remove_child(panel.panelBox);
                Utils.addChrome(panel.panelBox, {
                    affectsStruts: true,
                    trackFullscreen: true,
                });
            }

            Main.layoutManager.removeChrome(panel.clipContainer);
        } finally {
            this._panels.delete(panel);
        }
    }

    releaseAll() {
        for (const panel of [...this._panels]) {
            try {
                this.release(panel);
            } catch (error) {
                console.error(
                    `[layout-switcher-runtime] panel host release failed: ${error}`,
                );
            }
        }
    }

    diagnostics() {
        return {
            available: true,
            owned: this._panels.size > 0,
            generation: this._generation,
            activePanels: this._panels.size,
        };
    }

    _rollbackCreate(panel, panelBox, clipContainer, isStandalone) {
        try {
            panel?.disable();
        } catch (error) {
            console.warn(
                `[layout-switcher-runtime] partial panel cleanup failed: ${error}`,
            );
        }
        this._statusAreaHost.restore();

        try {
            if (panel)
                Main.layoutManager._untrackActor(panel);
            if (panelBox)
                Main.layoutManager._untrackActor(panelBox);
            if (isStandalone) {
                panelBox.destroy();
            } else {
                const nativeParent = Main.panel.get_parent?.();
                nativeParent?.remove_child(Main.panel);
                panel.get_parent?.()?.remove_child(panel);
                panelBox.get_parent?.()?.remove_child(panelBox);
                panelBox.add_child(Main.panel);
                delete panelBox._dtpIndex;
                Utils.addChrome(panelBox, {
                    affectsStruts: true,
                    trackFullscreen: true,
                });
            }
            Main.layoutManager.removeChrome(clipContainer);
            panel?.destroy();
        } catch (cleanupError) {
            console.error(
                `[layout-switcher-runtime] panel host rollback failed: ${cleanupError}`,
            );
        }
    }
}
