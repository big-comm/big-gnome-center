// Modified by Community Big, 2026-07-10: renamed, de-Zorinized, and adapted for GNOME Shell 50.
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as Constants from '../constants.js';

const MENU_ICON_NAME = 'bigcommunity-menu-symbolic';

export const MenuButton = GObject.registerClass({
}, class CommunityBigMenuButton extends St.BoxLayout {
    _init() {
        super._init({
            style_class: 'panel-status-menu-box'
        });

        this._icon = new St.Icon({
            icon_size: Constants.MENU_BUTTON_ICON_SIZE,
            style_class: 'community-menu-button-icon'
        });
        this._setIcon();
        this.add_child(this._icon);

        this.connect('destroy', this._onDestroy.bind(this));
    }

    _setIcon() {
        this._icon.set_icon_name(MENU_ICON_NAME);
    }

    setIconSize(size) {
        this._icon.set_icon_size(size);
    }

    _onDestroy() {
        this._icon?.destroy();
        this._icon = null;
    }
});
