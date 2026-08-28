/*
 * This file is part of the Dash-To-Panel extension for Gnome 3.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Status styling derives from Dash-to-Panel panelStyle.js. Recursive actor
 * styling was inspired by StatusAreaHorizontalSpacing.
 */

import GLib from 'gi://GLib';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class TaskbarStatusFullscreenIntegration {
    constructor(settings) {
        this._settings = settings;
        this._styles = new Map();
        this._tracked = new Map();
        this._signalRecords = [];
        this._generation = 0;
        this._restoreConflicts = 0;
        this._lastConflict = '';
        this._fullscreenEvents = 0;
        this._overviewEntries = 0;
        this._overviewExits = 0;
        this._visibilityUpdates = 0;
        this._trackMutations = 0;
        this._surfaceGuard = new FullscreenSurfaceGuard(
            () => this._fullscreenEvents++);
    }

    style(panel) {
        if (this._styles.has(panel))
            return;
        const style = new StatusStyleOwner(
            panel,
            this._settings,
            label => this._recordConflict(label),
        );
        style.enable();
        this._styles.set(panel, style);
    }

    unstyle(panel) {
        const style = this._styles.get(panel);
        if (!style)
            return;
        style.disable();
        this._styles.delete(panel);
    }

    track(panel) {
        if (this._tracked.has(panel))
            return;
        const actorData = this._trackedActorData(panel.panelBox);
        if (!actorData)
            throw new Error('Taskbar panelBox is not tracked');
        this._tracked.set(panel, {
            actorData,
            original: this._trackingState(actorData),
            installed: this._trackingState(actorData),
        });
        if (!this._signalRecords.length)
            this._connectSignals();
        this._generation++;
        this._syncOverview();
    }

    setIntellihideTracking(panel, enable) {
        const record = this._tracked.get(panel);
        if (!record)
            throw new Error('Taskbar fullscreen owner is not tracking panel');
        this._setTracking(record, {
            affectsStruts: !enable,
            trackFullscreen: !enable,
        });
        panel.panelBox.visible = enable ? true : panel.panelBox.visible;
        Main.layoutManager._queueUpdateRegions();
    }

    release(panel) {
        this.unstyle(panel);
        const record = this._tracked.get(panel);
        if (!record)
            return;
        const current = this._trackingState(record.actorData);
        if (this._trackingStatesMatch(current, record.installed)) {
            Object.assign(record.actorData, record.original);
        } else {
            this._recordConflict(`panel-${panel.monitor?.index ?? 'unknown'}-tracking`);
        }
        this._tracked.delete(panel);
        Main.layoutManager._queueUpdateRegions();
        if (!this._tracked.size)
            this._disconnectSignals();
    }

    destroy() {
        for (const panel of [...this._styles.keys()])
            this.unstyle(panel);
        for (const panel of [...this._tracked.keys()])
            this.release(panel);
        this._disconnectSignals();
    }

    diagnostics() {
        const styles = [...this._styles.values()];
        return {
            implementation: 'layout-switcher-runtime',
            active: this._tracked.size > 0,
            connected: this._signalRecords.length === 2 &&
                this._surfaceGuard.connected(),
            generation: this._generation,
            panelsOwned: this._tracked.size,
            styledPanels: this._styles.size,
            signalsOwned: this._signalRecords.length +
                this._surfaceGuard.rootSignalsOwned(),
            styledActors: styles.reduce(
                (total, style) => total + style.styledActors(), 0),
            orphanStyles: styles.reduce(
                (total, style) => total + style.orphanStyles(), 0),
            restorationPending: this._tracked.size > 0 ||
                styles.some(style => style.restorationPending()),
            restoreConflicts: this._restoreConflicts,
            lastConflict: this._lastConflict,
            fullscreenEvents: this._fullscreenEvents,
            overviewEntries: this._overviewEntries,
            overviewExits: this._overviewExits,
            visibilityUpdates: this._visibilityUpdates,
            trackMutations: this._trackMutations,
            fullscreenSurface: this._surfaceGuard.diagnostics(),
            panels: [...this._tracked.keys()].map(panel => {
                const data = this._trackedActorData(panel.panelBox);
                return {
                    monitor: panel.monitor?.index ?? -1,
                    monitorFullscreen: Boolean(panel.monitor?.inFullscreen),
                    visible: Boolean(panel.panelBox.visible),
                    mapped: Boolean(panel.panelBox.mapped),
                    affectsStruts: Boolean(data?.affectsStruts),
                    trackFullscreen: Boolean(data?.trackFullscreen),
                    intellihideEnabled: Boolean(panel.intellihide?.enabled),
                };
            }),
        };
    }

    _connectSignals() {
        this._connect(Main.overview, 'showing', () => {
            this._overviewEntries++;
            this._syncOverview();
        });
        this._connect(Main.overview, 'hiding', () => {
            this._overviewExits++;
            this._syncOverview();
        });
        this._surfaceGuard.enable();
    }

    _connect(object, signal, callback) {
        this._signalRecords.push({object, id: object.connect(signal, callback)});
    }

    _disconnectSignals() {
        this._surfaceGuard.destroy();
        for (const {object, id} of this._signalRecords.splice(0).reverse()) {
            try {
                object.disconnect(id);
            } catch (error) {
                console.warn(
                    `[layout-switcher-runtime] status/fullscreen signal cleanup failed: ${error}`,
                );
            }
        }
    }

    _syncOverview() {
        const isOverview = Boolean(Main.overview.visibleTarget);
        for (const [panel, record] of this._tracked) {
            const isFocused = panel.panelManager.checkIfFocusedMonitor(
                panel.monitor);
            this._setTracking(record, {
                affectsStruts: record.actorData.affectsStruts,
                trackFullscreen: !isOverview,
            });
            panel.panelBox[!isOverview || isFocused ? 'show' : 'hide']();
            this._visibilityUpdates++;
        }
        Main.layoutManager._updateVisibility();
    }

    _setTracking(record, state) {
        record.actorData.affectsStruts = state.affectsStruts;
        record.actorData.trackFullscreen = state.trackFullscreen;
        record.installed = {...state};
        this._trackMutations++;
    }

    _trackedActorData(actor) {
        return Main.layoutManager._trackedActors.find(
            candidate => candidate.actor === actor) ?? null;
    }

    _trackingState(actorData) {
        return {
            affectsStruts: Boolean(actorData.affectsStruts),
            trackFullscreen: Boolean(actorData.trackFullscreen),
        };
    }

    _trackingStatesMatch(left, right) {
        return left.affectsStruts === right.affectsStruts &&
            left.trackFullscreen === right.trackFullscreen;
    }

    _recordConflict(label) {
        this._restoreConflicts++;
        this._lastConflict = label;
        console.warn(
            `[layout-switcher-runtime] status/fullscreen state changed externally: ${label}`,
        );
    }
}

class FullscreenSurfaceGuard {
    constructor(onFullscreen) {
        this._onFullscreen = onFullscreen;
        this._signals = [];
        this._window = null;
        this._windowSignals = [];
        this._windowActor = null;
        this._windowActorSignals = [];
        this._surface = null;
        this._surfaceSignals = [];
        this._surfaceChildSignals = [];
        this._repairIdle = 0;
        this._repairing = false;
        this._repairCount = 0;
    }

    enable() {
        if (this._signals.length)
            return;
        this._connect(global.display, 'notify::focus-window', () => {
            this._watchFocusWindow();
        });
        this._connect(global.display, 'restacked', () => {
            this._ensureSurface();
        });
        this._connect(global.display, 'in-fullscreen-changed', () => {
            this._onFullscreen();
            if (this._window?.fullscreen || this._focusMonitor()?.inFullscreen) {
                this._repairCount = 0;
                this._ensureSurface();
            } else {
                this._disconnectWindowActor();
            }
        });
        this._watchFocusWindow();
    }

    destroy() {
        this._disconnectWindowActor();
        this._disconnectWindow();
        for (const [object, id] of this._signals.splice(0).reverse()) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Shell shutdown can dispose the display first.
            }
        }
    }

    connected() {
        return this._signals.length === 3;
    }

    rootSignalsOwned() {
        return this._signals.length;
    }

    diagnostics() {
        const monitor = this._focusMonitor();
        return {
            focusWindowConnected: this._windowSignals.length > 0,
            windowSignalsOwned: this._windowSignals.length,
            windowActorSignalsOwned: this._windowActorSignals.length,
            surfaceSignalsOwned: this._surfaceSignals.length,
            surfaceChildSignalsOwned: this._surfaceChildSignals.length,
            repairPending: Boolean(this._repairIdle),
            repairCount: this._repairCount,
            surfaceReady: this._surfaceReady(this._surface, monitor),
        };
    }

    _connect(object, signal, callback) {
        try {
            this._signals.push([object, object.connect(signal, callback)]);
        } catch (error) {
            console.warn(
                `[layout-switcher-runtime] fullscreen signal unavailable (${signal}): ${error}`,
            );
        }
    }

    _watchFocusWindow() {
        const previous = this._window;
        this._disconnectWindow();
        const window = global.display.focus_window;
        if (previous && previous !== window)
            this._disconnectWindowActor();
        if (!window)
            return;
        this._window = window;
        for (const signal of [
            'position-changed',
            'size-changed',
            'notify::fullscreen',
            'unmanaged',
        ]) {
            try {
                this._windowSignals.push([
                    window,
                    window.connect(signal, () => this._ensureSurface()),
                ]);
            } catch (error) {
                console.warn(
                    `[layout-switcher-runtime] fullscreen window signal unavailable (${signal}): ${error}`,
                );
            }
        }
        this._ensureSurface();
    }

    _disconnectWindow() {
        for (const [object, id] of this._windowSignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Mutter may dispose the window during teardown.
            }
        }
        this._window = null;
    }

    _ensureSurface() {
        const window = this._window;
        if (!window?.fullscreen || !this._focusMonitor()?.inFullscreen)
            return false;
        const actor = global.get_window_actors().find(
            candidate => candidate.meta_window === window);
        this._watchWindowActor(actor);
        this._watchSurface(actor);
        this._queueRepair();
        return Boolean(actor);
    }

    _watchWindowActor(actor) {
        if (!actor || actor === this._windowActor)
            return;
        this._disconnectWindowActor();
        this._windowActor = actor;
        const repair = () => {
            this._watchSurface(actor);
            this._queueRepair();
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
                this._windowActorSignals.push([
                    actor, actor.connect(signal, repair),
                ]);
            } catch (error) {
                console.warn(
                    `[layout-switcher-runtime] fullscreen actor signal unavailable (${signal}): ${error}`,
                );
            }
        }
    }

    _watchSurface(actor) {
        const surface = actor?.get_children().find(child =>
            String(child.constructor?.name)
                .includes('MetaSurfaceContainerActor'));
        if (!surface || surface === this._surface)
            return;
        this._disconnectSurface();
        this._surface = surface;
        for (const signal of [
            'child-added',
            'child-removed',
            'notify::x',
            'notify::y',
        ]) {
            try {
                this._surfaceSignals.push([
                    surface,
                    surface.connect(signal, () => {
                        if (signal === 'child-added' || signal === 'child-removed')
                            this._watchSurfaceChildren(surface);
                        this._queueRepair();
                    }),
                ]);
            } catch (error) {
                console.warn(
                    `[layout-switcher-runtime] fullscreen surface signal unavailable (${signal}): ${error}`,
                );
            }
        }
        this._watchSurfaceChildren(surface);
    }

    _watchSurfaceChildren(surface) {
        this._disconnectSurfaceChildren();
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
                    this._surfaceChildSignals.push([
                        child,
                        child.connect(signal, () => this._queueRepair()),
                    ]);
                } catch (error) {
                    console.warn(
                        `[layout-switcher-runtime] fullscreen surface child signal unavailable (${signal}): ${error}`,
                    );
                }
            }
        }
    }

    _disconnectWindowActor() {
        for (const [object, id] of this._windowActorSignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Mutter may dispose the actor during workspace teardown.
            }
        }
        this._windowActor = null;
        this._disconnectSurface();
    }

    _disconnectSurface() {
        this._cancelRepair();
        this._disconnectSurfaceChildren();
        for (const [object, id] of this._surfaceSignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Mutter may replace the surface during fullscreen negotiation.
            }
        }
        this._surface = null;
        this._repairing = false;
    }

    _disconnectSurfaceChildren() {
        for (const [object, id] of this._surfaceChildSignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Mutter may dispose a surface child first.
            }
        }
    }

    _queueRepair() {
        if (this._repairIdle)
            return;
        this._repairIdle = GLib.idle_add(
            GLib.PRIORITY_DEFAULT_IDLE,
            () => {
                this._repairIdle = 0;
                this._repairSurface(this._windowActor, this._surface);
                return GLib.SOURCE_REMOVE;
            },
        );
    }

    _cancelRepair() {
        if (!this._repairIdle)
            return;
        GLib.Source.remove(this._repairIdle);
        this._repairIdle = 0;
    }

    _repairSurface(actor, surface) {
        if (this._repairing || !actor || !surface)
            return;
        const window = this._window;
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
        if (!geometryReady || !this._surfaceReady(surface, monitor) ||
            (Math.round(surface.x) === 0 && Math.round(surface.y) === 0))
            return;
        this._repairing = true;
        try {
            surface.set_position(0, 0);
            this._repairCount++;
        } finally {
            this._repairing = false;
        }
    }

    _surfaceReady(surface, monitor) {
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
            return false;
        }
    }

    _focusMonitor() {
        const index = this._window?.get_monitor();
        if (!Number.isInteger(index))
            return null;
        return Main.layoutManager.monitors[index] ?? null;
    }
}

class StatusStyleOwner {
    constructor(panel, settings, conflict) {
        this._panel = panel;
        this._settings = settings;
        this._conflict = conflict;
        this._records = new Map();
        this._settingsIds = [];
        this._actorSignalRecords = [];
        this._refreshPanelButtons = true;
        this._ignoreAddedChild = false;
    }

    enable() {
        this._applyStyles();
        for (const key of [
            'tray-size',
            'leftbox-size',
            'tray-padding',
            'leftbox-padding',
            'status-icon-padding',
        ]) {
            this._settingsIds.push(this._settings.connect(
                `changed::${key}`,
                () => {
                    this._removeStyles(true);
                    this._applyStyles();
                },
            ));
        }
    }

    disable() {
        for (const id of this._settingsIds)
            this._settings.disconnect(id);
        this._settingsIds = [];
        this._refreshPanelButtons = false;
        this._removeStyles(false);
    }

    styledActors() {
        return this._records.size;
    }

    orphanStyles() {
        return [...this._records.keys()].filter(
            actor => !actor.get_parent?.()).length;
    }

    restorationPending() {
        return this._records.size > 0 || this._actorSignalRecords.length > 0;
    }

    _applyStyles() {
        const vertical = this._panel.geom.vertical;
        const padding = value => vertical
            ? `padding: ${value}px 0`
            : `padding: 0 ${value}px`;
        const trayOperations = [];
        const trayPadding = this._settings.get_int('tray-padding');
        if (trayPadding >= 0) {
            const style = vertical
                ? padding(trayPadding)
                : `-natural-hpadding: ${trayPadding}px${
                    trayPadding < 6
                        ? `; -minimum-hpadding: ${trayPadding}px`
                        : ''}`;
            trayOperations.push({
                matches: actor => vertical
                    ? this._isVerticalTrayActor(actor)
                    : actor.has_style_class_name?.('panel-button'),
                apply: (actor, index) => {
                    this._overrideStyle(actor, style, index);
                    this._refreshPanelButton(actor);
                },
            });
        }

        const statusPadding = this._settings.get_int('status-icon-padding');
        if (statusPadding >= 0) {
            trayOperations.push({
                matches: actor => actor.has_style_class_name?.(
                    'system-status-icon'),
                apply: (actor, index) => this._overrideStyle(
                    actor, padding(statusPadding), index),
            });
        }

        const traySize = this._settings.get_int('tray-size');
        if (traySize > 0) {
            trayOperations.push(this._typeStyle(
                'St_Icon', `icon-size: ${traySize}px`));
            trayOperations.push(this._typeStyle(
                'St_Label', `font-size: ${traySize}px`));
            this._overrideStyle(
                this._panel._rightBox, `font-size: ${traySize}px`, 0);
            this._overrideStyle(
                this._panel._centerBox, `font-size: ${traySize}px`, 0);
        }

        const leftOperations = [];
        const leftPadding = this._settings.get_int('leftbox-padding');
        if (leftPadding >= 0) {
            leftOperations.push({
                matches: actor => actor.get_parent?.()
                    ?.has_style_class_name?.('panel-button'),
                apply: (actor, index) => this._overrideStyle(
                    actor, padding(leftPadding), index),
            });
        }
        const leftSize = this._settings.get_int('leftbox-size');
        if (leftSize > 0) {
            leftOperations.push(this._typeStyle(
                'St_Icon', `icon-size: ${leftSize}px`));
            leftOperations.push(this._typeStyle(
                'St_Label', `font-size: ${leftSize}px`));
            this._overrideStyle(
                this._panel._leftBox, `font-size: ${leftSize}px`, 0);
        }

        this._operations = {
            right: trayOperations,
            center: trayOperations,
            left: leftOperations,
        };
        this._applyStylesRecursively();
        this._watchBox(this._panel._rightBox, trayOperations, true);
        this._watchBox(this._panel._centerBox, trayOperations, true);
        this._watchBox(this._panel._leftBox, leftOperations, false);
    }

    _removeStyles(refresh) {
        for (const {object, id} of this._actorSignalRecords.splice(0))
            object.disconnect(id);
        for (const actor of [...this._records.keys()])
            this._restoreStyle(actor, refresh);
        this._operations = null;
    }

    _applyStylesRecursively() {
        const quickSettings = this._panel.statusArea.quickSettings?.container;
        const dateMenu = this._panel.statusArea.dateMenu?.container;
        const groups = [
            [this._panel._rightBox, quickSettings, this._operations.right],
            [this._panel._centerBox, dateMenu, this._operations.center],
            [this._panel._leftBox, null, this._operations.left],
        ];
        for (const [box, extra, operations] of groups) {
            const children = box.get_children();
            if (extra)
                children.push(extra);
            for (const child of children)
                this._recursiveApply(child, operations);
        }
    }

    _watchBox(box, operations, respectsIgnore) {
        const id = box.connect('child-added', (_container, actor) => {
            if (operations.length && (!respectsIgnore || !this._ignoreAddedChild))
                this._recursiveApply(actor, operations);
            this._ignoreAddedChild = false;
        });
        this._actorSignalRecords.push({object: box, id});
    }

    _recursiveApply(actor, operations) {
        operations.forEach((operation, index) => {
            if (operation.matches(actor))
                operation.apply(actor, index);
        });
        for (const child of actor.get_children?.() ?? [])
            this._recursiveApply(child, operations);
    }

    _overrideStyle(actor, line, operation) {
        let record = this._records.get(actor);
        if (!record) {
            record = {
                original: actor.get_style(),
                installed: null,
                overrides: new Map(),
                destroyId: actor.connect('destroy', () => {
                    this._records.delete(actor);
                }),
            };
            this._records.set(actor, record);
        }
        record.overrides.set(operation, line);
        record.installed = `${[...record.overrides.values()].join('; ')}; ${
            record.original || ''}`;
        actor.set_style(record.installed);
    }

    _restoreStyle(actor, refresh) {
        const record = this._records.get(actor);
        if (!record)
            return;
        try {
            actor.disconnect(record.destroyId);
            if (actor.get_style() === record.installed) {
                actor.set_style(record.original);
            } else {
                this._conflict(this._actorLabel(actor));
            }
        } catch (error) {
            this._conflict(this._actorLabel(actor));
        }
        this._records.delete(actor);
        if (refresh && this._refreshPanelButtons &&
            actor.has_style_class_name?.('panel-button'))
            this._refreshPanelButton(actor);
    }

    _refreshPanelButton(actor) {
        if (!actor.visible)
            return;
        const parent = actor.get_parent?.();
        if (!parent)
            return;
        const children = parent.get_children();
        const index = Math.max(0, children.indexOf(actor));
        this._ignoreAddedChild = [
            this._panel._centerBox,
            this._panel._rightBox,
        ].includes(parent);
        parent.remove_child(actor);
        parent.insert_child_at_index(actor, index);
    }

    _isVerticalTrayActor(actor) {
        const parent = actor.get_parent?.();
        return Boolean(
            parent?.has_style_class_name?.('panel-button') &&
            !parent.has_style_class_name('clock-display') ||
            actor.has_style_class_name?.('clock'));
    }

    _typeStyle(type, line) {
        return {
            matches: actor => actor.constructor?.name === type,
            apply: (actor, index) => this._overrideStyle(actor, line, index),
        };
    }

    _actorLabel(actor) {
        return actor.name ?? actor.get_name?.() ?? actor.constructor?.name ??
            'unknown-actor';
    }
}
