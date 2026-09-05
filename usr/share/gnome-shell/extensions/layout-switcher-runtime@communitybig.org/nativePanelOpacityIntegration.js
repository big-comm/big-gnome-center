// SPDX-License-Identifier: GPL-2.0-or-later

import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {PanelAutohide} from './panelAutohide.js';
import {PanelMenuShortcuts} from './panelMenuShortcuts.js';

const VALID_VISIBILITY = new Set([
    'always-visible',
    'always-hidden',
    'intelligent',
]);

export class NativePanelOpacityIntegration {
    constructor() {
        this._panel = null;
        this._panelBox = null;
        this._originalStyle = null;
        this._ownedStyle = null;
        this._opacity = null;
        this._visibility = null;
        this._background = null;
        this._styleChangedId = 0;
        this._signals = [];
        this._windowSignals = [];
        this._focusWindow = null;
        this._revealZone = null;
        this._panelActorData = null;
        this._originalVisible = null;
        this._originalReactive = null;
        this._originalTrackHover = null;
        this._originalAffectsStruts = null;
        this._originalTrackFullscreen = null;
        this._overlayMode = null;
        this._inOverview = false;
        this._pointerReveal = false;
        this._hideTimeout = 0;
        this._applyingStyle = false;
        this._applyingVisibility = false;
        this._externalStyleUpdates = 0;
        this._repairCount = 0;
        this._restoreConflicts = 0;
        this._lastConflict = '';
    }

    activate(opacity, visibility) {
        if (!Number.isInteger(opacity) || !VALID_VISIBILITY.has(visibility)) {
            this.deactivate();
            return;
        }

        const panel = Main.panel;
        if (this._panel && this._panel !== panel)
            this.deactivate();
        if (!this._panel)
            this._enable(panel);

        const visibilityChanged = this._visibility !== visibility;
        this._opacity = Math.max(0, Math.min(100, opacity));
        this._visibility = visibility;
        if (visibilityChanged) {
            this._cancelHide();
            this._pointerReveal = false;
        }
        this._applyStyle();
        this._applyVisibility();
    }

    _enable(panel) {
        this._panel = panel;
        this._panelBox = Main.layoutManager.panelBox;
        this._originalStyle = panel.get_style();
        this._originalVisible = this._panelBox.visible;
        this._originalReactive = panel.reactive;
        this._originalTrackHover = panel.track_hover;
        const trackedIndex = Main.layoutManager._findActor(this._panelBox);
        this._panelActorData = trackedIndex >= 0
            ? Main.layoutManager._trackedActors[trackedIndex]
            : null;
        this._originalAffectsStruts = this._panelActorData?.affectsStruts;
        this._originalTrackFullscreen = this._panelActorData?.trackFullscreen;
        this._inOverview = Boolean(
            Main.overview.visible || Main.overview.visibleTarget);
        this._captureBackground();

        panel.reactive = true;
        panel.track_hover = true;
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
        this._autohide = new PanelAutohide(this._panelBox, this._revealZone, () => {
            this._pointerReveal = true;
            this._cancelHide();
            this._applyVisibility();
            this._queueHide();
        });

        this._menuShortcuts = new PanelMenuShortcuts(panel, () => {
            this._pointerReveal = true;
            this._cancelHide();
            this._applyVisibility(true);
            this._queueHide();
        });

        this._styleChangedId = panel.connect(
            'notify::style', () => this._onStyleChanged());
        this._connect(global.display, 'notify::focus-window', () => {
            this._watchFocusWindow();
            this._applyVisibility();
        });
        this._connect(global.display, 'restacked', () => this._applyVisibility());
        this._connect(global.display, 'in-fullscreen-changed',
            () => this._applyVisibility());
        this._connect(global.workspace_manager, 'active-workspace-changed',
            () => this._applyVisibility());
        this._connect(Main.layoutManager, 'monitors-changed', () => {
            this._positionRevealZone();
            this._applyVisibility();
        });
        this._connect(this._revealZone, 'leave-event', () => {
            if (!panel.hover)
                this._queueHide();
        });
        this._connect(panel, 'notify::hover', () => {
            if (panel.hover) {
                this._pointerReveal = true;
                this._cancelHide();
            } else {
                this._queueHide();
            }
        });
        this._connect(Main.overview, 'showing', () => {
            this._inOverview = true;
            this._applyVisibility();
        });
        this._connect(Main.overview, 'shown', () => {
            this._inOverview = true;
            this._applyVisibility();
        });
        this._connect(Main.overview, 'hidden', () => {
            this._inOverview = false;
            this._applyVisibility();
        });
        this._connect(this._panelBox, 'notify::visible', () => {
            if (this._overviewActive() && !this._panelBox.visible)
                this._applyVisibility();
        });
        this._watchFocusWindow();
    }

    _connect(object, signal, callback) {
        try {
            this._signals.push([object, object.connect(signal, callback)]);
        } catch (error) {
            console.warn(`[layout-switcher-runtime] native panel signal ${signal} unavailable: ${error}`);
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
        for (const signal of [
            'position-changed',
            'size-changed',
            'notify::fullscreen',
            'unmanaged',
        ]) {
            try {
                this._windowSignals.push([
                    window,
                    window.connect(signal, () => this._applyVisibility()),
                ]);
            } catch (error) {
                console.warn(`[layout-switcher-runtime] native panel window signal ${signal} unavailable: ${error}`);
            }
        }
    }

    _captureBackground() {
        const color = this._panel.get_theme_node().get_background_color();
        this._background = [color.red, color.green, color.blue];
    }

    _applyStyle() {
        const base = this._originalStyle?.trim() ?? '';
        const separator = base && !base.endsWith(';') ? '; ' : base ? ' ' : '';
        const [red, green, blue] = this._background;
        this._ownedStyle = `${base}${separator}background-color: rgba(` +
            `${red}, ${green}, ${blue}, ${(this._opacity / 100).toFixed(2)});`;
        this._applyingStyle = true;
        try {
            this._panel.set_style(this._ownedStyle);
        } finally {
            this._applyingStyle = false;
        }
    }

    _onStyleChanged() {
        if (this._applyingStyle || !this._panel)
            return;
        const style = this._panel.get_style();
        if (style === this._ownedStyle)
            return;
        this._externalStyleUpdates++;
        this._originalStyle = style;
        this._captureBackground();
        this._repairCount++;
        this._applyStyle();
    }

    _applyVisibility(immediate = false) {
        if (this._applyingVisibility || !this._panelBox || !this._visibility)
            return;
        this._applyingVisibility = true;
        try {
            const inOverview = this._overviewActive();
            const monitorFullscreen = Boolean(
                Main.layoutManager.primaryMonitor?.inFullscreen) && !inOverview;
            if (monitorFullscreen) {
                this._autohide.setEnabled(false);
                this._autohide.setVisible(false, true);
                return;
            }

            this._applyPanelTracking(this._visibility, inOverview);
            let visible = this._visibility === 'always-visible' || this._pointerReveal;
            if (this._visibility === 'always-hidden')
                visible = inOverview || this._pointerReveal;
            else if (this._visibility === 'intelligent')
                visible = inOverview || this._pointerReveal ||
                    !this._focusWindowTouchesPanel();

            this._autohide.setVisible(visible, immediate || inOverview);
        } finally {
            this._applyingVisibility = false;
        }
    }

    _overviewActive() {
        return this._inOverview || Boolean(
            Main.overview.visible || Main.overview.visibleTarget);
    }

    _applyPanelTracking(mode, inOverview = false) {
        const overlayMode = mode !== 'always-visible' && !inOverview;
        if (this._revealZone)
            this._revealZone.reactive = overlayMode;
        this._autohide.setEnabled(overlayMode);
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
        if (!monitor || !this._revealZone)
            return;
        this._revealZone.set_position(monitor.x, monitor.y);
        this._revealZone.set_size(monitor.width, 2);
        this._autohide?.reposition();
    }

    _queueHide() {
        this._cancelHide();
        this._hideTimeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
            this._hideTimeout = 0;
            if (!this._autohide.pointerInside() && !this._panelInteractionActive()) {
                this._pointerReveal = false;
                this._applyVisibility();
            } else {
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
        const quickSettings = this._panel.statusArea.quickSettings?.menu.actor;
        return Boolean(sourceActor &&
            (sourceActor === Main.layoutManager.dummyCursor ||
             this._panel.contains(sourceActor) ||
             menu?.actor?.contains(sourceActor) ||
             quickSettings?.contains(sourceActor)));
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

    _focusMonitor() {
        const window = this._focusWindow;
        if (!window || window.get_monitor() !== Main.layoutManager.primaryIndex)
            return null;
        return Main.layoutManager.monitors[window.get_monitor()] ?? null;
    }

    deactivate() {
        if (!this._panel)
            return;

        this._cancelHide();
        this._menuShortcuts.destroy();
        this._menuShortcuts = null;
        this._autohide.destroy();
        this._autohide = null;
        this._disconnectFocusWindow();
        for (const [object, id] of this._signals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Shell teardown may dispose an object first.
            }
        }
        if (this._styleChangedId)
            this._panel.disconnect(this._styleChangedId);
        this._styleChangedId = 0;
        if (this._revealZone) {
            Main.layoutManager.removeChrome(this._revealZone);
            this._revealZone.destroy();
        }
        if (this._panel.get_style() === this._ownedStyle) {
            this._panel.set_style(this._originalStyle);
        } else {
            this._restoreConflicts++;
            this._lastConflict = 'native panel inline style changed externally';
        }
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

        this._panel = null;
        this._panelBox = null;
        this._originalStyle = null;
        this._ownedStyle = null;
        this._opacity = null;
        this._visibility = null;
        this._background = null;
        this._revealZone = null;
        this._panelActorData = null;
        this._originalVisible = null;
        this._originalReactive = null;
        this._originalTrackHover = null;
        this._originalAffectsStruts = null;
        this._originalTrackFullscreen = null;
        this._overlayMode = null;
        this._pointerReveal = false;
        this._inOverview = false;
    }

    destroy() {
        this.deactivate();
    }

    diagnostics() {
        const active = Boolean(this._panel);
        const effectiveOpacity = active
            ? Math.round(this._panel.get_theme_node().get_background_color().alpha / 255 * 100)
            : null;
        return {
            implementation: 'layout-switcher-runtime',
            active,
            opacity: this._opacity,
            effectiveOpacity,
            visibility: this._visibility,
            visible: active ? Boolean(this._panelBox.visible) : null,
            inOverview: active ? this._overviewActive() : false,
            affectsStruts: active
                ? Boolean(this._panelActorData?.affectsStruts)
                : null,
            pointerReveal: active ? this._pointerReveal : false,
            styleOwned: active && this._panel.get_style() === this._ownedStyle,
            styleSignalOwned: active && Boolean(this._styleChangedId),
            visibilitySignalsOwned: active && this._signals.length > 0,
            externalStyleUpdates: this._externalStyleUpdates,
            repairCount: this._repairCount,
            restorationPending: active,
            restoreConflicts: this._restoreConflicts,
            lastConflict: this._lastConflict,
        };
    }
}
