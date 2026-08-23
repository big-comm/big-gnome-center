// SPDX-License-Identifier: GPL-2.0-or-later

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

import {RuntimeController} from './runtimeController.js';

export default class LayoutSwitcherRuntimeExtension extends Extension {
    enable() {
        this._controller = new RuntimeController(this);
        this._controller.enable();
    }

    disable() {
        this._controller?.disable();
        this._controller = null;
    }
}
