// SPDX-License-Identifier: GPL-2.0-or-later

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const CORE_ROLES = new Set([
    'a11y',
    'activities',
    'appMenu',
    'dateMenu',
    'dwellClick',
    'keyboard',
    'quickSettings',
    'screenRecording',
    'screenSharing',
]);

export class TaskbarStatusAreaHost {
    constructor() {
        this._generation = 0;
        this._owner = null;
        this._roles = new Map();
        this._toggleDescriptor = null;
        this._menuManager = null;
        this._quickSettingsArrow = null;
    }

    adopt(owner) {
        if (this._owner === owner)
            return;
        this.restore();

        const panel = Main.panel;
        this._owner = owner;
        this._menuManager = panel.menuManager;
        this._toggleDescriptor = Object.getOwnPropertyDescriptor(
            panel, '_toggleMenu');
        const quickSettingsMenu = panel.statusArea.quickSettings?.menu;
        if (quickSettingsMenu) {
            this._quickSettingsArrow = {
                side: quickSettingsMenu._arrowSide,
                alignment: quickSettingsMenu._arrowAlignment,
            };
        }

        for (const role of ['activities', 'quickSettings', 'dateMenu']) {
            const container = panel.statusArea[role]?.container;
            const parent = container?.get_parent?.();
            if (!container || !parent)
                continue;
            this._roles.set(role, {
                container,
                parent,
                index: parent.get_children().indexOf(container),
            });
            parent.remove_child(container);
            panel.add_child(container);
        }

        panel._toggleMenu = indicator => {
            if (!indicator ||
                (!owner.intellihide?.enabled && !indicator.mapped) ||
                !indicator.reactive)
                return;
            owner.intellihide?.revealAndHold(0, true);
            Object.getPrototypeOf(panel)._toggleMenu.call(panel, indicator);
        };
        this._generation++;
    }

    restore(owner = null) {
        if (!this._owner || (owner && owner !== this._owner))
            return;

        const panel = Main.panel;
        if (this._toggleDescriptor)
            Object.defineProperty(panel, '_toggleMenu', this._toggleDescriptor);
        else
            delete panel._toggleMenu;

        const records = [...this._roles.values()]
            .sort((a, b) => a.index - b.index);
        for (const {container, parent, index} of records) {
            try {
                container.get_parent?.()?.remove_child(container);
                parent.visible = true;
                parent.insert_child_at_index(
                    container,
                    Math.max(0, Math.min(index, parent.get_n_children())),
                );
            } catch (error) {
                console.warn(
                    `[layout-switcher] status actor restore failed: ${error}`,
                );
            }
        }

        const quickSettingsMenu = panel.statusArea.quickSettings?.menu;
        if (quickSettingsMenu && this._quickSettingsArrow) {
            quickSettingsMenu._arrowSide = this._quickSettingsArrow.side;
            quickSettingsMenu._arrowAlignment =
                this._quickSettingsArrow.alignment;
        }

        this._owner = null;
        this._roles.clear();
        this._toggleDescriptor = null;
        this._menuManager = null;
        this._quickSettingsArrow = null;
    }

    diagnostics(taskbarPanels = []) {
        const panel = Main.panel;
        const roles = Object.entries(panel?.statusArea ?? {})
            .map(([role, indicator]) =>
                this._roleDiagnostics(role, indicator, taskbarPanels))
            .sort((a, b) => a.role.localeCompare(b.role));
        const orphanRoles = roles
            .filter(role => !role.onStage || !role.parent)
            .map(role => role.role);
        const openMenus = roles
            .filter(role => role.menuOpen)
            .map(role => role.role);

        return {
            available: Boolean(panel),
            hostOwned: Boolean(this._owner),
            generation: this._generation,
            adoptedRoles: [...this._roles.keys()],
            restorationPending: Boolean(this._owner && this._roles.size),
            nativeMenuManagerPreserved: Boolean(
                !this._owner || panel.menuManager === this._menuManager),
            host: this._actorDiagnostics(panel),
            panelBox: this._actorDiagnostics(Main.layoutManager.panelBox),
            boxes: {
                left: this._actorDiagnostics(panel?._leftBox),
                center: this._actorDiagnostics(panel?._centerBox),
                right: this._actorDiagnostics(panel?._rightBox),
            },
            roleCount: roles.length,
            externalRoles: roles
                .filter(role => !CORE_ROLES.has(role.role))
                .map(role => role.role),
            menuRoles: roles
                .filter(role => role.hasMenu)
                .map(role => role.role),
            openMenus,
            orphanRoles,
            dateMenu: this._dateMenuDiagnostics(panel?.statusArea?.dateMenu),
            quickSettings: this._quickSettingsDiagnostics(
                panel?.statusArea?.quickSettings),
            roles,
        };
    }

    _roleDiagnostics(role, indicator, taskbarPanels) {
        const container = indicator?.container ?? indicator;
        const menu = indicator?.menu;
        const stageRect = this._stageRect(container);
        return {
            role,
            type: this._typeName(indicator),
            parent: this._actorLabel(container?.get_parent?.()),
            location: this._location(container, taskbarPanels),
            visible: Boolean(container?.visible),
            mapped: Boolean(container?.mapped),
            onStage: this._isOnStage(container),
            hasMenu: Boolean(menu),
            menuOpen: Boolean(menu?.isOpen),
            menuMapped: Boolean(menu?.actor?.mapped),
            ...stageRect,
        };
    }

    _dateMenuDiagnostics(dateMenu) {
        const container = dateMenu?.container;
        return {
            present: Boolean(dateMenu),
            mapped: Boolean(container?.mapped),
            onStage: this._isOnStage(container),
            clock: dateMenu?._clockDisplay?.text ??
                dateMenu?._clock?.clock ?? '',
            menuOpen: Boolean(dateMenu?.menu?.isOpen),
        };
    }

    _quickSettingsDiagnostics(quickSettings) {
        const container = quickSettings?.container;
        const indicators = quickSettings?._indicators?.get_children?.() ?? [];
        const items = quickSettings?.menu?._grid?.get_children?.() ?? [];
        return {
            present: Boolean(quickSettings),
            mapped: Boolean(container?.mapped),
            onStage: this._isOnStage(container),
            indicatorCount: indicators.length,
            itemCount: items.length,
            menuOpen: Boolean(quickSettings?.menu?.isOpen),
            menuMapped: Boolean(quickSettings?.menu?.actor?.mapped),
        };
    }

    _location(actor, taskbarPanels) {
        const panel = Main.panel;
        let current = actor;
        for (let depth = 0; current && depth < 12; depth++) {
            if (current === panel?._leftBox)
                return 'left';
            if (current === panel?._centerBox)
                return 'center';
            if (current === panel?._rightBox)
                return 'right';
            if (current === panel)
                return 'panel';
            if (taskbarPanels.some(candidate => current === candidate))
                return 'taskbar';
            if (current === global.stage)
                return 'stage';
            current = current.get_parent?.();
        }
        return 'other';
    }

    _isOnStage(actor) {
        let current = actor;
        for (let depth = 0; current && depth < 32; depth++) {
            if (current === global.stage)
                return true;
            current = current.get_parent?.();
        }
        return false;
    }

    _actorDiagnostics(actor) {
        if (!actor)
            return {};
        return {
            type: this._typeName(actor),
            name: actor.name ?? actor.get_name?.() ?? '',
            classes: actor.get_style_class_name?.() ?? '',
            parent: this._actorLabel(actor.get_parent?.()),
            visible: Boolean(actor.visible),
            mapped: Boolean(actor.mapped),
            x: Math.round(actor.x ?? 0),
            y: Math.round(actor.y ?? 0),
            width: Math.round(actor.width ?? 0),
            height: Math.round(actor.height ?? 0),
        };
    }

    _stageRect(actor) {
        if (!actor?.get_transformed_position || !actor?.get_transformed_size)
            return {};
        try {
            const [stageX, stageY] = actor.get_transformed_position();
            const [stageWidth, stageHeight] = actor.get_transformed_size();
            return {
                stageX: Math.round(stageX),
                stageY: Math.round(stageY),
                stageWidth: Math.round(stageWidth),
                stageHeight: Math.round(stageHeight),
            };
        } catch (error) {
            return {};
        }
    }

    _actorLabel(actor) {
        if (!actor)
            return '';
        const name = actor.name ?? actor.get_name?.() ?? '';
        const classes = actor.get_style_class_name?.() ?? '';
        return [this._typeName(actor), name, classes]
            .filter(Boolean)
            .join(':');
    }

    _typeName(object) {
        return object?.constructor?.$gtype?.name ??
            object?.constructor?.name ?? '';
    }
}
