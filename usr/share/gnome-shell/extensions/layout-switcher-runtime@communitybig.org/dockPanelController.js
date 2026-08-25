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
const FULLSCREEN_EXIT_SETTLE_MS = 120;
const FULLSCREEN_REPAIR_STAGE_TIMEOUT_MS = 500;
const FULLSCREEN_EXIT_REPAIR_LIMIT = 3;

export class PanelController {
    constructor(extension, dockProvider = () => []) {
        this._settings = extension.getSettings(SETTINGS_SCHEMA);
        this._dockProvider = dockProvider;
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
        this._fullscreenExitArmed = false;
        this._fullscreenExitTimeout = 0;
        this._fullscreenExitRepairAttempts = 0;
        this._fullscreenExitRepairStage = null;
        this._normalGeometry = null;

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
        this._connect(global.display, 'restacked',
            () => this._applyVisibility());
        this._connect(global.display, 'in-fullscreen-changed',
            () => this._onFullscreenChanged());
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
        this._cancelFullscreenExitRepair();
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
        this._dockProvider = null;
    }

    diagnostics() {
        const window = this._focusWindow;
        const monitor = this._focusMonitor();
        const frame = window?.get_frame_rect();
        const buffer = window?.get_buffer_rect();
        const windowActor = global.get_window_actors()
            .find(actor => actor.meta_window === window);
        const workArea = monitor
            ? Main.layoutManager.getWorkAreaForMonitor(monitor.index)
            : null;
        return {
            visible: Boolean(this._panelBox?.visible),
            mapped: Boolean(this._panelBox?.mapped),
            fullscreen: Boolean(monitor?.inFullscreen),
            windowFullscreen: Boolean(window?.fullscreen),
            monitorFullscreen: Boolean(monitor?.inFullscreen),
            overview: Boolean(this._inOverview),
            affectsStruts: Boolean(this._panelActorData?.affectsStruts),
            trackFullscreen: Boolean(this._panelActorData?.trackFullscreen),
            dockAffectsStruts: this._dockTrackingDiagnostics(),
            dockVisible: this._dockVisibilityDiagnostics(),
            frame: this._rectangleDiagnostics(frame),
            buffer: this._rectangleDiagnostics(buffer),
            windowActor: this._windowActorDiagnostics(windowActor),
            workArea: this._rectangleDiagnostics(workArea),
            fullscreenExitRepairArmed: this._fullscreenExitArmed,
            fullscreenExitRepairPending: Boolean(this._fullscreenExitTimeout),
            fullscreenExitRepairAttempts: this._fullscreenExitRepairAttempts,
            fullscreenExitRepairStage: this._fullscreenExitRepairStage,
        };
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
        const previousWindow = this._focusWindow;
        this._disconnectFocusWindow();
        const window = global.display.focus_window;
        if (previousWindow && previousWindow !== window) {
            this._cancelFullscreenExitRepair();
            this._fullscreenExitArmed = false;
            this._fullscreenExitRepairAttempts = 0;
            this._fullscreenExitRepairStage = null;
            this._normalGeometry = null;
        }
        if (!window)
            return;
        this._focusWindow = window;
        for (const signal of [
            'position-changed',
            'size-changed',
            'unmanaged',
        ]) {
            try {
                this._windowSignals.push([
                    window,
                    window.connect(signal, () => this._onWindowGeometryChanged()),
                ]);
            } catch (error) {
                console.warn(`[community-dock] window signal ${signal} unavailable: ${error}`);
            }
        }
        this._rememberNormalGeometry();
    }

    _apply() {
        this._applyOpacity();
        this._applyVisibility();
    }

    _onFullscreenChanged() {
        if (this._focusMonitor()?.inFullscreen) {
            this._fullscreenExitArmed = true;
            this._fullscreenExitRepairAttempts = 0;
            this._fullscreenExitRepairStage = null;
            this._cancelFullscreenExitRepair();
        } else if (this._fullscreenExitArmed) {
            this._queueFullscreenExitRepair();
        }
        this._applyVisibility();
    }

    _onWindowGeometryChanged() {
        this._applyVisibility();
        if (this._advanceFullscreenExitRepair())
            return;
        if (this._fullscreenExitArmed &&
            !this._focusWindow?.fullscreen &&
            !this._focusMonitor()?.inFullscreen)
            this._queueFullscreenExitRepair();
        else
            this._rememberNormalGeometry();
    }

    _queueFullscreenExitRepair(
        delay = FULLSCREEN_EXIT_SETTLE_MS) {
        this._cancelFullscreenExitRepair();
        this._fullscreenExitTimeout = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            delay,
            () => {
                this._fullscreenExitTimeout = 0;
                this._repairFullscreenExit();
                return GLib.SOURCE_REMOVE;
            },
        );
    }

    _cancelFullscreenExitRepair() {
        if (!this._fullscreenExitTimeout)
            return;
        GLib.Source.remove(this._fullscreenExitTimeout);
        this._fullscreenExitTimeout = 0;
    }

    _repairFullscreenExit() {
        const window = this._focusWindow;
        const monitor = this._focusMonitor();
        if (!window || !monitor || window.fullscreen || monitor.inFullscreen)
            return;

        if (this._fullscreenExitRepairStage) {
            this._fullscreenExitRepairStage = null;
            this._fullscreenExitArmed = false;
            return;
        }

        const normal = this._normalGeometry;
        if (!normal || normal.window !== window || window.minimized ||
            !window.showing_on_its_workspace()) {
            this._fullscreenExitArmed = false;
            this._fullscreenExitRepairStage = null;
            return;
        }

        const frame = window.get_frame_rect();
        const buffer = window.get_buffer_rect();
        const workArea = Main.layoutManager.getWorkAreaForMonitor(monitor.index);
        const target = normal.maximized ? workArea : normal.frame;
        const targetBuffer = normal.maximized ? workArea : normal.buffer;
        const actor = global.get_window_actors()
            .find(candidate => candidate.meta_window === window);
        const frameMatches = frame.x === target.x && frame.y === target.y &&
            frame.width === target.width && frame.height === target.height;
        const bufferMatches = buffer.x === targetBuffer.x &&
            buffer.y === targetBuffer.y && buffer.width === targetBuffer.width &&
            buffer.height === targetBuffer.height;
        const actorMatches = !actor || (
            Math.round(actor.x) === targetBuffer.x &&
            Math.round(actor.y) === targetBuffer.y &&
            Math.round(actor.width) === targetBuffer.width &&
            Math.round(actor.height) === targetBuffer.height
        );
        if (frameMatches && bufferMatches && actorMatches) {
            this._fullscreenExitArmed = false;
            this._fullscreenExitRepairAttempts = 0;
            this._rememberNormalGeometry();
            return;
        }

        if (this._fullscreenExitRepairAttempts >= FULLSCREEN_EXIT_REPAIR_LIMIT) {
            this._fullscreenExitArmed = false;
            this._fullscreenExitRepairStage = null;
            return;
        }
        this._fullscreenExitRepairAttempts++;

        if (normal.maximized) {
            this._fullscreenExitRepairStage = 'await-unmaximized';
            window.unmaximize();
        } else {
            this._fullscreenExitRepairStage = 'await-temporary-maximized';
            window.maximize();
        }
        this._queueFullscreenExitRepair(FULLSCREEN_REPAIR_STAGE_TIMEOUT_MS);
    }

    _advanceFullscreenExitRepair() {
        const stage = this._fullscreenExitRepairStage;
        const window = this._focusWindow;
        const normal = this._normalGeometry;
        if (!stage || !window || normal?.window !== window ||
            window.fullscreen || this._focusMonitor()?.inFullscreen)
            return false;

        const maximized = window.maximized_horizontally &&
            window.maximized_vertically;
        const frame = window.get_frame_rect();
        const workArea = Main.layoutManager.getWorkAreaForMonitor(
            window.get_monitor());
        const matchesWorkArea = frame.x === workArea.x &&
            frame.y === workArea.y && frame.width === workArea.width &&
            frame.height === workArea.height;
        if (stage === 'await-unmaximized' && !maximized &&
            !matchesWorkArea) {
            this._fullscreenExitRepairStage = 'await-maximized';
            window.maximize();
        } else if (stage === 'await-maximized' && maximized &&
            matchesWorkArea) {
            this._fullscreenExitRepairStage = null;
        } else if (stage === 'await-temporary-maximized' && maximized &&
            matchesWorkArea) {
            this._fullscreenExitRepairStage = 'await-restored-normal';
            window.unmaximize();
        } else if (stage === 'await-restored-normal' && !maximized &&
            !matchesWorkArea) {
            this._fullscreenExitRepairStage = null;
            const target = normal.frame;
            window.move_resize_frame(
                false,
                target.x,
                target.y,
                target.width,
                target.height,
            );
        } else {
            return false;
        }

        this._queueFullscreenExitRepair(
            this._fullscreenExitRepairStage
                ? FULLSCREEN_REPAIR_STAGE_TIMEOUT_MS
                : FULLSCREEN_EXIT_SETTLE_MS,
        );
        return true;
    }

    _rememberNormalGeometry() {
        const window = this._focusWindow;
        if (!window || window.fullscreen || this._focusMonitor()?.inFullscreen ||
            this._fullscreenExitArmed)
            return;
        const frame = window.get_frame_rect();
        const buffer = window.get_buffer_rect();
        this._normalGeometry = {
            window,
            frame: {
                x: frame.x,
                y: frame.y,
                width: frame.width,
                height: frame.height,
            },
            buffer: {
                x: buffer.x,
                y: buffer.y,
                width: buffer.width,
                height: buffer.height,
            },
            maximized: window.maximized_horizontally &&
                window.maximized_vertically,
        };
        this._fullscreenExitRepairAttempts = 0;
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
            const monitorFullscreen = Boolean(
                this._focusMonitor()?.inFullscreen) && !this._inOverview;
            if (monitorFullscreen)
                return;

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

    _dockTrackingDiagnostics() {
        return (this._dockProvider?.() ?? []).map(dock => {
            const index = Main.layoutManager._findActor(dock);
            if (index < 0)
                return null;
            return Boolean(
                Main.layoutManager._trackedActors[index]?.affectsStruts);
        });
    }

    _dockVisibilityDiagnostics() {
        return (this._dockProvider?.() ?? [])
            .map(dock => Boolean(dock.visible));
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

    _focusMonitor() {
        const window = this._focusWindow;
        if (!window || window.get_monitor() !== Main.layoutManager.primaryIndex)
            return null;
        return Main.layoutManager.monitors[window.get_monitor()] ?? null;
    }

    _rectangleDiagnostics(rectangle) {
        if (!rectangle)
            return null;
        return {
            x: Math.round(rectangle.x),
            y: Math.round(rectangle.y),
            width: Math.round(rectangle.width),
            height: Math.round(rectangle.height),
        };
    }

    _windowActorDiagnostics(actor) {
        if (!actor)
            return null;
        const [transformedX, transformedY] = actor.get_transformed_position();
        const [transformedWidth, transformedHeight] = actor.get_transformed_size();
        const transitionNames = [
            'translation-x',
            'translation-y',
            'scale-x',
            'scale-y',
            'x',
            'y',
            'width',
            'height',
        ];
        return {
            x: Math.round(actor.x),
            y: Math.round(actor.y),
            width: Math.round(actor.width),
            height: Math.round(actor.height),
            translationX: Math.round(actor.translation_x),
            translationY: Math.round(actor.translation_y),
            scaleX: actor.scale_x,
            scaleY: actor.scale_y,
            transformedX: Math.round(transformedX),
            transformedY: Math.round(transformedY),
            transformedWidth: Math.round(transformedWidth),
            transformedHeight: Math.round(transformedHeight),
            transitions: transitionNames.filter(name => actor.get_transition(name)),
            animationInfo: Boolean(actor.__animationInfo),
            resizePending: Boolean(Main.wm?._resizePending?.has(actor)),
            resizing: Boolean(Main.wm?._resizing?.has(actor)),
        };
    }
}
