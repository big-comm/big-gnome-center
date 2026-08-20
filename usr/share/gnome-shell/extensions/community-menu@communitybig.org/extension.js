// Modified by Community Big, 2026-07-10: renamed, de-Zorinized, and adapted for GNOME Shell 50.
/*
 * Zorin Menu: The official applications menu for Zorin OS.
 *
 * Copyright (C) 2016-2025 Zorin OS Technologies Ltd.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import * as Constants from './constants.js';
import * as Menu from './menu.js';
import {SearchProviderEmitter} from './searchProviderEmitter.js';
import * as Utils from './utils.js';

export let EXTENSION_PATH = null;
export let SETTINGS = null;
export let SEARCH_EMITTER = null;

const LIGHT_PANEL_STYLE_CLASS = 'community-menu-light-panel';
const DARK_PANEL_STYLE_CLASS = 'community-menu-dark-panel';
const GRID_PANEL_STYLE_CLASS = 'community-menu-grid-panel';
const CLASSIC_DESKTOP_LAYOUT = 'Classic';
const DESK_UX_DESKTOP_LAYOUT = 'Desk UX';

export default class CommunityMenuExtension extends Extension {
    enable() {
        EXTENSION_PATH = this.path;
        SETTINGS = this.getSettings();
        SEARCH_EMITTER = new SearchProviderEmitter();

        this.menuButtons = [];
        this._styledPanels = new Set();
        this._interfaceSettings = new Gio.Settings({
            schema_id: 'org.gnome.desktop.interface',
        });
        this._interfaceSettings.connectObject(
            'changed::color-scheme', () => this._syncPanelColorClass(), this);
        this._mutterSettings = new Gio.Settings({
            schema_id: Constants.MUTTER_SCHEMA,
        });
        this._savedOverlayKey = this._mutterSettings.get_value('overlay-key');
        this._mutterSettings.connectObject('changed::overlay-key', () => {
            if (!this._changingOverlayKey)
                this._savedOverlayKey = this._mutterSettings.get_value('overlay-key');
        }, this);
        SETTINGS.connectObject('changed::layout', () => {
            this._syncOverlayKeyBinding();
        }, this);
        SETTINGS.connectObject('changed::desktop-layout', () => {
            this._syncPanelColorClass();
        }, this);
        SETTINGS.connectObject('changed::super-key-opens-menu', () => {
            this._syncOverlayKeyBinding();
        }, this);

        this._getActivePanelExtension();
        this._enableButtons();
        this._syncOverlayKeyBinding();

        Main.extensionManager.connectObject('extension-state-changed', (data, extension) => {
            if (Utils.isPanelExtension(extension.uuid)) {
                this._getActivePanelExtension();
                this._disconnectExtensionSignals();
                this._connectExtensionSignals();
                this._reload();
            }
        }, this);

        this._connectExtensionSignals();
    }

    disable() {
        this._disableOverlayKeyBinding();
        SETTINGS?.disconnectObject(this);
        this._interfaceSettings?.disconnectObject(this);
        this._mutterSettings?.disconnectObject(this);
        this._clearPanelColorClass();
        this._interfaceSettings = null;
        this._mutterSettings = null;
        this._savedOverlayKey = null;

        this._disconnectExtensionSignals();
        Main.extensionManager.disconnectObject(this);

        this._disableButtons();
        this.menuButtons = null;

        SEARCH_EMITTER?.destroy();
        SEARCH_EMITTER = null;

        Utils.clearCommandsCache();

        EXTENSION_PATH = null;
        SETTINGS = null;
    }

    _getActivePanelExtension() {
        this._panelExtension = null;

        let dtp = Main.extensionManager.lookup(Constants.COMMUNITY_PANEL_UUID);

        if (Utils.isExtensionEnabled(dtp) && global.dashToPanel) {
            this._panelExtension = "dashToPanel";
        }
    }

    _connectExtensionSignals() {
        if (this._panelExtension && global[this._panelExtension]) {
            global[this._panelExtension].connectObject('panels-created', () => {
                this._reload();
            }, this);
        }
    }

    _disconnectExtensionSignals() {
        if (global.dashToPanel)
            global.dashToPanel.disconnectObject(this);
    }

    _reload() {
        this._disableButtons();
        this._enableButtons();
        this._syncOverlayKeyBinding();
    }

    _enableButtons() {
        let panelExtensionEnabled = false;
        let panels;

        if (this._panelExtension && global[this._panelExtension]?.panels) {
            panels = global[this._panelExtension].panels.filter(p => p);
            panelExtensionEnabled = true;
        } else {
            panels = [Main.panel];
        }

        const primaryPanelIndex = Main.layoutManager.primaryMonitor?.index;

        for (var i = 0; i < panels.length; i++) {
            if (!panels[i]) {
                console.log(`Community Menu Error: panel ${i} not found. Skipping...`);
                continue;
            }

            let panel, panelBox, panelParent;
            if (panelExtensionEnabled) {
                panel = panels[i].panel;
                panelBox = panels[i].panelBox;
                panelParent = panels[i];
            } else {
                panel = panels[i];
                panelBox = Main.layoutManager.panelBox;
                panelParent = Main.panel;
            }

            let monitorIndex = 0;
            if (panelParent.monitor)
                monitorIndex = panelParent.monitor.index;
            else if (panel === Main.panel)
                monitorIndex = primaryPanelIndex ?? 0;

            const panelExtension = this._panelExtension;
            const panelInfo = {panel, panelBox, panelParent, monitorIndex, panelExtension};

            // Community Panel can rebuild its actors while a layout switch is
            // still completing. Recover an already attached menu button
            // instead of leaving an orphan actor and an empty tracking list.
            const existingButton = panel?.statusArea?.['community-menu'];
            if (existingButton?.get_parent()) {
                if (!this.menuButtons.includes(existingButton))
                    this.menuButtons.push(existingButton);
                continue;
            }
            if (existingButton)
                panel.statusArea['community-menu'] = null;

            const menuButton = new Menu.ApplicationsButton(panelInfo);
            this._enableButton(menuButton)
        }

        this._syncPanelColorClass();
    }

    _clearPanelColorClass() {
        for (const menuButton of this.menuButtons ?? [])
            menuButton.setLightStyle(false);

        for (const panel of this._styledPanels ?? []) {
            try {
                panel.remove_style_class_name(LIGHT_PANEL_STYLE_CLASS);
                panel.remove_style_class_name(DARK_PANEL_STYLE_CLASS);
                panel.remove_style_class_name(GRID_PANEL_STYLE_CLASS);
            } catch (e) {
                console.debug(`Community Menu: panel style cleanup failed: ${e}`);
            }
        }
        this._styledPanels?.clear();
    }

    _syncPanelColorClass() {
        this._clearPanelColorClass();
        const desktopLayout = SETTINGS.get_string('desktop-layout');
        const lightMode = this._interfaceSettings &&
            this._interfaceSettings.get_string('color-scheme') !== 'prefer-dark';
        const panelStyleClass = lightMode
            ? (desktopLayout === CLASSIC_DESKTOP_LAYOUT
                ? LIGHT_PANEL_STYLE_CLASS
                : (desktopLayout === DESK_UX_DESKTOP_LAYOUT
                    ? DARK_PANEL_STYLE_CLASS
                    : null))
            : null;
        for (const menuButton of this.menuButtons ?? []) {
            menuButton.setLightStyle(lightMode);
            const panel = menuButton.panel;
            if (!panel)
                continue;
            if (desktopLayout === DESK_UX_DESKTOP_LAYOUT)
                panel.add_style_class_name(GRID_PANEL_STYLE_CLASS);
            if (panelStyleClass)
                panel.add_style_class_name(panelStyleClass);
            this._styledPanels.add(panel);
        }
    }

    _enableButton(menuButton) {
        const panel = menuButton.panel;

        panel?.addToStatusArea(
            'community-menu', menuButton, 0, 'left'
        );
        panel?.connectObject('destroy', () => this._disableButton(menuButton, panel), this);

        this.menuButtons.push(menuButton);
    }

    _disableButtons() {
        for (let i = this.menuButtons.length - 1; i >= 0; --i) {
            const mb = this.menuButtons[i];
            this._disableButton(mb, mb.panel);
        }
    }

    _disableButton(menuButton, panel) {
        if (panel) {
            panel.disconnectObject(this);
            panel.statusArea['community-menu'] = null;
        }

        const index = this.menuButtons.indexOf(menuButton);
        if (index !== -1)
            this.menuButtons.splice(index, 1);

        menuButton?.destroy();
    }

    _getOpenedMenu() {
        const menus = this._getAllMenus();
        for (let i = 0; i < menus.length; i++) {
            if (menus[i].isOpen)
                return menus[i];
        }
        return null;
    }

    _getAllMenus() {
        const menus = [];
        for (let i = 0; i < this.menuButtons.length; i++) {
            menus.push(this.menuButtons[i]._menu);
        }
        return menus;
    }

    _toggleMenu() {
        if (this.menuButtons.length < 1) {
            // A panel rebuild may briefly remove every tracked button. Super
            // belongs to Community Menu in this layout, so rebuild the menu
            // instead of falling through to GNOME's overview.
            this._getActivePanelExtension();
            this._enableButtons();
        }

        if (this.menuButtons.length < 1) {
            console.warn('Community Menu: no panel button available for Super');
            return;
        }

        if (this.menuButtons.length === 1) {
            this.menuButtons[0].toggleMenu();
        } else {
            this._toggleMenuOnMonitor();
        }
    }

    _syncOverlayKeyBinding() {
        // Keep one stable handler while the extension is enabled. Restoring
        // GNOME Shell's private handler at runtime is unreliable across Shell
        // versions; delegate to the overview when that is the user's choice.
        this._enableOverlayKeyBinding();
    }

    _enableOverlayKeyBinding() {
        if (this._overlayKeyActive)
            return;

        this._overlayKeyActive = true;
        this._changingOverlayKey = true;
        this._mutterSettings.set_string('overlay-key', 'Super_L');
        this._changingOverlayKey = false;
        Main.wm.allowKeybinding('overlay-key', Shell.ActionMode.ALL);

        if (Main.layoutManager._startingUp) {
            Main.layoutManager.connectObject('startup-complete', () => {
                if (this._overlayKeyActive)
                    this._overrideOverlayKey();
            }, this);
        } else {
            this._overrideOverlayKey();
        }
    }

    _overrideOverlayKey() {
        this._defaultOverlayKeyId = GObject.signal_handler_find(
            global.display, {signalId: 'overlay-key'});
        if (!this._defaultOverlayKeyId) {
            console.warn('Community Menu: failed to override the Super key');
            this._disableOverlayKeyBinding();
            return;
        }

        GObject.signal_handler_block(global.display, this._defaultOverlayKeyId);
        global.display.connectObject('overlay-key', () => {
            if (SETTINGS.get_boolean('super-key-opens-menu'))
                this._toggleMenu();
            else
                Main.overview.toggle();
            Main.wm.allowKeybinding('overlay-key', Shell.ActionMode.ALL);
        }, this);
    }

    _disableOverlayKeyBinding() {
        Main.layoutManager.disconnectObject(this);
        global.display.disconnectObject(this);

        if (this._defaultOverlayKeyId) {
            GObject.signal_handler_unblock(global.display, this._defaultOverlayKeyId);
            this._defaultOverlayKeyId = 0;
        }

        if (this._overlayKeyActive && this._mutterSettings && this._savedOverlayKey) {
            this._changingOverlayKey = true;
            this._mutterSettings.set_value('overlay-key', this._savedOverlayKey);
            this._changingOverlayKey = false;
        }

        this._overlayKeyActive = false;
        Main.wm.allowKeybinding(
            'overlay-key', Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW);
    }

    _toggleMenuOnMonitor() {
        const monitor = Main.layoutManager.currentMonitor;
        if (!monitor) {
            this.menuButtons[0]?.toggleMenu();
            return;
        }

        const primaryMonitorIndex = Main.layoutManager.primaryMonitor?.index ?? 0;
        let targetButton = null;
        let primaryButton = null;

        for (let i = 0; i < this.menuButtons.length; i++) {
            const menuButton = this.menuButtons[i];
            const {monitorIndex} = menuButton;

            if (monitor.index === monitorIndex) {
                targetButton = menuButton;
            } else {
                menuButton.maybeCloseMenus();
            }

            if (monitorIndex === primaryMonitorIndex)
                primaryButton = menuButton;
        }

        // Open the menu on the current monitor, or fall back to the
        // primary monitor's menu if none is found on the current one.
        const buttonToToggle = targetButton ?? primaryButton ?? this.menuButtons[0];
        buttonToToggle?.toggleMenu();
    }

}
