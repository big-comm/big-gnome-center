// SPDX-License-Identifier: GPL-3.0-or-later

import GLib from 'gi://GLib';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {ShellBlurSurface} from './shellBlurSurface.js';

const TARGET_CLASS = 'frosted-glass-shell-surface';
const QUICK_SUBMENU_CLASS = 'frosted-glass-quick-submenu';
const LIGHT_STYLE_CLASS = 'frosted-glass-light';
const THEME_RADIUS_KINDS = new Set([
    'panel',
    'dash-to-panel',
    'dash-to-dock',
    'quick-settings',
    'date-menu',
    'notification-banner',
    'system-dialog',
]);

const CORNER_RADII = {
    panel: 18,
    'dash-to-panel': 18,
    'dash-to-dock': 20,
    'layout-menu': 24,
    'quick-settings': 36,
    'date-menu': 28,
    'notification-banner': 16,
    'system-dialog': 24,
};

function styleClasses(actor) {
    try {
        return new Set((actor.get_style_class_name?.() ?? '').split(/\s+/).filter(Boolean));
    } catch (error) {
        return new Set();
    }
}

function findDescendants(root, predicate, maxDepth = 12) {
    const found = [];
    const seen = new WeakSet();
    const stack = [{actor: root, depth: 0}];
    while (stack.length) {
        const {actor, depth} = stack.pop();
        if (!actor || seen.has(actor) || depth > maxDepth)
            continue;
        seen.add(actor);
        if (predicate(actor))
            found.push(actor);
        let children = [];
        try {
            children = actor.get_children?.() ?? [];
        } catch (error) {
            continue;
        }
        for (const child of children)
            stack.push({actor: child, depth: depth + 1});
    }
    return found;
}

function findFirstDescendant(root, predicate, maxDepth = 12) {
    const seen = new WeakSet();
    const queue = [{actor: root, depth: 0}];
    while (queue.length) {
        const {actor, depth} = queue.shift();
        if (!actor || seen.has(actor) || depth > maxDepth)
            continue;
        seen.add(actor);
        if (predicate(actor))
            return actor;
        try {
            for (const child of actor.get_children?.() ?? [])
                queue.push({actor: child, depth: depth + 1});
        } catch (error) {
            // Actor may be disposed while a popup is closing.
        }
    }
    return null;
}

function relativeGeometry(actor, container) {
    const [actorX, actorY] = actor.get_transformed_position();
    const [containerX, containerY] = container.get_transformed_position();
    return {
        x: Math.round(actorX - containerX),
        y: Math.round(actorY - containerY),
        width: actor.width,
        height: actor.height,
    };
}

export class ShellSurfaces {
    constructor(getConfig) {
        this._getConfig = getConfig;
        this._records = new Map();
        this._quickSubmenus = new Set();
        this._scanId = 0;
        this._refreshId = 0;
        this._modalDialogSignal = 0;
        this._messageTraySignals = [];
    }

    enable() {
        this.refresh();
        const modalGroup = Main.layoutManager.modalDialogGroup;
        if (modalGroup) {
            this._modalDialogSignal = modalGroup.connect('child-added', () =>
                this._queueRefresh());
        }
        const bannerBin = Main.messageTray?._bannerBin;
        if (bannerBin) {
            for (const signal of ['child-added', 'child-removed']) {
                try {
                    this._messageTraySignals.push([
                        bannerBin,
                        bannerBin.connect(signal, () => this._queueRefresh()),
                    ]);
                } catch (error) {
                    // Message tray internals may differ across Shell releases.
                }
            }
        }
        this._scanId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this.refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    refresh() {
        const config = this._getConfig();
        const quickSubmenus = new Set();
        const targets = config.enabled
            ? this._discover(config, quickSubmenus)
            : new Map();

        this._syncQuickSubmenus(quickSubmenus, config.lightMode);

        for (const [actor, record] of this._records) {
            if (!targets.has(actor)) {
                record.destroy();
                this._records.delete(actor);
            }
        }

        for (const [actor, kind] of targets) {
            let surface = this._records.get(actor);
            if (!surface) {
                const container = actor.get_parent?.();
                if (!container)
                    continue;
                surface = new ShellBlurSurface(actor, {
                    kind,
                    container,
                    cornerRadius: CORNER_RADII[kind] ?? 18,
                    themeCornerRadius: THEME_RADIUS_KINDS.has(kind),
                    geometryProvider: () => relativeGeometry(actor, container),
                });
                this._records.set(actor, surface);
            }
            surface.update(kind === 'layout-menu'
                ? {
                    ...config,
                    lightMode: config.appLightMode,
                    brightness: config.appLightMode ? 1.0 : 0.9,
                }
                : config);
        }
    }

    destroy() {
        if (this._refreshId) {
            GLib.source_remove(this._refreshId);
            this._refreshId = 0;
        }
        if (this._scanId) {
            GLib.source_remove(this._scanId);
            this._scanId = 0;
        }
        if (this._modalDialogSignal) {
            try {
                Main.layoutManager.modalDialogGroup.disconnect(
                    this._modalDialogSignal);
            } catch (error) {
                // Shell teardown may dispose the group first.
            }
            this._modalDialogSignal = 0;
        }
        for (const [object, id] of this._messageTraySignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Message tray may be disposed during Shell teardown.
            }
        }
        for (const surface of this._records.values())
            surface.destroy();
        this._records.clear();
        this._syncQuickSubmenus(new Set(), false);
    }

    _queueRefresh() {
        if (this._refreshId)
            return;
        this._refreshId = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._refreshId = 0;
            this.refresh();
            return GLib.SOURCE_REMOVE;
        });
    }

    _discover(config, quickSubmenus) {
        const targets = new Map();
        if (config.panelEnabled)
            this._discoverPanels(targets);
        if (config.dockEnabled)
            this._discoverDocks(targets);
        if (config.layoutMenusEnabled)
            this._discoverLayoutMenus(targets);
        if (config.quickSettingsEnabled)
            this._discoverQuickSettings(targets, quickSubmenus);
        if (config.calendarEnabled) {
            this._discoverDateMenu(targets);
            this._discoverNotificationBanner(targets);
        }
        if (config.systemDialogsEnabled)
            this._discoverSystemDialogs(targets);
        return targets;
    }

    _discoverPanels(targets) {
        const dashToPanelPanels = global.dashToPanel?.panels ?? [];
        const managedPanels = new Set(dashToPanelPanels
            .map(panelInfo => panelInfo?.panel)
            .filter(Boolean));

        if (Main.panel && !managedPanels.has(Main.panel))
            targets.set(Main.panel, 'panel');

        for (const panelInfo of dashToPanelPanels) {
            if (panelInfo?.get_parent?.())
                targets.set(panelInfo, 'dash-to-panel');
        }
    }

    _discoverDocks(targets) {
        const roots = [Main.layoutManager.uiGroup, Main.uiGroup].filter(Boolean);
        for (const root of roots) {
            for (const actor of findDescendants(root, candidate => {
                const name = candidate.name ?? '';
                return name === 'dashtodockContainer';
            }, 5)) {
                const backgrounds = findDescendants(actor,
                    child => styleClasses(child).has('dash-background'), 5);
                for (const background of backgrounds)
                    targets.set(background, 'dash-to-dock');
            }
        }
    }

    _discoverLayoutMenus(targets) {
        for (const actor of findDescendants(Main.uiGroup,
            candidate => styleClasses(candidate).has('community-menu'))) {
            const contents = findDescendants(actor,
                child => styleClasses(child).has('popup-menu-content'), 5);
            if (contents.length) {
                for (const content of contents)
                    targets.set(content, 'layout-menu');
            } else {
                targets.set(actor, 'layout-menu');
            }
        }
    }

    _discoverQuickSettings(targets, quickSubmenus) {
        const panels = [Main.panel, ...(global.dashToPanel?.panels ?? [])];
        for (const panelInfo of panels) {
            const panel = panelInfo.panel ?? panelInfo;
            const root = panel?.statusArea?.quickSettings?.menu?.actor ??
                panel?.statusArea?.quickSettings?.menu?._overlay;
            if (!root)
                continue;
            for (const submenu of findDescendants(root,
                candidate => styleClasses(candidate).has('quick-toggle-menu'), 10))
                quickSubmenus.add(submenu);
            const content = findFirstDescendant(root,
                candidate => styleClasses(candidate).has('quick-settings'), 7) ??
                findFirstDescendant(root,
                    candidate => styleClasses(candidate).has('popup-menu-content'), 7) ??
                root;
            targets.set(content, 'quick-settings');
        }
    }

    _syncQuickSubmenus(nextActors, lightMode) {
        for (const actor of this._quickSubmenus) {
            if (!nextActors.has(actor)) {
                try {
                    actor.remove_style_class_name?.(QUICK_SUBMENU_CLASS);
                    actor.remove_style_class_name?.(LIGHT_STYLE_CLASS);
                } catch (error) {
                    // Submenu may be disposed during a Shell rebuild.
                }
            }
        }
        for (const actor of nextActors) {
            if (!this._quickSubmenus.has(actor)) {
                try {
                    actor.add_style_class_name?.(QUICK_SUBMENU_CLASS);
                } catch (error) {
                    // Submenu may be disposed during a Shell rebuild.
                }
            }
            try {
                if (lightMode)
                    actor.add_style_class_name?.(LIGHT_STYLE_CLASS);
                else
                    actor.remove_style_class_name?.(LIGHT_STYLE_CLASS);
            } catch (error) {
                // Submenu may be disposed during a Shell rebuild.
            }
        }
        this._quickSubmenus = nextActors;
    }

    _discoverDateMenu(targets) {
        const panels = [Main.panel, ...(global.dashToPanel?.panels ?? [])];
        for (const panelInfo of panels) {
            const panel = panelInfo.panel ?? panelInfo;
            const dateMenu = panel?.statusArea?.dateMenu;
            const root = dateMenu?.menu?.actor;
            if (!root)
                continue;
            const content = dateMenu.menu.box ??
                findFirstDescendant(root,
                    candidate => styleClasses(candidate).has('datemenu-popover'), 5) ??
                findFirstDescendant(root,
                    candidate => styleClasses(candidate).has('popup-menu-content'), 5);
            if (content)
                targets.set(content, 'date-menu');
        }
    }

    _discoverNotificationBanner(targets) {
        const bannerBin = Main.messageTray?._bannerBin;
        const banner = Main.messageTray?._banner ??
            findFirstDescendant(bannerBin,
                candidate => styleClasses(candidate).has('notification-banner'), 2);
        if (banner?.mapped)
            targets.set(banner, 'notification-banner');
    }

    _discoverSystemDialogs(targets) {
        const root = Main.layoutManager.modalDialogGroup;
        if (!root)
            return;
        for (const dialog of findDescendants(root,
            candidate => styleClasses(candidate).has('modal-dialog'), 10))
            targets.set(dialog, 'system-dialog');
    }
}
