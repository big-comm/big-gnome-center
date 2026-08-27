// SPDX-License-Identifier: GPL-2.0-or-later

import * as AppDisplay from 'resource:///org/gnome/shell/ui/appDisplay.js';
import * as BoxPointer from 'resource:///org/gnome/shell/ui/boxpointer.js';
import {InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Layout from 'resource:///org/gnome/shell/ui/layout.js';
import * as LookingGlass from 'resource:///org/gnome/shell/ui/lookingGlass.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import St from 'gi://St';

import * as Utils from '../community-panel@communitybig.org/utils.js';
import {SETTINGS} from '../community-panel@communitybig.org/runtimeContext.js';

export class TaskbarShellHooks {
    constructor() {
        this._owner = null;
        this._records = [];
        this._installedHooks = [];
        this._injectionManager = null;
        this._forceHotCornerId = 0;
        this._enableHotCornersId = 0;
        this._shutdownId = 0;
        this._clickGestureEnabled = null;
        this._activated = false;
        this._active = false;
        this._generation = 0;
        this._restoreConflicts = 0;
        this._lastConflict = '';
    }

    prepare(manager) {
        if (this._owner === manager)
            return;
        this.destroy();
        this._owner = manager;
        this._generation++;
        this._lastConflict = '';

        try {
            const appIconPrototype = AppDisplay.AppIcon.prototype;
            if (!appIconPrototype._removeMenuTimeout) {
                this._assign(
                    appIconPrototype,
                    '_setPopupTimeout',
                    this._emptyFunc,
                    'app-icon-popup-timeout',
                );
                this._assign(
                    appIconPrototype,
                    '_removeMenuTimeout',
                    this._emptyFunc,
                    'app-icon-remove-timeout',
                );
            }

            this._assign(
                Main.layoutManager,
                'findIndexForActor',
                actor => '_dtpIndex' in actor
                    ? actor._dtpIndex
                    : Layout.LayoutManager.prototype.findIndexForActor.call(
                        Main.layoutManager, actor),
                'actor-monitor-index',
            );
        } catch (error) {
            this.destroy(manager);
            throw error;
        }
    }

    activate(manager, callbacks) {
        if (this._owner !== manager)
            throw new Error('Taskbar Shell hooks were not prepared');
        if (this._activated)
            return;

        try {
            this._installLayoutHooks(manager, callbacks);
            this._installOverviewHooks(manager, callbacks);
            this._installLookingGlassHooks(callbacks);
            this._installMessageTrayHook(manager);
            this._activated = true;
        } catch (error) {
            this.destroy(manager);
            throw error;
        }
    }

    finish(manager) {
        if (this._owner !== manager || !this._activated)
            throw new Error('Taskbar Shell hooks were not activated');
        if (this._active)
            return;

        try {
            this._installPanelStyleHook();
            this._shutdownId = global.connect('shutdown', () => {
                for (const panel of manager.allPanels)
                    manager._removePanelBarriers(panel);
            });
            this._installedHooks.push('shutdown-cleanup');
            this._active = true;
        } catch (error) {
            this.destroy(manager);
            throw error;
        }
    }

    destroy(owner = null) {
        if (owner && owner !== this._owner)
            return;

        if (this._shutdownId) {
            try {
                global.disconnect(this._shutdownId);
            } catch (error) {
                // Shell shutdown can dispose the global object first.
            }
            this._shutdownId = 0;
        }
        if (this._forceHotCornerId) {
            try {
                SETTINGS?.disconnect(this._forceHotCornerId);
            } catch (error) {
                console.warn(
                    `[layout-switcher-runtime] hot-corner setting cleanup failed: ${error}`,
                );
            }
            this._forceHotCornerId = 0;
        }
        if (this._enableHotCornersId) {
            try {
                Main.layoutManager._interfaceSettings?.disconnect(
                    this._enableHotCornersId);
            } catch (error) {
                console.warn(
                    `[layout-switcher-runtime] hot-corner interface cleanup failed: ${error}`,
                );
            }
            this._enableHotCornersId = 0;
        }

        try {
            this._injectionManager?.clear();
        } catch (error) {
            console.warn(
                `[layout-switcher-runtime] Shell injection cleanup failed: ${error}`,
            );
        }
        this._injectionManager = null;
        this._restoreRecords();

        if (this._clickGestureEnabled !== null && Main.panel?._clickGesture)
            Main.panel._clickGesture.set_enabled(this._clickGestureEnabled);
        this._clickGestureEnabled = null;

        if (this._active) {
            Main.layoutManager._updateHotCorners?.();
            Main.layoutManager._updatePanelBarrier?.();
        }

        this._owner = null;
        this._activated = false;
        this._active = false;
        this._installedHooks = [];
    }

    diagnostics() {
        return {
            available: true,
            owned: Boolean(this._owner),
            active: this._active,
            generation: this._generation,
            restorationPending: this._records.length > 0,
            installedHooks: [...this._installedHooks],
            injectionManagerOwned: Boolean(this._injectionManager),
            shutdownConnected: Boolean(this._shutdownId),
            restoreConflicts: this._restoreConflicts,
            lastConflict: this._lastConflict,
        };
    }

    _installLayoutHooks(manager, callbacks) {
        this._assign(
            Main.layoutManager,
            '_updatePanelBarrier',
            panel => {
                const panels = panel ? [panel] : manager.allPanels;
                for (const candidate of panels) {
                    callbacks.updatePanelBarrier.call(
                        Main.layoutManager, candidate);
                }
            },
            'panel-barriers',
        );
        Main.layoutManager._updatePanelBarrier();

        this._assign(
            Main.layoutManager,
            '_updateHotCorners',
            callbacks.updateHotCorners.bind(Main.layoutManager),
            'hot-corners',
        );
        Main.layoutManager._updateHotCorners();
        this._forceHotCornerId = SETTINGS.connect(
            'changed::stockgs-force-hotcorner',
            () => Main.layoutManager._updateHotCorners(),
        );
        if (Main.layoutManager._interfaceSettings) {
            this._enableHotCornersId =
                Main.layoutManager._interfaceSettings.connect(
                    'changed::enable-hot-corners',
                    () => Main.layoutManager._updateHotCorners(),
                );
        }
    }

    _installOverviewHooks(manager, callbacks) {
        const display =
            Main.overview._overview._controls._workspacesDisplay;
        this._assign(
            display,
            '_updateWorkspacesViews',
            callbacks.updateWorkspacesViews.bind(display),
            'overview-workspace-views',
        );
        this._assign(
            display,
            'setPrimaryWorkspaceVisible',
            callbacks.setPrimaryWorkspaceVisible.bind(display),
            'overview-primary-workspace',
        );

        this._injectionManager = new InjectionManager();
        this._injectionManager.overrideMethod(
            BoxPointer.BoxPointer.prototype,
            'vfunc_get_preferred_height',
            () => function (forWidth) {
                const alloc = {min_size: 0, natural_size: 0};
                [alloc.min_size, alloc.natural_size] =
                    this.vfunc_get_preferred_height(forWidth);
                return manager._getBoxPointerPreferredHeight(this, alloc);
            },
        );
        this._installedHooks.push('box-pointer-height');

        const activitiesChild =
            Main.panel.statusArea.activities.get_first_child();
        if (activitiesChild?.constructor.name === 'WorkspaceIndicators') {
            this._injectionManager.overrideMethod(
                Object.getPrototypeOf(activitiesChild.get_first_child()),
                'vfunc_get_preferred_width',
                getPreferredWidth => function (forHeight) {
                    return Utils.getBoxLayoutVertical(this.get_parent())
                        ? [0, forHeight]
                        : getPreferredWidth.call(this, forHeight);
                },
            );
            this._installedHooks.push('workspace-indicator-width');
        }

        if (Main.panel._clickGesture) {
            this._clickGestureEnabled =
                Main.panel._clickGesture.get_enabled?.() ??
                Boolean(Main.panel._clickGesture.enabled);
            Main.panel._clickGesture.set_enabled(false);
            this._installedHooks.push('panel-click-gesture');
        }
    }

    _installLookingGlassHooks(callbacks) {
        const prototype = LookingGlass.LookingGlass.prototype;
        const originalResize = prototype._resize;
        this._assign(
            prototype,
            '_resize',
            function (...args) {
                return callbacks.resizeLookingGlass.call(
                    this, originalResize, ...args);
            },
            'looking-glass-resize',
        );
        const originalOpen = prototype.open;
        this._assign(
            prototype,
            'open',
            function (...args) {
                return callbacks.openLookingGlass.call(
                    this, originalOpen, ...args);
            },
            'looking-glass-open',
        );
    }

    _installMessageTrayHook(manager) {
        const bannerBin = Main.messageTray._bannerBin;
        const nativeEase = Object.getPrototypeOf(bannerBin).ease;
        this._assign(
            bannerBin,
            'ease',
            params => {
                if (params.y === 0) {
                    const panel = manager.allPanels.find(candidate =>
                        candidate.monitor === Main.layoutManager.primaryMonitor);
                    if (panel?.intellihide?.enabled &&
                        panel.geom.position === St.Side.TOP &&
                        panel.panelBox.visible) {
                        params.y += panel.geom.outerSize;
                    }
                }
                nativeEase.call(bannerBin, params);
            },
            'message-banner-offset',
        );
    }

    _installPanelStyleHook() {
        if (SETTINGS.get_boolean('stockgs-keep-top-panel'))
            return;
        this._define(
            Main.panel,
            'style',
            {configurable: true, set() {}},
            'native-panel-style-guard',
        );
    }

    _assign(object, key, value, label) {
        this._record(object, key, label);
        object[key] = value;
        this._records.at(-1).installed =
            Object.getOwnPropertyDescriptor(object, key);
        this._installedHooks.push(label);
    }

    _define(object, key, descriptor, label) {
        this._record(object, key, label);
        Object.defineProperty(object, key, descriptor);
        this._records.at(-1).installed =
            Object.getOwnPropertyDescriptor(object, key);
        this._installedHooks.push(label);
    }

    _record(object, key, label) {
        this._records.push({
            object,
            key,
            label,
            original: Object.getOwnPropertyDescriptor(object, key),
            installed: null,
        });
    }

    _restoreRecords() {
        for (const record of this._records.reverse()) {
            try {
                const current = Object.getOwnPropertyDescriptor(
                    record.object, record.key);
                if (!this._descriptorsMatch(current, record.installed)) {
                    this._restoreConflicts++;
                    this._lastConflict = record.label;
                    console.warn(
                        `[layout-switcher-runtime] Shell hook changed externally: ${record.label}`,
                    );
                    continue;
                }
                if (record.original) {
                    Object.defineProperty(
                        record.object, record.key, record.original);
                } else {
                    delete record.object[record.key];
                }
            } catch (error) {
                this._restoreConflicts++;
                this._lastConflict = record.label;
                console.warn(
                    `[layout-switcher-runtime] Shell hook restore failed (${record.label}): ${error}`,
                );
            }
        }
        this._records = [];
    }

    _descriptorsMatch(left, right) {
        if (!left || !right)
            return left === right;
        return left.value === right.value &&
            left.get === right.get && left.set === right.set;
    }

    _emptyFunc() {}
}
