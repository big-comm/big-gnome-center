// SPDX-License-Identifier: GPL-2.0-or-later

import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as SystemActions from 'resource:///org/gnome/shell/misc/systemActions.js';
import * as Util from 'resource:///org/gnome/shell/misc/util.js';

import * as BaseLayout from './baseLayout.js';
import * as Constants from '../constants.js';
import * as SearchEntry from '../widgets/searchEntry.js';
import * as Sections from '../sections.js';
import * as SessionButtons from '../widgets/sessionButtons.js';
import * as UserWidgets from '../widgets/userWidgets.js';
import * as Utils from '../utils.js';
import * as Widgets from '../widgets/widgets.js';
import {getOrientationProp} from '../utils.js';

export const HybridLayout = GObject.registerClass({
}, class CommunityBigHybridLayout extends BaseLayout.BaseLayout {
    _init(appsBackend, panelInfo) {
        super._init(appsBackend, panelInfo);
        this.add_style_class_name('main-box');
        this.add_style_class_name('hybrid-layout-box');
    }

    _loadLayout() {
        this._systemActions = SystemActions.getDefault();
        this._systemActions.forceUpdate();

        this._categoriesSection = new Sections.HybridCategoriesSection(this._appsBackend);
        this._appsSection = new Sections.AppsListSection(
            this._appsBackend,
            true,
            this._monitorIndex,
            'frequent_apps',
            Constants.APP_GRID_ICON_SIZE,
            false,
            Constants.HYBRID_COLUMN_COUNT);
        this._searchResults = this._appsSection.searchResults;
        this._searchEntry = new SearchEntry.SearchEntry(this._searchResults);
        this._userButton = new UserWidgets.UserMenuItem();
        this._userButton.x_expand = false;

        this._headerBox = new St.BoxLayout({
            ...getOrientationProp(false),
            x_expand: true,
            style_class: 'hybrid-header-box',
        });
        this._headerBox.add_child(this._userButton);
        this._headerBox.add_child(this._searchEntry);

        this._sessionActions = [
            new SessionButtons.LogoutButton(this._systemActions),
            new SessionButtons.LockButton(this._systemActions),
            new SessionButtons.RestartButton(this._systemActions),
            new SessionButtons.PowerButton(this._systemActions),
        ];
        this._sessionActionsBox = new St.BoxLayout({
            ...getOrientationProp(false),
            style_class: 'hybrid-session-actions',
        });
        for (const button of this._sessionActions)
            this._sessionActionsBox.add_child(button);

        this._leftBox = new St.BoxLayout({
            ...getOrientationProp(true),
            y_expand: true,
            style_class: 'hybrid-left-box',
        });
        this._leftBox.add_child(this._categoriesSection);
        this._leftBox.add_child(this._sessionActionsBox);

        this._verticalSeparator = new Widgets.VerticalSeparator();
        this._contentBox = new St.BoxLayout({
            ...getOrientationProp(false),
            x_expand: true,
            y_expand: true,
            style_class: 'hybrid-content-box',
        });
        this._contentBox.add_child(this._leftBox);
        this._contentBox.add_child(this._verticalSeparator.actor);
        this._contentBox.add_child(this._appsSection);

        this._box = new St.BoxLayout({
            ...getOrientationProp(true),
            x_expand: true,
            y_expand: true,
            style_class: 'hybrid-box',
        });
        this._box.add_child(this._headerBox);
        this._box.add_child(this._contentBox);
        this.add_child(this._box);
    }

    _connectSignals() {
        this._categoriesSection.connectObject('selected', this._onSelectCategory.bind(this), this);
        this._appsSection.connectObject('activated', this._activated.bind(this), this);
        this._searchEntry.connectObject('notify::search-active', this._onSearchChanged.bind(this), this);
        this._searchEntry.connectObject('entry-key-press', this._onSearchEntryKeyPress.bind(this), this);
        this._searchResults.connectObject('screenshot-activated', this._onScreenshotActivated.bind(this), this);
        this._userButton.connectObject('activated', this._activated.bind(this), this);
        for (const button of this._sessionActions)
            button.connectObject('activated', this._activated.bind(this), this);
    }

    _onSelectCategory(actor, categoryMenuId) {
        if (categoryMenuId === 'recent_files') {
            Util.spawn(['gio', 'open', 'recent:///']);
            this._activated();
            return;
        }
        this._appsSection.selectCategory(categoryMenuId);
    }

    _onSearchChanged() {
        Utils.blockHover();
        if (this._searchEntry.searchActive) {
            this._appsSection.searchActive();
            this._searchEntry.grab_key_focus();
        } else {
            this._appsSection.selectCategory('frequent_apps');
            this._appsSection.grab_key_focus();
        }
    }

    reset() {
        this._searchEntry.clear();
        this._onSearchChanged();
    }

    updateHeight() {
        const scaleFactor = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const availableHeight = this._availableHeight();
        const naturalHeight = Constants.HYBRID_MENU_HEIGHT * scaleFactor;
        this.set_height(Math.min(naturalHeight, availableHeight));
    }

    _onDestroy() {
        this._systemActions = null;

        this._searchEntry?.destroy();
        this._searchEntry = null;
        this._searchResults = null;

        this._userButton?.destroy();
        this._userButton = null;

        this._categoriesSection?.destroy();
        this._categoriesSection = null;

        this._appsSection?.destroy();
        this._appsSection = null;

        for (const button of this._sessionActions ?? [])
            button?.destroy();
        this._sessionActions = null;

        this._sessionActionsBox?.destroy();
        this._sessionActionsBox = null;
        this._leftBox?.destroy();
        this._leftBox = null;
        this._verticalSeparator?.destroy();
        this._verticalSeparator = null;
        this._contentBox?.destroy();
        this._contentBox = null;
        this._headerBox?.destroy();
        this._headerBox = null;
        this._box?.destroy();
        this._box = null;

        super._onDestroy();
    }
});
