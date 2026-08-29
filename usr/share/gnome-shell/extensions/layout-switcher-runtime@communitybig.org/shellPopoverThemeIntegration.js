// SPDX-License-Identifier: GPL-2.0-or-later

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const INTERFACE_SCHEMA = 'org.gnome.desktop.interface';
const SCAN_INTERVAL_SECONDS = 2;
const STYLE_CLASSES = {
    'quick-settings': 'layout-switcher-light-quick-settings',
    'date-menu': 'layout-switcher-light-date-menu',
    'notification-banner': 'layout-switcher-light-notification-banner',
};

function styleClasses(actor) {
    try {
        return new Set((actor.get_style_class_name?.() ?? '')
            .split(/\s+/).filter(Boolean));
    } catch (error) {
        return new Set();
    }
}

function findFirstDescendant(root, predicate, maxDepth = 8) {
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
            // Popup children may be disposed while their menu closes.
        }
    }
    return null;
}

export class ShellPopoverThemeIntegration {
    constructor() {
        this._layout = 'Minimal';
        this._records = new Map();
        this._messageTraySignals = [];
        this._actorDestroyCount = 0;
        this._refreshCount = 0;
    }

    enable() {
        if (this._interfaceSettings)
            return;
        this._interfaceSettings = new Gio.Settings({schema_id: INTERFACE_SCHEMA});
        this._schemeSignal = this._interfaceSettings.connect(
            'changed::color-scheme', () => this._refresh());
        const bannerBin = Main.messageTray?._bannerBin;
        if (bannerBin) {
            for (const signal of ['child-added', 'child-removed']) {
                try {
                    this._messageTraySignals.push([
                        bannerBin,
                        bannerBin.connect(signal, () => this._queueRefresh()),
                    ]);
                } catch (error) {
                    // Message tray internals differ across Shell releases.
                }
            }
        }
        this._scanId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT, SCAN_INTERVAL_SECONDS, () => {
                this._refresh();
                return GLib.SOURCE_CONTINUE;
            });
        this._refresh();
    }

    apply(layout) {
        this._layout = layout;
        this._refresh();
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
        if (this._schemeSignal)
            this._interfaceSettings?.disconnect(this._schemeSignal);
        this._schemeSignal = 0;
        for (const [object, id] of this._messageTraySignals.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Shell teardown may dispose the banner container first.
            }
        }
        this._syncRecords(new Map());
        this._interfaceSettings = null;
    }

    _lightRequested() {
        return this._layout !== 'Minimal' &&
            this._interfaceSettings?.get_string('color-scheme') !== 'prefer-dark';
    }

    _queueRefresh() {
        if (this._refreshId)
            return;
        this._refreshId = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._refreshId = 0;
            this._refresh();
            return GLib.SOURCE_REMOVE;
        });
    }

    _refresh() {
        this._refreshCount++;
        this._syncRecords(this._discover());
    }

    _discover() {
        const records = new Map();
        const panels = [Main.panel, ...(global.dashToPanel?.panels ?? [])];
        for (const panelInfo of panels) {
            const panel = panelInfo?.panel ?? panelInfo;
            this._discoverQuickSettings(panel, records);
            this._discoverDateMenu(panel, records);
        }

        const bannerBin = Main.messageTray?._bannerBin;
        const banner = Main.messageTray?._banner ?? findFirstDescendant(
            bannerBin,
            actor => styleClasses(actor).has('notification-banner'),
            3);
        if (banner)
            records.set(banner, 'notification-banner');
        return records;
    }

    _discoverQuickSettings(panel, records) {
        const root = panel?.statusArea?.quickSettings?.menu?.actor ?? null;
        if (!root)
            return;
        records.set(root, 'quick-settings');
        const content = findFirstDescendant(root,
            actor => styleClasses(actor).has('quick-settings')) ??
            findFirstDescendant(root,
                actor => styleClasses(actor).has('popup-menu-content'));
        if (content)
            records.set(content, 'quick-settings');
    }

    _discoverDateMenu(panel, records) {
        const dateMenu = panel?.statusArea?.dateMenu;
        const root = dateMenu?.menu?.actor ?? null;
        if (!root)
            return;
        records.set(root, 'date-menu');
        const content = dateMenu.menu.box ?? findFirstDescendant(root,
            actor => styleClasses(actor).has('datemenu-popover'), 5) ??
            findFirstDescendant(root,
                actor => styleClasses(actor).has('popup-menu-content'), 5);
        if (content)
            records.set(content, 'date-menu');
    }

    _syncRecords(nextRecords) {
        for (const [actor, record] of this._records) {
            if (nextRecords.get(actor) === record.kind)
                continue;
            this._releaseActor(actor, record);
        }

        for (const [actor, kind] of nextRecords) {
            if (!this._records.has(actor)) {
                let destroyId = 0;
                try {
                    destroyId = actor.connect('destroy', () => {
                        const record = this._records.get(actor);
                        if (record?.destroyId !== destroyId)
                            return;
                        this._records.delete(actor);
                        this._actorDestroyCount++;
                    });
                } catch (error) {
                    // Actor disposal may race discovery.
                    continue;
                }
                this._records.set(actor, {kind, destroyId});
            }
            try {
                if (this._lightRequested())
                    actor.add_style_class_name(STYLE_CLASSES[kind]);
                else
                    actor.remove_style_class_name(STYLE_CLASSES[kind]);
            } catch (error) {
                // Shell may rebuild popovers during profile changes.
            }
        }
    }

    _releaseActor(actor, record) {
        this._records.delete(actor);
        try {
            if (record.destroyId)
                actor.disconnect(record.destroyId);
            actor.remove_style_class_name(STYLE_CLASSES[record.kind]);
        } catch (error) {
            // A destroy callback normally removes disposed actors first.
        }
    }

    diagnostics() {
        const kinds = {
            quickSettings: 0,
            dateMenu: 0,
            notificationBanners: 0,
        };
        let classActors = 0;
        for (const [actor, record] of this._records) {
            const {kind} = record;
            if (kind === 'quick-settings')
                kinds.quickSettings++;
            else if (kind === 'date-menu')
                kinds.dateMenu++;
            else if (kind === 'notification-banner')
                kinds.notificationBanners++;
            try {
                if (actor.has_style_class_name(STYLE_CLASSES[kind]))
                    classActors++;
            } catch (error) {
                // Diagnostics tolerate actors disposed between scans.
            }
        }
        return {
            implementation: 'layout-switcher-runtime',
            connected: Boolean(this._schemeSignal),
            bannerSignals: this._messageTraySignals.length,
            layout: this._layout,
            colorScheme: this._interfaceSettings?.get_string('color-scheme') ?? '',
            lightRequested: this._lightRequested(),
            menusAvailable: kinds.quickSettings > 0 && kinds.dateMenu > 0,
            kinds,
            ownedActors: this._records.size,
            classActors,
            actorDestroyCount: this._actorDestroyCount,
            refreshPending: Boolean(this._refreshId),
            refreshCount: this._refreshCount,
        };
    }
}
