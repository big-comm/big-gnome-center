// SPDX-License-Identifier: GPL-2.0-or-later
// Big Gnome Center panel appearance and visibility controller.

import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {PanelAutohide} from './panelAutohide.js';

const SETTINGS_SCHEMA = 'org.communitybig.panel-and-dock';
const VALID_VISIBILITY = new Set([
    'always-visible',
    'always-hidden',
    'intelligent',
]);
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
        this._fullscreenWindowActor = null;
        this._fullscreenWindowActorSignals = [];
        this._fullscreenSurface = null;
        this._fullscreenSurfaceSignals = [];
        this._fullscreenSurfaceChildSignals = [];
        this._fullscreenSurfaceRepairIdle = 0;
        this._repairingFullscreenSurface = false;
        this._fullscreenSurfaceRepairCount = 0;

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
        this._autohide = new PanelAutohide(this._panelBox, this._revealZone, () => {
            this._pointerReveal = true;
            this._cancelHide();
            this._applyVisibility();
            this._queueHide();
        });

        this._connect(this._settings, 'changed', () => this._apply());
        this._connect(global.display, 'notify::focus-window', () => {
            this._watchFocusWindow();
            this._applyVisibility();
        });
        this._connect(global.display, 'restacked', () => {
            this._applyVisibility();
            this._ensureFullscreenSurface();
        });
        this._connect(global.display, 'in-fullscreen-changed',
            () => this._onFullscreenChanged());
        this._connect(global.workspace_manager, 'active-workspace-changed',
            () => this._applyVisibility());
        this._connect(Main.layoutManager, 'monitors-changed', () => {
            this._positionRevealZone();
            this._applyVisibility();
        });
        this._connect(this._revealZone, 'leave-event', () => {
            if (!this._panel.hover)
                this._queueHide();
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
        this._autohide.destroy();
        this._cancelOpacityApply();
        this._disconnectFullscreenWindowActor();
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
            fullscreenExitRepairArmed: false,
            fullscreenExitRepairPending: false,
            fullscreenExitRepairAttempts: 0,
            fullscreenExitRepairStage: null,
            fullscreenSurfaceRepairCount: this._fullscreenSurfaceRepairCount,
            fullscreenSurfaceReady: this._fullscreenSurfaceReady(
                this._fullscreenSurface, monitor),
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
            this._disconnectFullscreenWindowActor();
        }
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
                    window.connect(signal, () => this._onWindowGeometryChanged()),
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

    _onFullscreenChanged() {
        if (this._focusWindow?.fullscreen ||
            this._focusMonitor()?.inFullscreen) {
            this._fullscreenSurfaceRepairCount = 0;
            this._ensureFullscreenSurface();
        } else {
            this._disconnectFullscreenWindowActor();
        }
        this._applyVisibility();
    }

    _ensureFullscreenSurface() {
        const window = this._focusWindow;
        if (!window?.fullscreen || !this._focusMonitor()?.inFullscreen)
            return false;
        const actor = global.get_window_actors()
            .find(candidate => candidate.meta_window === window);
        this._watchFullscreenWindowActor(actor);
        this._watchFullscreenSurface(actor);
        this._queueFullscreenSurfaceRepair();
        return Boolean(actor);
    }

    _watchFullscreenSurface(actor) {
        const surface = actor?.get_children().find(child =>
            String(child.constructor?.name)
                .includes('MetaSurfaceContainerActor'));
        if (!surface || surface === this._fullscreenSurface)
            return;

        this._disconnectFullscreenSurface();
        this._fullscreenSurface = surface;
        for (const signal of [
            'child-added',
            'child-removed',
            'notify::x',
            'notify::y',
        ]) {
            try {
                this._fullscreenSurfaceSignals.push([
                    surface,
                    surface.connect(signal, () => {
                        if (signal === 'child-added' || signal === 'child-removed')
                            this._watchFullscreenSurfaceChildren(actor, surface);
                        this._queueFullscreenSurfaceRepair();
                    }),
                ]);
            } catch (error) {
                console.warn(`[community-dock] surface signal ${signal} unavailable: ${error}`);
            }
        }
        this._watchFullscreenSurfaceChildren(actor, surface);
    }

    _watchFullscreenSurfaceChildren(actor, surface) {
        this._disconnectFullscreenSurfaceChildren();
        for (const child of surface.get_children()) {
            for (const signal of [
                'notify::allocation',
                'notify::mapped',
                'notify::x',
                'notify::y',
                'notify::width',
                'notify::height',
            ]) {
                try {
                    this._fullscreenSurfaceChildSignals.push([
                        child,
                        child.connect(signal,
                            () => this._queueFullscreenSurfaceRepair()),
                    ]);
                } catch (error) {
                    console.warn(`[community-dock] surface child signal ${signal} unavailable: ${error}`);
                }
            }
        }
    }

    _watchFullscreenWindowActor(actor) {
        if (!actor || actor === this._fullscreenWindowActor)
            return;

        this._disconnectFullscreenWindowActor();
        this._fullscreenWindowActor = actor;
        const repair = () => {
            this._watchFullscreenSurface(actor);
            this._queueFullscreenSurfaceRepair();
        };
        for (const signal of [
            'child-added',
            'child-removed',
            'notify::x',
            'notify::y',
            'notify::width',
            'notify::height',
        ]) {
            try {
                this._fullscreenWindowActorSignals.push([
                    actor,
                    actor.connect(signal, repair),
                ]);
            } catch (error) {
                console.warn(`[community-dock] window actor signal ${signal} unavailable: ${error}`);
            }
        }
    }

    _disconnectFullscreenWindowActor() {
        for (const [object, id] of
            this._fullscreenWindowActorSignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Mutter may dispose the actor during workspace teardown.
            }
        }
        this._fullscreenWindowActor = null;
        this._disconnectFullscreenSurface();
    }

    _disconnectFullscreenSurface() {
        this._cancelFullscreenSurfaceRepair();
        this._disconnectFullscreenSurfaceChildren();
        for (const [object, id] of this._fullscreenSurfaceSignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Mutter may dispose the surface before the window actor.
            }
        }
        this._fullscreenSurface = null;
        this._repairingFullscreenSurface = false;
    }

    _disconnectFullscreenSurfaceChildren() {
        for (const [object, id] of
            this._fullscreenSurfaceChildSignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Mutter may replace a surface during fullscreen negotiation.
            }
        }
    }

    _queueFullscreenSurfaceRepair() {
        if (this._fullscreenSurfaceRepairIdle)
            return;
        this._fullscreenSurfaceRepairIdle = GLib.idle_add(
            GLib.PRIORITY_DEFAULT_IDLE,
            () => {
                this._fullscreenSurfaceRepairIdle = 0;
                this._repairFullscreenSurface(
                    this._fullscreenWindowActor,
                    this._fullscreenSurface,
                );
                return GLib.SOURCE_REMOVE;
            },
        );
    }

    _cancelFullscreenSurfaceRepair() {
        if (!this._fullscreenSurfaceRepairIdle)
            return;
        GLib.Source.remove(this._fullscreenSurfaceRepairIdle);
        this._fullscreenSurfaceRepairIdle = 0;
    }

    _fullscreenSurfaceReady(surface, monitor) {
        if (!surface || !monitor)
            return false;
        try {
            return surface.get_children().some(child => {
                if (!child.mapped)
                    return false;
                const allocation = child.get_allocation_box();
                return Math.round(allocation.x1) === 0 &&
                    Math.round(allocation.y1) === 0 &&
                    Math.round(allocation.x2 - allocation.x1) ===
                        monitor.width &&
                    Math.round(allocation.y2 - allocation.y1) ===
                        monitor.height;
            });
        } catch (error) {
            // Mutter may replace or dispose the surface during negotiation.
            return false;
        }
    }

    _repairFullscreenSurface(actor, surface) {
        if (this._repairingFullscreenSurface || !actor || !surface)
            return;
        const window = this._focusWindow;
        const monitor = this._focusMonitor();
        if (!window?.fullscreen || !monitor?.inFullscreen ||
            actor.meta_window !== window)
            return;

        const frame = window.get_frame_rect();
        const buffer = window.get_buffer_rect();
        const geometryReady = frame.x === monitor.x &&
            frame.y === monitor.y && frame.width === monitor.width &&
            frame.height === monitor.height && buffer.x === monitor.x &&
            buffer.y === monitor.y && buffer.width === monitor.width &&
            buffer.height === monitor.height &&
            Math.round(actor.x) === monitor.x &&
            Math.round(actor.y) === monitor.y &&
            Math.round(actor.width) === monitor.width &&
            Math.round(actor.height) === monitor.height;
        if (!geometryReady || !this._fullscreenSurfaceReady(surface, monitor) ||
            (Math.round(surface.x) === 0 && Math.round(surface.y) === 0))
            return;

        this._repairingFullscreenSurface = true;
        try {
            surface.set_position(0, 0);
            this._fullscreenSurfaceRepairCount++;
        } finally {
            this._repairingFullscreenSurface = false;
        }
    }

    _onWindowGeometryChanged() {
        this._applyVisibility();
        this._ensureFullscreenSurface();
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
            if (monitorFullscreen) {
                this._autohide.setEnabled(false);
                this._autohide.setVisible(false, true);
                return;
            }

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

            this._autohide.setVisible(visible, this._inOverview);
        } finally {
            this._applying = false;
        }
    }

    _applyPanelTracking(mode) {
        const overlayMode = mode !== 'always-visible';
        this._autohide.setEnabled(overlayMode && !this._inOverview);
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
        this._autohide?.reposition();
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
            children: actor.get_children().map(child =>
                this._childActorDiagnostics(child)),
        };
    }

    _childActorDiagnostics(actor) {
        const [transformedX, transformedY] = actor.get_transformed_position();
        const [transformedWidth, transformedHeight] = actor.get_transformed_size();
        return {
            type: actor.constructor?.name ?? '',
            x: Math.round(actor.x),
            y: Math.round(actor.y),
            width: Math.round(actor.width),
            height: Math.round(actor.height),
            transformedX: Math.round(transformedX),
            transformedY: Math.round(transformedY),
            transformedWidth: Math.round(transformedWidth),
            transformedHeight: Math.round(transformedHeight),
            children: actor.get_children().map(child => ({
                type: child.constructor?.name ?? '',
                x: Math.round(child.x),
                y: Math.round(child.y),
                width: Math.round(child.width),
                height: Math.round(child.height),
            })),
        };
    }
}
