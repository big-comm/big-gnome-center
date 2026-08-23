// SPDX-License-Identifier: GPL-2.0-or-later

import Shell from 'gi://Shell';

import * as AppFavorites from 'resource:///org/gnome/shell/ui/appFavorites.js';

export class DockAppModel {
    favorites() {
        return AppFavorites.getAppFavorites().getFavoriteMap();
    }

    running() {
        return [...Shell.AppSystem.get_default().get_running()];
    }

    order(oldApps, favorites, running, showFavorites, showRunning) {
        const apps = [];
        const pending = [...running];

        if (showFavorites)
            apps.push(...Object.values(favorites));

        if (!showRunning)
            return apps;

        for (const oldApp of oldApps) {
            const index = pending.indexOf(oldApp);
            if (index < 0)
                continue;

            const [app] = pending.splice(index, 1);
            if (!showFavorites || !(app.get_id() in favorites))
                apps.push(app);
        }

        for (const app of pending) {
            if (!showFavorites || !(app.get_id() in favorites))
                apps.push(app);
        }

        return apps;
    }
}
