// SPDX-License-Identifier: GPL-2.0-or-later
// Layout Switcher panel appearance and visibility controller.

import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const SETTINGS_SCHEMA = 'org.communitybig.panel-and-dock';
const VALID_VISIBILITY = new Set([
    'always-visible',
    'always-hidden',
    'intelligent',
]);

export class PanelController {
    constructor(extension) {
        this._settings = extension.getSettings(SETTINGS_SCHEMA);
        this._panel = Main.panel;
        this._panelBox = Main.layoutManager.panelBox;
        this._originalStyle = this._panel.get_style();
        this._originalVisible = this._panelBox.visible;
        this._originalReactive = this._panel.reactive;
        this._originalTrackHover = this._panel.track_hover;
        const trackedIndex = Main.layoutManager._findActor(this._panelBox);
        this._panelActorData = trackedIndex >= 0
            ? Main.layoutManager._trackedActors[trackedIndex]
            : null;
        this._originalAffectsStruts = this._panelActorData?.affectsStruts;
        this._originalTrackFullscreen = this._panelActorData?.trackFullscreen;
        this._overlayMode = null;
        this._signals = [];
        this._windowSignals = [];
        this._focusWindow = null;
        this._inOverview = Main.overview.visible;
        this._applying = false;
        this._pointerReveal = false;
        this._hideTimeout = 0;
        this._opacityIdle = 0;

        this._panel.reactive = true;
        this._panel.track_hover = true;
        this._revealZone = new St.Widget({
            reactive: true,
            track_hover: true,
            opacity: 0,
        });
        Main.layoutManager.addTopChrome(this._revealZone, {
            affectsStruts: false,
            trackFullscreen: true,
        });
        this._positionRevealZone();

        this._connect(this._settings, 'changed', () => this._apply());
        this._connect(global.display, 'notify::focus-window', () => {
            this._watchFocusWindow();
            this._applyVisibility();
        });
        this._connect(global.display, 'restacked', () => this._applyVisibility());
        this._connect(global.workspace_manager, 'active-workspace-changed',
            () => this._applyVisibility());
        this._connect(Main.layoutManager, 'monitors-changed', () => {
            this._positionRevealZone();
            this._applyVisibility();
        });
        this._connect(this._revealZone, 'enter-event', () => {
            this._pointerReveal = true;
            this._cancelHide();
            this._applyVisibility();
        });
        this._connect(this._panel, 'notify::hover', () => {
            if (this._panel.hover) {
                this._pointerReveal = true;
                this._cancelHide();
            } else {
                this._queueHide();
            }
        });
        this._connect(Main.overview, 'showing', () => {
            this._inOverview = true;
            this._applyVisibility();
            this._queueOpacityApply();
        });
        this._connect(Main.overview, 'shown', () => this._queueOpacityApply());
        this._connect(Main.overview, 'hiding', () => this._queueOpacityApply());
        this._connect(Main.overview, 'hidden', () => {
            this._inOverview = false;
            this._applyVisibility();
            this._queueOpacityApply();
        });

        this._watchFocusWindow();
        this._apply();
    }

    destroy() {
        this._cancelHide();
        this._cancelOpacityApply();
        this._disconnectFocusWindow();
        for (const [object, id] of this._signals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Shell teardown may dispose an object first.
            }
        }
        Main.layoutManager.removeChrome(this._revealZone);
        this._revealZone.destroy();
        this._panel.set_style(this._originalStyle);
        this._panel.reactive = this._originalReactive;
        this._panel.track_hover = this._originalTrackHover;
        if (this._panelActorData) {
            this._panelActorData.affectsStruts = this._originalAffectsStruts;
            this._panelActorData.trackFullscreen = this._originalTrackFullscreen;
            Main.layoutManager._queueUpdateRegions();
        }
        if (this._originalVisible)
            this._panelBox.show();
        else
            this._panelBox.hide();
        this._settings = null;
        this._panel = null;
        this._panelBox = null;
        this._revealZone = null;
    }

    _connect(object, signal, callback) {
        try {
            this._signals.push([object, object.connect(signal, callback)]);
        } catch (error) {
            console.warn(`[community-dock] panel signal ${signal} unavailable: ${error}`);
        }
    }

    _disconnectFocusWindow() {
        for (const [object, id] of this._windowSignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Window may already be unmanaged.
            }
        }
        this._focusWindow = null;
    }

    _watchFocusWindow() {
        this._disconnectFocusWindow();
        const window = global.display.focus_window;
        if (!window)
            return;
        this._focusWindow = window;
        for (const signal of ['position-changed', 'size-changed', 'unmanaged']) {
            try {
                this._windowSignals.push([
                    window,
                    window.connect(signal, () => this._applyVisibility()),
                ]);
            } catch (error) {
                console.warn(`[community-dock] window signal ${signal} unavailable: ${error}`);
            }
        }
    }

    _apply() {
        this._applyOpacity();
        this._applyVisibility();
    }

    _applyOpacity() {
        const opacity = Math.min(100, this._settings.get_uint('panel-opacity')) / 100;
        const base = this._originalStyle ? `${this._originalStyle}; ` : '';
        this._panel.set_style(
            `${base}background-color: rgba(0, 0, 0, ${opacity.toFixed(2)});`);
    }

    _queueOpacityApply() {
        this._applyOpacity();
        this._cancelOpacityApply();
        this._opacityIdle = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._opacityIdle = 0;
            if (this._settings)
                this._applyOpacity();
            return GLib.SOURCE_REMOVE;
        });
    }

    _cancelOpacityApply() {
        if (!this._opacityIdle)
            return;
        GLib.Source.remove(this._opacityIdle);
        this._opacityIdle = 0;
    }

    _applyVisibility() {
        if (this._applying)
            return;
        this._applying = true;
        try {
            const configured = this._settings.get_string('panel-visibility');
            const mode = VALID_VISIBILITY.has(configured)
                ? configured
                : 'always-visible';
            this._applyPanelTracking(mode);
            let visible = mode === 'always-visible' || this._pointerReveal;
            if (mode === 'always-hidden')
                visible = this._inOverview || this._pointerReveal;
            else if (mode === 'intelligent')
                visible = this._inOverview || this._pointerReveal ||
                    !this._focusWindowTouchesPanel();

            if (visible)
                this._panelBox.show();
            else
                this._panelBox.hide();
        } finally {
            this._applying = false;
        }
    }

    _applyPanelTracking(mode) {
        const overlayMode = mode !== 'always-visible';
        if (!this._panelActorData || this._overlayMode === overlayMode)
            return;

        this._overlayMode = overlayMode;
        this._panelActorData.affectsStruts = overlayMode
            ? false
            : this._originalAffectsStruts;
        this._panelActorData.trackFullscreen = overlayMode
            ? false
            : this._originalTrackFullscreen;
        Main.layoutManager._queueUpdateRegions();
    }

    _positionRevealZone() {
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;
        this._revealZone.set_position(monitor.x, monitor.y);
        this._revealZone.set_size(monitor.width, 2);
    }

    _queueHide() {
        this._cancelHide();
        this._hideTimeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
            this._hideTimeout = 0;
            if (!this._panel.hover && !this._panelInteractionActive()) {
                this._pointerReveal = false;
                this._applyVisibility();
            } else if (!this._panel.hover) {
                this._queueHide();
            }
            return GLib.SOURCE_REMOVE;
        });
    }

    _cancelHide() {
        if (!this._hideTimeout)
            return;
        GLib.Source.remove(this._hideTimeout);
        this._hideTimeout = 0;
    }

    _panelInteractionActive() {
        const manager = this._panel.menuManager;
        const menu = manager?.activeMenu ?? manager?._activeMenu;
        if (menu?.isOpen || menu?.actor?.visible)
            return true;

        const grabActor = global.stage.get_grab_actor();
        const sourceActor = grabActor?._sourceActor ?? grabActor;
        return Boolean(sourceActor &&
            (sourceActor === Main.layoutManager.dummyCursor ||
             this._panel.contains(sourceActor) ||
             menu?.actor?.contains(sourceActor) ||
             this._panel.statusArea.quickSettings?.menu.actor.contains(sourceActor)));
    }

    _focusWindowTouchesPanel() {
        const window = this._focusWindow;
        const monitor = Main.layoutManager.primaryMonitor;
        if (!window || !monitor || window.minimized ||
            window.get_monitor() !== Main.layoutManager.primaryIndex ||
            !window.showing_on_its_workspace())
            return false;

        const rect = window.get_frame_rect();
        const panelHeight = Math.max(1, this._panel.height, this._panelBox.height);
        const workArea = Main.layoutManager.getWorkAreaForMonitor(
            Main.layoutManager.primaryIndex);
        const panelBoundary = Math.max(
            monitor.y + panelHeight,
            workArea?.y ?? monitor.y);
        const touchesTop = window.maximized_vertically || window.fullscreen ||
            rect.y <= panelBoundary;
        return rect.x < monitor.x + monitor.width &&
            rect.x + rect.width > monitor.x &&
            touchesTop &&
            rect.y + rect.height > monitor.y;
    }
}
