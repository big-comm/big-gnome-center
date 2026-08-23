// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const PRIMARY_BUTTON = 1;
const CLICK_MODIFIERS = Clutter.ModifierType.SHIFT_MASK |
    Clutter.ModifierType.CONTROL_MASK;

export class DockAppActions {
    activate(icon, button) {
        const event = Clutter.get_current_event();
        const modifiers = (event?.get_state() ?? 0) & CLICK_MODIFIERS;
        if (button !== PRIMARY_BUTTON || modifiers)
            return false;

        const windows = icon.getInterestingWindows();
        if (!icon.running) {
            this._launch(icon);
        } else if (Main.overview.visible) {
            icon.app.activate();
        } else if (windows.length === 1 || icon._urgentWindows?.size) {
            if (icon.focused)
                this._minimize(windows[0]);
            else
                Main.activateWindow(windows[0]);
        } else {
            icon._windowPreviews();
        }

        Main.overview.hide();
        return true;
    }

    _launch(icon) {
        const app = icon.app;
        if (app.state === Shell.AppState.RUNNING && app.can_open_new_window()) {
            icon.animateLaunch();
            app.open_new_window(-1);
            return;
        }

        const windows = icon.getWindows();
        if (windows.length) {
            Main.activateWindow(windows[0]);
            return;
        }

        app.activate();
        icon.animateLaunch();
    }

    _minimize(window) {
        const workspace = global.workspace_manager.get_active_workspace();
        if (window?.get_workspace() === workspace && window.showing_on_its_workspace())
            window.minimize();
    }
}
