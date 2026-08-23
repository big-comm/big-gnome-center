// SPDX-License-Identifier: GPL-2.0-or-later

import Shell from 'gi://Shell';

import * as AppFavorites from 'resource:///org/gnome/shell/ui/appFavorites.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class DockAppMenuActions {
    activateWindow(window) {
        if (window) {
            Main.activateWindow(window);
        } else {
            Main.overview.hide();
            Main.panel.closeCalendar();
        }
        return true;
    }

    openNewWindow(icon) {
        if (icon.app.state === Shell.AppState.STOPPED)
            icon.animateLaunch();
        icon.app.open_new_window(-1);
        return true;
    }

    launchOnGpu(icon, gpuPreference) {
        icon.animateLaunch();
        icon.app.launch(0, -1, gpuPreference);
        return true;
    }

    launchDesktopAction(icon, action, time) {
        icon.app.launch_action(action, time, -1);
        return true;
    }

    setFavorite(appId, favorite) {
        const favorites = AppFavorites.getAppFavorites();
        if (favorite)
            favorites.addFavorite(appId);
        else
            favorites.removeFavorite(appId);
        return true;
    }

    quit(icon) {
        const time = global.get_current_time();
        for (const window of icon.getInterestingWindows())
            window.delete(time);
        return true;
    }
}
