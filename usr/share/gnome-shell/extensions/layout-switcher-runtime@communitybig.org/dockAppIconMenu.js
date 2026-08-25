// SPDX-License-Identifier: GPL-2.0-or-later

import {
    Gio,
    GLib,
    Shell,
    St,
} from './dock/dependencies/gi.js';

import {
    AppFavorites,
    BoxPointer,
    Main,
    PopupMenu,
} from './dock/dependencies/shell/ui.js';

import {
    ParentalControlsManager,
    Util,
} from './dock/dependencies/shell/misc.js';

import {Extension} from './dock/dependencies/shell/extensions/extension.js';
import * as DBusMenuUtils from './dock/dbusmenuUtils.js';
import * as Docking from './dockSurface.js';
import * as Utils from './dock/utils.js';
import * as WindowPreview from './dock/windowPreview.js';

const {gettext: __, ngettext} = Extension;
const DBusMenu = await DBusMenuUtils.haveDBusMenu();

export const DockAppIconMenu = class DockAppIconMenu extends PopupMenu.PopupMenu {
    constructor(source, isApplicationIcon = false) {
        super(source, 0.5, Utils.getPosition());

        this._isApplicationIcon = isApplicationIcon;

        this._signalsHandler = new Utils.GlobalSignalsHandler(this);

        // We want to keep the item hovered while the menu is up
        this.blockSourceEvents = true;

        this.actor.add_style_class_name('app-menu');
        this.actor.add_style_class_name('dock-app-menu');

        // Chain our visibility and lifecycle to that of the source
        this._signalsHandler.add(source, 'notify::mapped', () => {
            if (!source.mapped)
                this.close();
        });
        this._signalsHandler.add(source, 'destroy', () => this.destroy());

        Main.uiGroup.add_child(this.actor);

        const {remoteModel} = Docking.DockSurfaceManager.getDefault();
        const remoteModelApp = remoteModel?.lookupById(this.sourceActor?.app?.id);
        if (remoteModelApp && DBusMenu) {
            const [onQuickList, onDynamicSection] = Utils.splitHandler((sender,
                {quicklist}, dynamicSection) => {
                dynamicSection.removeAll();
                if (quicklist) {
                    quicklist.get_children().forEach(remoteItem =>
                        dynamicSection.addMenuItem(
                            DBusMenuUtils.makePopupMenuItem(remoteItem, false)));
                }
            });

            this._signalsHandler.add([
                remoteModelApp,
                'quicklist-changed',
                onQuickList,
            ], [
                this,
                'dynamic-section-changed',
                onDynamicSection,
            ]);
        }
    }

    destroy() {
        super.destroy();
        delete this.sourceActor;
        delete this._signalsHandler;
        delete this._isApplicationIcon;
    }

    _appendSeparator() {
        this.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
    }

    _appendMenuItem(labelText, params) {
        const item = new PopupMenu.PopupMenuItem(labelText, params);
        this.addMenuItem(item);
        return item;
    }

    popup(_activatingButton) {
        this._rebuildMenu();
        this.open(BoxPointer.PopupAnimation.FULL);
    }

    removeAll() {
        super.removeAll();

        delete this._allWindowsMenuItem;
        delete this._quitMenuItem;
    }

    _rebuildMenu() {
        this.removeAll();

        const appItemLabel = this.sourceActor.updating
            ? _('%s is being updated…').format(this.sourceActor.name)
            : this.sourceActor.name;
        this.addMenuItem(new PopupMenu.PopupSeparatorMenuItem(appItemLabel));

        const {app} = this.sourceActor;

        if (Docking.DockSurfaceManager.settings.showWindowsPreview) {
            // Display the app windows menu items and the separator between windows
            // of the current desktop and other windows.
            const windows = this.sourceActor.getInterestingWindows();

            this._allWindowsMenuItem = new PopupMenu.PopupSubMenuMenuItem(__('All Windows'), false);
            if (this._allWindowsMenuItem.menu?.actor)
                this._allWindowsMenuItem.menu.actor.overlayScrollbars = true;
            this._allWindowsMenuItem.hide();
            if (windows.length > 0)
                this.addMenuItem(this._allWindowsMenuItem);
        } else {
            const windows = this.sourceActor.getInterestingWindows();

            if (windows.length > 0) {
                this.addMenuItem(
                    /* Translators: This is the heading of a list of open windows */
                    new PopupMenu.PopupSeparatorMenuItem(_('Open Windows')));
            }

            windows.forEach(window => {
                const title = window.title ? window.title : app.get_name();
                const item = this._appendMenuItem(title);
                item.connect('activate', () => {
                    this.emit('activate-window', window);
                });
            });
        }

        if (!app.is_window_backed()) {
            this._appendSeparator();

            const appInfo = app.get_app_info();
            const actions = this.sourceActor.updating ? [] : appInfo.list_actions();
            if (!this.sourceActor.updating &&
                app.can_open_new_window() &&
                actions.indexOf('new-window') === -1) {
                const newMenuItem = this._appendMenuItem(_('New Window'));
                newMenuItem.connect('activate', () => {
                    if (!Docking.DockSurfaceManager.extension.appMenuActions
                        ?.openNewWindow(this.sourceActor)) {
                        if (app.state === Shell.AppState.STOPPED)
                            this.sourceActor.animateLaunch();
                        app.open_new_window(-1);
                    }
                    this.emit('activate-window', null);
                });
                this._appendSeparator();
            }

            if (!this.sourceActor.updating &&
                Docking.DockSurfaceManager.getDefault().discreteGpuAvailable &&
                app.state === Shell.AppState.STOPPED) {
                const appPrefersNonDefaultGPU = appInfo.get_boolean('PrefersNonDefaultGPU');
                const gpuPref = appPrefersNonDefaultGPU
                    ? Shell.AppLaunchGpu.DEFAULT
                    : Shell.AppLaunchGpu.DISCRETE;
                const gpuMenuItem = this._appendMenuItem(appPrefersNonDefaultGPU
                    ? _('Launch using Integrated Graphics Card')
                    : _('Launch using Discrete Graphics Card'));
                gpuMenuItem.connect('activate', () => {
                    if (!Docking.DockSurfaceManager.extension.appMenuActions
                        ?.launchOnGpu(this.sourceActor, gpuPref)) {
                        this.sourceActor.animateLaunch();
                        app.launch(0, -1, gpuPref);
                    }
                    this.emit('activate-window', null);
                });
            }

            for (let i = 0; i < actions.length; i++) {
                const action = actions[i];
                const item = this._appendMenuItem(appInfo.get_action_name(action));
                item.sensitive = !appInfo.busy;
                item.connect('activate', (emitter, event) => {
                    if (!Docking.DockSurfaceManager.extension.appMenuActions
                        ?.launchDesktopAction(this.sourceActor, action, event.get_time()))
                        app.launch_action(action, event.get_time(), -1);
                    this.emit('activate-window', null);
                });
            }

            const canFavorite = global.settings.is_writable('favorite-apps') &&
                (this._isApplicationIcon) &&
                ParentalControlsManager.getDefault().shouldShowApp(app.appInfo);

            if (canFavorite) {
                this._appendSeparator();

                const isFavorite = AppFavorites.getAppFavorites().isFavorite(app.get_id());
                if (isFavorite) {
                    const item = this._appendMenuItem(_('Unpin'));
                    item.connect('activate', () => {
                        if (!Docking.DockSurfaceManager.extension.appMenuActions
                            ?.setFavorite(app.get_id(), false)) {
                            const favs = AppFavorites.getAppFavorites();
                            favs.removeFavorite(app.get_id());
                        }
                    });
                } else {
                    const item = this._appendMenuItem(__('Pin to Dock'));
                    item.connect('activate', () => {
                        if (!Docking.DockSurfaceManager.extension.appMenuActions
                            ?.setFavorite(app.get_id(), true)) {
                            const favs = AppFavorites.getAppFavorites();
                            favs.addFavorite(app.get_id());
                        }
                    });
                }
            }

            if (Shell.AppSystem.get_default().lookup_app('org.gnome.Software.desktop') &&
                this._isApplicationIcon &&
                !this.sourceActor.getSnapName()) {
                this._appendSeparator();
                const item = this._appendMenuItem(_('App Details'));
                item.connect('activate', () => {
                    const id = app.get_id();
                    const args = GLib.Variant.new('(ss)', [id, '']);
                    Gio.DBus.get(Gio.BusType.SESSION, null,
                        (o, res) => {
                            const bus = Gio.DBus.get_finish(res);
                            bus.call('org.gnome.Software',
                                '/org/gnome/Software',
                                'org.gtk.Actions', 'Activate',
                                GLib.Variant.new('(sava{sv})',
                                    ['details', [args], null]),
                                null, 0, -1, null, null);
                            Main.overview.hide();
                        });
                });
            }

            if (this._isApplicationIcon) {
                const snapName = this.sourceActor.getSnapName();
                const snapStore = snapName
                    ? Shell.AppSystem.get_default().lookup_app(
                        'snap-store_snap-store.desktop') : null;

                if (snapStore) {
                    this._appendSeparator();
                    const item = this._appendMenuItem(_('App Details'));
                    item.connect('activate', (_, event) => {
                        snapStore.activate_full(-1, event.get_time());
                        Util.spawnApp(
                            [...snapStore.appInfo.get_commandline().split(' '), snapName]);
                        Main.overview.hide();
                    });
                }
            }
        }

        // dynamic menu
        const items = this._getMenuItems();
        let i = items.length;
        if (Shell.AppSystem.get_default().lookup_app('org.gnome.Software.desktop'))
            i -= 2;

        if (global.settings.is_writable('favorite-apps'))
            i -= 2;

        if (i < 0)
            i = 0;

        const dynamicSection = new PopupMenu.PopupMenuSection();
        this.addMenuItem(dynamicSection, i);
        this.emit('dynamic-section-changed', dynamicSection);

        // quit menu
        this._appendSeparator();
        this._quitMenuItem = this._appendMenuItem(_('Quit'));
        this._quitMenuItem.connect('activate', () => {
            if (!Docking.DockSurfaceManager.extension.appMenuActions?.quit(this.sourceActor))
                this.sourceActor.closeAllWindows();
        });

        this.update();
    }

    // update menu content when application windows change. This is desirable as actions
    // acting on windows (closing) are performed while the menu is shown.
    update() {
        // update, show or hide the quit menu
        if (this.sourceActor.windowsCount > 0) {
            if (this.sourceActor.windowsCount === 1) {
                this._quitMenuItem.label.set_text(_('Quit'));
            } else {
                this._quitMenuItem.label.set_text(ngettext(
                    'Quit %d Window', 'Quit %d Windows', this.sourceActor.windowsCount).format(
                    this.sourceActor.windowsCount));
            }

            this._quitMenuItem.actor.show();
        } else {
            this._quitMenuItem.actor.hide();
        }

        if (Docking.DockSurfaceManager.settings.showWindowsPreview) {
            const windows = this.sourceActor.getInterestingWindows();

            // update, show, or hide the allWindows menu
            // Check if there are new windows not already displayed. In such case,
            // repopulate the allWindows menu. Windows removal is already handled
            // by each preview being connected to the destroy signal
            const oldWindows = this._allWindowsMenuItem.menu._getMenuItems().map(item => {
                return item._window;
            });

            const newWindows = windows.filter(w =>
                oldWindows.indexOf(w) < 0);
            if (newWindows.length > 0) {
                this._populateAllWindowMenu(windows);

                // Try to set the width to that of the submenu.
                // TODO: can't get the actual size, getting a bit less.
                // Temporary workaround: add 15px to compensate
                this._allWindowsMenuItem.width =  this._allWindowsMenuItem.menu.actor.width + 15;
            }

            // The menu is created hidden and never hidden after being shown.
            // Instead, a signal connected to its items destroy will set is
            // insensitive if no more windows preview are shown.
            if (windows.length > 0) {
                this._allWindowsMenuItem.show();
                this._allWindowsMenuItem.setSensitive(true);

                if (Docking.DockSurfaceManager.settings.defaultWindowsPreviewToOpen)
                    this._allWindowsMenuItem.menu.open();
            }
        }

        // Update separators
        this._getMenuItems().forEach(item => {
            if ('label' in item)
                this._updateSeparatorVisibility(item);
        });
    }

    _populateAllWindowMenu(windows) {
        this._allWindowsMenuItem.menu.removeAll();

        if (windows.length > 0) {
            const activeWorkspace = global.workspace_manager.get_active_workspace();
            let separatorShown =  windows[0].get_workspace() !== activeWorkspace;

            for (let i = 0; i < windows.length; i++) {
                const window = windows[i];
                if (!separatorShown && window.get_workspace() !== activeWorkspace) {
                    this._allWindowsMenuItem.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
                    separatorShown = true;
                }

                const item = new WindowPreview.WindowPreviewMenuItem(window,
                    St.Side.LEFT);
                this._allWindowsMenuItem.menu.addMenuItem(item);
                item.connect('activate', () => {
                    this.emit('activate-window', window);
                });

                // This is to achieve a more graceful transition when the last
                // window is closed.
                item.connect('destroy', () => {
                    // It's still counting the item just going to be destroyed
                    if (this._allWindowsMenuItem.menu._getMenuItems().length === 1)
                        this._allWindowsMenuItem.setSensitive(false);
                });
            }
        }
    }
};

export class DockAppMenuFactory {
    create(source, isApplicationIcon = false) {
        return new DockAppIconMenu(source, isApplicationIcon);
    }
}
