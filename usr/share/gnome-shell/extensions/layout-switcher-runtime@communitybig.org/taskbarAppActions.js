// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Shell from 'gi://Shell';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import * as Utils from './taskbar/utils.js';

const DOUBLE_CLICK_DELAY_MS = 450;
const CLICK_MODIFIERS = Clutter.ModifierType.SHIFT_MASK |
    Clutter.ModifierType.CONTROL_MASK;
const MEMORY_TIME_MS = 3000;

export class TaskbarAppActions {
    constructor(settings) {
        this._settings = settings;
        this._recentLoopId = 0;
        this._recentApp = null;
        this._recentWindows = null;
        this._recentIndex = 0;
        this._recentMonitorIndex = null;
        this._lastAction = '';
        this._actionCounts = {};
    }

    destroy() {
        this.resetRecentlyClickedApp();
        this._settings = null;
    }

    diagnostics() {
        return {
            lastAction: this._lastAction,
            actionCounts: {...this._actionCounts},
        };
    }

    activate(icon, button, modifiers = 0, handleAsGrouped = false) {
        const event = Clutter.get_current_event();
        modifiers = (event?.get_state() ?? modifiers) & CLICK_MODIFIERS;

        const ctrlPressed = modifiers & Clutter.ModifierType.CONTROL_MASK;
        if (ctrlPressed) {
            this._recordAction('LAUNCH');
            return this.launchNewInstance(icon, true);
        }

        let buttonAction = '';
        let doubleClick = false;
        if (button === 2) {
            buttonAction = this._settings.get_string(
                modifiers & Clutter.ModifierType.SHIFT_MASK
                    ? 'shift-middle-click-action'
                    : 'middle-click-action');
        } else if (button === 0 || button === 1) {
            const now = global.get_current_time();
            doubleClick = now - icon.lastClick < DOUBLE_CLICK_DELAY_MS;
            icon.lastClick = now;
            buttonAction = this._settings.get_string(
                modifiers & Clutter.ModifierType.SHIFT_MASK
                    ? 'shift-click-action'
                    : 'click-action');
        }

        const closePreview = () => icon._previewMenu.close(
            this._settings.get_boolean('window-preview-hide-immediate-click'));
        const appCount = icon.getAppIconInterestingWindows().length;
        const previewedIcon = icon._previewMenu.getCurrentAppIcon();

        if (icon.window || buttonAction !== 'TOGGLE-SHOWPREVIEW')
            closePreview();

        const appIsRunning = icon.app.state === Shell.AppState.RUNNING && appCount > 0;
        this._recordAction(appIsRunning && !icon.isLauncher
            ? buttonAction || 'ACTIVATE'
            : 'LAUNCH');
        if (appIsRunning && !icon.isLauncher) {
            if (icon.window && !handleAsGrouped) {
                this._activateUngrouped(icon, buttonAction, button, modifiers);
            } else {
                const result = this._activateGrouped(
                    icon, buttonAction, button, modifiers, doubleClick,
                    appCount, previewedIcon, closePreview);
                if (result !== undefined)
                    return result;
            }
        } else {
            this.launchNewInstance(icon);
        }

        const signalId = GObject.signal_lookup(
            'grab-op-begin', global.display.constructor);
        const signalQuery = signalId && GObject.signal_query(signalId);
        if (signalQuery)
            global.display.emit(
                'grab-op-begin', ...signalQuery.param_types.map(() => null));
        Main.overview.hide();
        return undefined;
    }

    launchNewInstance(icon, ctrlPressed = false) {
        const app = icon.app;
        const maybeAnimate = () => {
            if (this._settings.get_boolean('animate-window-launch'))
                icon.animateLaunch();
        };

        if ((ctrlPressed || app.state === Shell.AppState.RUNNING) &&
            app.can_open_new_window()) {
            maybeAnimate();
            app.open_new_window(-1);
            return;
        }

        const windows = icon.window ? [icon.window] : app.get_windows();
        if (windows.length) {
            Main.activateWindow(windows[0]);
        } else {
            maybeAnimate();
            app.activate();
        }
    }

    minimizeWindow(app, allWindows, monitor) {
        const windows = this.getInterestingWindows(app, monitor);
        const workspace = Utils.DisplayWrapper.getWorkspaceManager()
            .get_active_workspace();
        for (const window of windows) {
            if (window.get_workspace() !== workspace ||
                !window.showing_on_its_workspace())
                continue;
            window.minimize();
            if (!allWindows)
                break;
        }
    }

    activateAllWindows(app, monitor) {
        const windows = this.getInterestingWindows(app, monitor);
        if (!windows.length)
            return;

        Main.activateWindow(windows[0]);
        const workspaceIndex = Utils.DisplayWrapper.getWorkspaceManager()
            .get_active_workspace_index();
        for (let index = windows.length - 1; index >= 0; index--) {
            if (windows[index].get_workspace().index() === workspaceIndex)
                Main.activateWindow(windows[index]);
        }
    }

    activateFirstWindow(app, monitor) {
        const [window] = this.getInterestingWindows(app, monitor);
        if (window)
            Main.activateWindow(window);
    }

    cycleThroughWindows(app, reversed, shouldMinimize, monitor) {
        const windows = this.getInterestingWindows(app, monitor);
        if (shouldMinimize)
            windows.push('MINIMIZE');
        if (!windows.length)
            return;

        if (this._recentLoopId)
            GLib.Source.remove(this._recentLoopId);
        this._recentLoopId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            MEMORY_TIME_MS,
            () => this.resetRecentlyClickedApp());

        if (!this._recentApp || this._recentApp.get_id() !== app.get_id() ||
            this._recentWindows.length !== windows.length ||
            this._recentMonitorIndex !== monitor.index) {
            this._recentApp = app;
            this._recentWindows = windows;
            this._recentIndex = 0;
            this._recentMonitorIndex = monitor.index;
        }

        if (reversed) {
            this._recentIndex--;
            if (this._recentIndex < 0)
                this._recentIndex = this._recentWindows.length - 1;
        } else {
            this._recentIndex++;
        }

        const window = this._recentWindows[
            this._recentIndex % this._recentWindows.length];
        if (window === 'MINIMIZE')
            this.minimizeWindow(app, true, monitor);
        else
            Main.activateWindow(window);
    }

    resetRecentlyClickedApp() {
        if (this._recentLoopId)
            GLib.Source.remove(this._recentLoopId);
        this._recentLoopId = 0;
        this._recentApp = null;
        this._recentWindows = null;
        this._recentIndex = 0;
        this._recentMonitorIndex = null;
        return GLib.SOURCE_REMOVE;
    }

    closeAllWindows(app, monitor) {
        for (const window of this.getInterestingWindows(app, monitor))
            window.delete(global.get_current_time());
    }

    getInterestingWindows(app, monitor, isolateMonitors = false) {
        let windows = (app ? app.get_windows() : Utils.getAllMetaWindows())
            .filter(window => !window.skip_taskbar);

        if (this._settings.get_boolean('isolate-workspaces')) {
            windows = windows.filter(window =>
                window.get_workspace() &&
                window.get_workspace() === Utils.getCurrentWorkspace());
        }

        if (monitor &&
            (isolateMonitors || this._settings.get_boolean('isolate-monitors')) &&
            (this._settings.get_boolean('multi-monitors') ||
             this._settings.get_boolean('isolate-monitors-with-single-panel'))) {
            windows = windows.filter(window => window.get_monitor() === monitor.index);
        }
        return windows;
    }

    _recordAction(action) {
        this._lastAction = action;
        this._actionCounts[action] = (this._actionCounts[action] ?? 0) + 1;
    }

    _activateUngrouped(icon, action, button, modifiers) {
        switch (action) {
        case 'LAUNCH':
            this.launchNewInstance(icon);
            break;
        case 'QUIT':
            icon.window.delete(global.get_current_time());
            break;
        default:
            if (!Main.overview._shown &&
                ['MINIMIZE', 'TOGGLE-SHOWPREVIEW', 'TOGGLE-CYCLE',
                    'TOGGLE-SPREAD', 'CYCLE-MIN'].includes(action) &&
                (icon._isFocusedWindow() ||
                 (action === 'MINIMIZE' &&
                  (button === 2 || modifiers & Clutter.ModifierType.SHIFT_MASK)))) {
                icon.window.minimize();
            } else {
                Main.activateWindow(icon.window);
            }
        }
    }

    _activateGrouped(icon, action, button, modifiers, doubleClick,
        appCount, previewedIcon, closePreview) {
        const monitor = icon.dtpPanel.monitor;
        const appHasFocus = icon._checkIfFocusedApp() && icon._checkIfMonitorHasFocus();

        switch (action) {
        case 'RAISE':
            this.activateAllWindows(icon.app, monitor);
            break;
        case 'LAUNCH':
            this.launchNewInstance(icon);
            break;
        case 'MINIMIZE':
            if (!Main.overview._shown || modifiers) {
                if (appHasFocus || button === 2 ||
                    modifiers & Clutter.ModifierType.SHIFT_MASK) {
                    const allWindows = (button === 1 && !modifiers) || doubleClick;
                    this.minimizeWindow(icon.app, allWindows, monitor);
                } else {
                    this.activateAllWindows(icon.app, monitor);
                }
            } else {
                icon.app.activate();
            }
            break;
        case 'CYCLE':
            if (!Main.overview._shown) {
                if (appHasFocus)
                    this.cycleThroughWindows(icon.app, false, false, monitor);
                else
                    this.activateFirstWindow(icon.app, monitor);
            } else {
                icon.app.activate();
            }
            break;
        case 'CYCLE-MIN':
            if (!Main.overview._shown) {
                const recentWindow = this._recentWindows?.[
                    this._recentIndex % this._recentWindows.length];
                if (appHasFocus ||
                    (this._recentApp === icon.app && recentWindow === 'MINIMIZE')) {
                    this.cycleThroughWindows(icon.app, false, true, monitor);
                } else {
                    this.activateFirstWindow(icon.app, monitor);
                }
            } else {
                icon.app.activate();
            }
            break;
        case 'TOGGLE-SHOWPREVIEW':
            if (!Main.overview._shown) {
                if (appCount === 1) {
                    closePreview();
                    if (appHasFocus)
                        this.minimizeWindow(icon.app, false, monitor);
                    else
                        this.activateFirstWindow(icon.app, monitor);
                } else if (doubleClick) {
                    closePreview();
                    this.minimizeWindow(icon.app, true, monitor);
                } else if (previewedIcon !== icon) {
                    icon._previewMenu.open(icon);
                }
                icon.emit('sync-tooltip');
            } else {
                icon.app.activate();
            }
            break;
        case 'TOGGLE-CYCLE':
            if (!Main.overview._shown) {
                if (appCount === 1) {
                    if (appHasFocus)
                        this.minimizeWindow(icon.app, false, monitor);
                    else
                        this.activateFirstWindow(icon.app, monitor);
                } else {
                    this.cycleThroughWindows(icon.app, false, false, monitor);
                }
            } else {
                icon.app.activate();
            }
            break;
        case 'QUIT':
            this.closeAllWindows(icon.app, monitor);
            break;
        case 'TOGGLE-SPREAD':
            if (appCount === 1) {
                if (appHasFocus && !Main.overview._shown)
                    this.minimizeWindow(icon.app, false, monitor);
                else
                    this.activateFirstWindow(icon.app, monitor);
            } else {
                return icon.dtpPanel.panelManager.showFocusedAppInOverview(icon.app);
            }
            break;
        default:
            this.launchNewInstance(icon);
        }
        return undefined;
    }
}
