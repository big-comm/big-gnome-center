/*
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Derived from Dash to Panel overview.js.
 */

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as WindowManager from 'resource:///org/gnome/shell/ui/windowManager.js';
import {WindowPreview} from 'resource:///org/gnome/shell/ui/windowPreview.js';

import * as Intellihide from '../community-panel@communitybig.org/intellihide.js';
import * as Utils from '../community-panel@communitybig.org/utils.js';
import {SETTINGS} from '../community-panel@communitybig.org/runtimeContext.js';

const GS_SWITCH_HOTKEYS_KEY = 'switch-to-application-';
const GS_OPEN_HOTKEYS_KEY = 'open-new-window-application-';
const LABEL_MARGIN = 60;
const NUMBER_OVERLAY_TIMEOUT = 'number-overlay';

export class TaskbarOverviewIntegration {
    constructor(panelManager) {
        this._panelManager = panelManager;
        this._panel = null;
        this.taskbar = null;
        this._signals = [];
        this._overrides = [];
        this._timeouts = new Map();
        this._ownedKeybindings = new Set();
        this._removedNativeKeybindings = new Set();
        this._dash = null;
        this._dashOwnedState = null;
        this._hotkeyPreviewCycleInfo = null;
        this._hotKeysEnabled = false;
        this._extraShortcutOwned = false;
        this._clickToExitOwned = false;
        this._active = false;
        this._entryCount = 0;
        this._exitCount = 0;
        this._stateChangeCount = 0;
        this._allocationCount = 0;
        this._restoreConflicts = 0;
        this._lastConflict = '';
        this._lastState = 'hidden';
    }

    enable(primaryPanel) {
        if (this._active)
            return;

        this._panel = primaryPanel;
        this.taskbar = primaryPanel.taskbar;

        try {
            this._connectOverviewState();
            this._connectSettings();
            this._syncWorkspaceIsolation(false);
            this._syncHotkeys();
            this._syncNumberOverlay();
            this._syncClickToExit();
            this._toggleDash();
            this._installAllocationHook();
            this._active = true;
        } catch (error) {
            this.disable();
            throw error;
        }
    }

    disable() {
        this._endHotkeyPreviewCycle();
        this._clearTimeouts();
        this._disableClickToExit();
        this._disableExtraShortcut();
        this._disableHotKeys();
        this._restoreOverrides();
        this._restoreDash();
        this._disconnectAll();

        this._panel = null;
        this.taskbar = null;
        this._active = false;
    }

    diagnostics() {
        const controls = Main.overview?._overview?._controls;
        const state = Number(controls?._stateAdjustment?.value ?? 0);
        const searchController = controls?._searchController;
        const hookLabels = [...new Set(this._overrides.map(record => record.label))];
        return {
            implementation: 'layout-switcher-runtime',
            connected: Boolean(
                this._active &&
                this._signals.length &&
                hookLabels.includes('overview-allocation')
            ),
            active: this._active,
            signalsOwned: this._signals.length,
            hooksOwned: this._overrides.length,
            hookLabels,
            allocationHookOwned: hookLabels.includes('overview-allocation'),
            workspaceIsolationOwned:
                hookLabels.includes('workspace-isolation'),
            configuredWorkspaceIsolation:
                SETTINGS?.get_boolean('isolate-workspaces') ?? false,
            hotkeysEnabled: this._hotKeysEnabled,
            configuredHotkeys: SETTINGS?.get_boolean('hot-keys') ?? false,
            keybindingsOwned: this._ownedKeybindings.size,
            nativeKeybindingsSuppressed: this._removedNativeKeybindings.size,
            clickToExitOwned: this._clickToExitOwned,
            configuredClickToExit:
                SETTINGS?.get_boolean('overview-click-to-exit') ?? false,
            dashVisible: Boolean(controls?.dash?.visible),
            configuredDashVisible:
                SETTINGS?.get_boolean('stockgs-keep-dash') ?? true,
            dashHeight: Number(controls?.dash?.height ?? 0),
            overviewVisible: Boolean(Main.overview?.visible),
            overviewVisibleTarget: Boolean(Main.overview?.visibleTarget),
            overviewState: this._stateName(state),
            overviewStateValue: state,
            searchActive: Boolean(
                searchController?.searchActive ?? searchController?._searchActive),
            appGridActive: state > 1,
            hotkeyPreviewActive: Boolean(this._hotkeyPreviewCycleInfo),
            pendingTimeouts: this._timeouts.size,
            restorationPending: Boolean(
                this._overrides.length ||
                this._ownedKeybindings.size ||
                this._removedNativeKeybindings.size ||
                this._dashOwnedState
            ),
            restoreConflicts: this._restoreConflicts,
            lastConflict: this._lastConflict,
            entryCount: this._entryCount,
            exitCount: this._exitCount,
            stateChangeCount: this._stateChangeCount,
            allocationCount: this._allocationCount,
            lastState: this._lastState,
            actorsCreated: 0,
            orphanActors: 0,
        };
    }

    _connectOverviewState() {
        this._connect(Main.overview, 'showing', () => {
            this._entryCount++;
            this._lastState = 'showing';
        }, 'overview-state');
        this._connect(Main.overview, 'shown', () => {
            this._lastState = 'shown';
        }, 'overview-state');
        this._connect(Main.overview, 'hiding', () => {
            this._lastState = 'hiding';
        }, 'overview-state');
        this._connect(Main.overview, 'hidden', () => {
            this._exitCount++;
            this._lastState = 'hidden';
        }, 'overview-state');

        const adjustment =
            Main.overview._overview._controls._stateAdjustment;
        this._connect(adjustment, 'notify::value', () => {
            this._stateChangeCount++;
        }, 'overview-state');
    }

    _connectSettings() {
        this._connect(SETTINGS, 'changed::isolate-workspaces', () => {
            this._syncWorkspaceIsolation(true);
        }, 'settings');
        this._connect(SETTINGS, 'changed::hot-keys', () => {
            this._syncHotkeys();
            this._syncNumberOverlay();
        }, 'settings');
        this._connect(SETTINGS, 'changed::hotkeys-overlay-combo', () => {
            this._syncNumberOverlay();
        }, 'settings');
        this._connect(SETTINGS, 'changed::shortcut-overlay-on-secondary', () => {
            this._syncNumberOverlay();
        }, 'settings');
        this._connect(SETTINGS, 'changed::shortcut-num-keys', () => {
            if (this._hotKeysEnabled) {
                this._disableHotKeys();
                this._enableHotKeys();
            }
        }, 'settings');
        this._connect(SETTINGS, 'changed::overview-click-to-exit', () => {
            this._syncClickToExit();
        }, 'settings');
        this._connect(SETTINGS, 'changed::stockgs-keep-dash', () => {
            this._toggleDash();
        }, 'settings');
        this._connect(SETTINGS, 'changed::panel-sizes', () => {
            this._toggleDash();
        }, 'settings');
    }

    _toggleDash(visible = undefined) {
        const controls = Main.overview._overview._controls;
        const dash = controls.dash;
        if (!this._dash) {
            this._dash = dash;
            this._dashOwnedState = {
                visible: Boolean(dash.visible),
            };
        }
        if (dash !== this._dash) {
            this._recordConflict('Overview dash changed while owned');
            return;
        }

        const shouldShow = visible ?? SETTINGS.get_boolean('stockgs-keep-dash');
        if (shouldShow)
            dash.show();
        else
            dash.hide();
        dash.set_height(shouldShow ? -1 : LABEL_MARGIN * Utils.getScaleFactor());
    }

    _restoreDash() {
        if (!this._dashOwnedState)
            return;

        const dash = Main.overview?._overview?._controls?.dash;
        if (dash !== this._dash) {
            this._recordConflict('Overview dash replacement prevented restoration');
        } else {
            if (this._dashOwnedState.visible)
                dash.show();
            else
                dash.hide();
            dash.set_height(-1);
        }

        this._dash = null;
        this._dashOwnedState = null;
    }

    _installAllocationHook() {
        const controls = Main.overview._overview._controls;
        const integration = this;
        this._overrideMethod(
            Object.getPrototypeOf(controls),
            'vfunc_allocate',
            originalAllocate => function (box) {
                integration._allocationCount++;
                const focusedPanel =
                    integration._panel?.panelManager?.focusedMonitorPanel;
                if (focusedPanel) {
                    const position = focusedPanel.geom.position;
                    const isBottom = position === St.Side.BOTTOM;

                    if (focusedPanel.intellihide?.enabled) {
                        const {transitioning, finalState, progress} =
                            this._stateAdjustment.getStateTransitionParams();
                        const size = focusedPanel.geom[
                            focusedPanel.geom.vertical ? 'w' : 'h'
                        ] * (transitioning
                            ? Math.abs((finalState !== 0 ? 0 : 1) - progress)
                            : 1);
                        if (isBottom || position === St.Side.RIGHT)
                            box[focusedPanel.fixedCoord.c2] -= size;
                        else
                            box[focusedPanel.fixedCoord.c1] += size;
                    } else if (isBottom) {
                        box.y2 -= focusedPanel.geom.outerSize;
                    }
                }
                return originalAllocate.call(this, box);
            },
            'overview-allocation',
        );
    }

    _syncWorkspaceIsolation(resetIcons) {
        if (resetIcons) {
            for (const panel of this._panelManager.allPanels)
                panel.taskbar.resetAppIcons();
        }

        if (SETTINGS.get_boolean('isolate-workspaces'))
            this._enableWorkspaceIsolation();
        else
            this._disableWorkspaceIsolation();
    }

    _enableWorkspaceIsolation() {
        if (this._overrides.some(record =>
            record.label === 'workspace-isolation'))
            return;

        this._overrideMethod(
            Shell.App.prototype,
            'activate',
            () => function () {
                const activeWorkspace =
                    Utils.DisplayWrapper.getWorkspaceManager()
                        .get_active_workspace();
                const windows = this.get_windows().filter(window =>
                    window.get_workspace().index() === activeWorkspace.index());
                if (windows.length > 0 &&
                    (!(windows.length === 1 && windows[0].skip_taskbar) ||
                     this.is_on_workspace(activeWorkspace))) {
                    return Main.activateWindow(windows[0]);
                }
                return this.open_new_window(-1);
            },
            'workspace-isolation',
        );
        this._connect(
            global.window_manager,
            'switch-workspace',
            () => {
                for (const panel of this._panelManager.allPanels)
                    panel.taskbar.handleIsolatedWorkspaceSwitch();
            },
            'workspace-isolation',
        );
    }

    _disableWorkspaceIsolation() {
        this._disconnectLabel('workspace-isolation');
        this._restoreOverrides('workspace-isolation');
    }

    _syncHotkeys() {
        if (SETTINGS.get_boolean('hot-keys')) {
            this._enableHotKeys();
            this._enableExtraShortcut();
        } else {
            this._disableExtraShortcut();
            this._disableHotKeys();
        }
    }

    _enableHotKeys() {
        if (this._hotKeysEnabled)
            return;

        const shortcutNumKeys = SETTINGS.get_string('shortcut-num-keys');
        const bothNumKeys = shortcutNumKeys === 'BOTH';
        const numRowKeys = shortcutNumKeys === 'NUM_ROW';
        const keys = [];
        let modifiers = Clutter.ModifierType.SUPER_MASK;

        if (Main.wm._switchToApplication) {
            for (let i = 1; i < 10; i++) {
                this._suppressNativeKeybinding(`${GS_SWITCH_HOTKEYS_KEY}${i}`);
                if (bothNumKeys || numRowKeys) {
                    this._suppressNativeKeybinding(
                        `${GS_OPEN_HOTKEYS_KEY}${i}`);
                }
            }
        }

        if (SETTINGS.get_string('hotkey-prefix-text') === 'SuperAlt')
            modifiers |= Clutter.ModifierType.MOD1_MASK;
        if (bothNumKeys || numRowKeys) {
            keys.push('app-hotkey-', 'app-shift-hotkey-', 'app-ctrl-hotkey-');
        }
        if (bothNumKeys || shortcutNumKeys === 'NUM_KEYPAD') {
            keys.push(
                'app-hotkey-kp-',
                'app-shift-hotkey-kp-',
                'app-ctrl-hotkey-kp-',
            );
        }

        for (const key of keys) {
            let bindingModifiers = modifiers;
            if (key.includes('-shift-'))
                bindingModifiers |= Clutter.ModifierType.SHIFT_MASK;
            if (key.includes('-ctrl-'))
                bindingModifiers |= Clutter.ModifierType.CONTROL_MASK;
            for (let i = 0; i < 10; i++) {
                this._addOwnedKeybinding(
                    `${key}${i + 1}`,
                    SETTINGS,
                    () => this._activateApp(i, bindingModifiers),
                );
            }
        }

        this._hotKeysEnabled = true;
        if (SETTINGS.get_string('hotkeys-overlay-combo') === 'ALWAYS')
            this._toggleHotkeysNumberOverlay(true);
    }

    _disableHotKeys() {
        const ownedAppKeys = [...this._ownedKeybindings].filter(key =>
            key.startsWith('app-'));
        if (!this._hotKeysEnabled &&
            !this._removedNativeKeybindings.size &&
            !ownedAppKeys.length)
            return;

        for (const key of ownedAppKeys)
            this._removeOwnedKeybinding(key);
        this._restoreNativeKeybindings();
        this._hotKeysEnabled = false;
        this._toggleHotkeysNumberOverlay(false);
    }

    _enableExtraShortcut() {
        if (this._extraShortcutOwned)
            return;
        this._addOwnedKeybinding(
            'shortcut', SETTINGS, () => this._showOverlay(true));
        this._extraShortcutOwned = this._ownedKeybindings.has('shortcut');
    }

    _disableExtraShortcut() {
        if (this._extraShortcutOwned)
            this._removeOwnedKeybinding('shortcut');
        this._extraShortcutOwned = false;
    }

    _activateApp(appIndex, modifiers) {
        const seenApps = new Map();
        const apps = [];
        for (const appIcon of this.taskbar._getAppIcons()) {
            if (!seenApps.has(appIcon.app) || this.taskbar.allowSplitApps)
                apps.push(appIcon);
            seenApps.set(appIcon.app, (seenApps.get(appIcon.app) ?? 0) + 1);
        }

        this._showOverlay();
        if (appIndex >= apps.length)
            return;

        const appIcon = apps[appIndex];
        const seenAppCount = seenApps.get(appIcon.app);
        const windowCount = appIcon.window || appIcon._hotkeysCycle
            ? seenAppCount
            : appIcon._nWindows;
        const previewModifiers = Clutter.ModifierType.MOD1_MASK |
            Clutter.ModifierType.SUPER_MASK;

        if (SETTINGS.get_boolean('shortcut-previews') &&
            windowCount > 1 && !(modifiers & ~previewModifiers)) {
            if (this._hotkeyPreviewCycleInfo?.appIcon !== appIcon)
                this._endHotkeyPreviewCycle();
            if (!this._hotkeyPreviewCycleInfo)
                this._beginHotkeyPreviewCycle(appIcon);
            appIcon._previewMenu.focusNext();
            return;
        }

        this._endHotkeyPreviewCycle();
        appIcon.activate(1, modifiers, !this.taskbar.allowSplitApps);
    }

    _beginHotkeyPreviewCycle(appIcon) {
        this._hotkeyPreviewCycleInfo = {
            appIcon,
            currentWindow: appIcon.window,
        };
        this._connect(appIcon, 'key-focus-out', () => {
            appIcon.grab_key_focus();
        }, 'hotkey-preview');
        this._connect(global.stage, 'captured-event', (_actor, event) => {
            const symbol = event.get_key_symbol();
            if (event.type() === Clutter.EventType.KEY_RELEASE &&
                (symbol === Clutter.KEY_Super_L ||
                 symbol === Clutter.KEY_Super_R)) {
                this._endHotkeyPreviewCycle(true);
            }
            return Clutter.EVENT_PROPAGATE;
        }, 'hotkey-preview');

        appIcon._hotkeysCycle = appIcon.window;
        appIcon.window = null;
        appIcon._previewMenu.open(appIcon, true);
        appIcon.grab_key_focus();
    }

    _endHotkeyPreviewCycle(focusWindow = false) {
        const info = this._hotkeyPreviewCycleInfo;
        if (!info)
            return;

        this._disconnectLabel('hotkey-preview');
        try {
            if (focusWindow)
                info.appIcon._previewMenu.activateFocused();
            else
                info.appIcon._previewMenu.close();
            info.appIcon.window = info.currentWindow;
            delete info.appIcon._hotkeysCycle;
        } catch (error) {
            console.debug(
                `[layout-switcher-runtime] hotkey preview cleanup: ${error}`,
            );
        }
        this._hotkeyPreviewCycleInfo = null;
    }

    _syncNumberOverlay() {
        if (SETTINGS.get_boolean('hot-keys') &&
            SETTINGS.get_string('hotkeys-overlay-combo') === 'ALWAYS') {
            this._toggleHotkeysNumberOverlay(true);
        } else {
            this._toggleHotkeysNumberOverlay(false, true);
        }
    }

    _showOverlay(overlayFromShortcut = false) {
        if (!this._panel?.intellihide)
            return;

        const option = SETTINGS.get_string('hotkeys-overlay-combo');
        const temporarily = option === 'TEMPORARILY';
        const timeout = SETTINGS.get_int(
            overlayFromShortcut ? 'shortcut-timeout' : 'overlay-timeout');
        if (option === 'NEVER' || (!timeout && temporarily))
            return;

        if (temporarily || overlayFromShortcut)
            this._toggleHotkeysNumberOverlay(true);
        this._panel.intellihide.revealAndHold(Intellihide.Hold.TEMPORARY);
        this._setTimeout(NUMBER_OVERLAY_TIMEOUT, timeout, () => {
            if (option !== 'ALWAYS')
                this._toggleHotkeysNumberOverlay(false);
            this._panel?.intellihide?.release(Intellihide.Hold.TEMPORARY);
        });
    }

    _toggleHotkeysNumberOverlay(show, reset = false) {
        this.taskbar?.toggleHotkeysNumberOverlay(show);
        if (reset || SETTINGS?.get_boolean('shortcut-overlay-on-secondary')) {
            for (const panel of this._panelManager.allPanels) {
                if (!panel.isPrimary)
                    panel.taskbar.toggleHotkeysNumberOverlay(show);
            }
        }
    }

    _syncClickToExit() {
        if (SETTINGS.get_boolean('overview-click-to-exit'))
            this._enableClickToExit();
        else
            this._disableClickToExit();
    }

    _enableClickToExit() {
        if (this._clickToExitOwned)
            return;
        this._connect(
            Main.layoutManager.overviewGroup,
            'button-release-event',
            () => {
                const [x, y] = global.get_pointer();
                const pickedActor = global.stage.get_actor_at_pos(
                    Clutter.PickMode.REACTIVE, x, y);
                const searchEntry =
                    Main.overview._overview._controls._searchEntryBin;
                if (pickedActor &&
                    ((pickedActor.has_style_class_name?.('apps-scroll-view') &&
                      !pickedActor.has_style_pseudo_class('first-child')) ||
                     searchEntry.contains(pickedActor) ||
                     pickedActor instanceof WindowPreview)) {
                    return Clutter.EVENT_PROPAGATE;
                }
                Main.overview.toggle();
                return Clutter.EVENT_PROPAGATE;
            },
            'click-to-exit',
        );
        this._clickToExitOwned = true;
    }

    _disableClickToExit() {
        this._disconnectLabel('click-to-exit');
        this._clickToExitOwned = false;
    }

    _addOwnedKeybinding(key, settings, handler) {
        if (this._keybindingActive(key)) {
            this._recordConflict(`Keybinding already owned: ${key}`);
            return;
        }
        Utils.addKeybinding(key, settings, handler);
        if (!this._keybindingActive(key))
            throw new Error(`Failed to own keybinding: ${key}`);
        this._ownedKeybindings.add(key);
    }

    _removeOwnedKeybinding(key) {
        if (!this._ownedKeybindings.has(key))
            return;
        if (!this._keybindingActive(key)) {
            this._recordConflict(`Owned keybinding disappeared: ${key}`);
        } else {
            Utils.removeKeybinding(key);
        }
        this._ownedKeybindings.delete(key);
    }

    _suppressNativeKeybinding(key) {
        if (!this._keybindingActive(key))
            return;
        Utils.removeKeybinding(key);
        if (this._keybindingActive(key))
            throw new Error(`Failed to suppress native keybinding: ${key}`);
        this._removedNativeKeybindings.add(key);
    }

    _restoreNativeKeybindings() {
        if (!this._removedNativeKeybindings.size)
            return;
        const settings = new Gio.Settings({
            schema_id: WindowManager.SHELL_KEYBINDINGS_SCHEMA,
        });
        for (const key of this._removedNativeKeybindings) {
            if (this._keybindingActive(key)) {
                this._recordConflict(`Native keybinding changed: ${key}`);
                continue;
            }
            const handler = key.startsWith(GS_OPEN_HOTKEYS_KEY)
                ? Main.wm._openNewApplicationWindow.bind(Main.wm)
                : Main.wm._switchToApplication.bind(Main.wm);
            Utils.addKeybinding(key, settings, handler);
            if (!this._keybindingActive(key))
                this._recordConflict(`Native keybinding restore failed: ${key}`);
        }
        this._removedNativeKeybindings.clear();
    }

    _keybindingActive(key) {
        return Boolean(Main.wm._allowedKeybindings?.[key]);
    }

    _connect(object, signal, callback, label) {
        const id = object.connect(signal, callback);
        this._signals.push({object, id, label});
        return id;
    }

    _disconnectLabel(label) {
        for (let i = this._signals.length - 1; i >= 0; i--) {
            const record = this._signals[i];
            if (record.label !== label)
                continue;
            try {
                record.object.disconnect(record.id);
            } catch (error) {
                this._recordConflict(`Signal changed before cleanup: ${label}`);
            }
            this._signals.splice(i, 1);
        }
    }

    _disconnectAll() {
        for (let i = this._signals.length - 1; i >= 0; i--) {
            const record = this._signals[i];
            try {
                record.object.disconnect(record.id);
            } catch (error) {
                this._recordConflict(
                    `Signal changed before cleanup: ${record.label}`);
            }
        }
        this._signals = [];
    }

    _overrideMethod(object, key, createOverride, label) {
        const original = Object.getOwnPropertyDescriptor(object, key);
        const originalMethod = object[key];
        if (typeof originalMethod !== 'function')
            throw new Error(`Overview hook is unavailable: ${key}`);
        const installed = {
            configurable: original?.configurable ?? true,
            enumerable: original?.enumerable ?? false,
            writable: original?.writable ?? true,
            value: createOverride(originalMethod),
        };
        Object.defineProperty(object, key, installed);
        this._overrides.push({object, key, label, original, installed});
    }

    _restoreOverrides(label = null) {
        for (let i = this._overrides.length - 1; i >= 0; i--) {
            const record = this._overrides[i];
            if (label && record.label !== label)
                continue;
            const current = Object.getOwnPropertyDescriptor(
                record.object, record.key);
            if (this._descriptorsMatch(current, record.installed)) {
                if (record.original)
                    Object.defineProperty(
                        record.object, record.key, record.original);
                else
                    delete record.object[record.key];
            } else {
                this._recordConflict(
                    `Overview hook changed externally: ${record.label}`);
            }
            this._overrides.splice(i, 1);
        }
    }

    _descriptorsMatch(left, right) {
        if (!left || !right)
            return left === right;
        return left.configurable === right.configurable &&
            left.enumerable === right.enumerable &&
            left.writable === right.writable &&
            left.value === right.value &&
            left.get === right.get &&
            left.set === right.set;
    }

    _setTimeout(name, delay, callback) {
        this._removeTimeout(name);
        const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, delay, () => {
            this._timeouts.delete(name);
            callback();
            return GLib.SOURCE_REMOVE;
        });
        this._timeouts.set(name, id);
    }

    _removeTimeout(name) {
        const id = this._timeouts.get(name);
        if (!id)
            return;
        GLib.Source.remove(id);
        this._timeouts.delete(name);
    }

    _clearTimeouts() {
        for (const name of [...this._timeouts.keys()])
            this._removeTimeout(name);
    }

    _recordConflict(message) {
        this._restoreConflicts++;
        this._lastConflict = message;
    }

    _stateName(value) {
        if (value <= 0)
            return 'hidden';
        if (value < 1)
            return 'entering';
        if (value === 1)
            return 'window-picker';
        if (value < 2)
            return 'transitioning';
        return 'app-grid';
    }
}
