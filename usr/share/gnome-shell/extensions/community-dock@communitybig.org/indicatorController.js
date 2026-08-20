// SPDX-License-Identifier: GPL-2.0-or-later
// BigCommunity running application indicator controller.

const SETTINGS_SCHEMA = 'org.communitybig.panel-and-dock';
const DOCK_SCHEMA = 'org.gnome.shell.extensions.dash-to-dock';
const STYLE_CLASSES = new Map([
    ['dot', 'community-indicator-dot'],
    ['hybrid', 'community-indicator-hybrid'],
    ['desk-ux', 'community-indicator-desk-ux'],
]);

export class IndicatorController {
    constructor(extension, dockManager) {
        this._settings = extension.getSettings(SETTINGS_SCHEMA);
        this._dockSettings = extension.getSettings(DOCK_SCHEMA);
        this._dockManager = dockManager;
        this._signals = [
            [this._settings, this._settings.connect(
                'changed::indicator-style', () => this._apply())],
            [this._dockSettings, this._dockSettings.connect(
                'changed::running-indicator-style', () => this._apply())],
            [this._dockManager, this._dockManager.connect(
                'docks-ready', () => this._apply())],
        ];
        this._apply();
    }

    destroy() {
        for (const dock of this._dockManager?._allDocks ?? [])
            this._clearClasses(dock);
        for (const [object, id] of this._signals.splice(0))
            object.disconnect(id);
        this._settings = null;
        this._dockSettings = null;
        this._dockManager = null;
    }

    _apply() {
        if (this._dockSettings.get_enum('running-indicator-style') !== 0) {
            this._dockSettings.set_enum('running-indicator-style', 0);
            return;
        }

        const configured = this._settings.get_string('indicator-style');
        const styleClass = STYLE_CLASSES.get(configured) ?? STYLE_CLASSES.get('dot');
        for (const dock of this._dockManager._allDocks) {
            this._clearClasses(dock);
            dock.add_style_class_name(styleClass);
        }
    }

    _clearClasses(dock) {
        for (const styleClass of STYLE_CLASSES.values())
            dock.remove_style_class_name(styleClass);
    }
}
