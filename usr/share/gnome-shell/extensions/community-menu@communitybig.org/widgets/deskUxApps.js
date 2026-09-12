// SPDX-License-Identifier: GPL-2.0-or-later
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Pango from 'gi://Pango';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as AppFavorites from 'resource:///org/gnome/shell/ui/appFavorites.js';
import * as DND from 'resource:///org/gnome/shell/ui/dnd.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as ParentalControlsManager from 'resource:///org/gnome/shell/misc/parentalControlsManager.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';

import {AppFolders} from '../appFolders.js';
import {folderMembers, containsApp} from '../folderModel.js';
import {getOrientationProp} from '../utils.js';
import {AppItemMenu} from './secondaryMenu.js';
import {Grid, ScrollView} from './widgets.js';

function box(vertical, style = '') {
    return new St.BoxLayout({...getOrientationProp(vertical), x_expand: true, style_class: style});
}

function button(text, action) {
    const actor = new St.Button({label: text, can_focus: true, style_class: 'button desk-ux-action'});
    actor.connect('clicked', action);
    return actor;
}

const Tile = GObject.registerClass(class CommunityBigDeskUxTile extends St.Button {
    _init(owner, {app = null, folder = null, favorite = false, members = []}) {
        const title = app ? app.get_name() : owner.folderName(folder);
        super._init({can_focus: true, track_hover: true, accessible_name: title,
            toggle_mode: Boolean(app && owner.view === '@create'),
            style_class: folder ? 'desk-ux-tile desk-ux-folder' : 'desk-ux-tile'});
        this._delegate = this;
        this.owner = owner;
        this.app = app;
        this.folder = folder;
        this.favorite = favorite;
        const content = box(true, 'desk-ux-tile-content');
        content.y_align = Clutter.ActorAlign.START;
        if (app) {
            this.icon = app.create_icon_texture(40);
            this.icon.set({x_expand: true, y_expand: true,
                x_align: Clutter.ActorAlign.CENTER, y_align: Clutter.ActorAlign.CENTER});
            const iconBox = new St.Widget({layout_manager: new Clutter.BinLayout(),
                style_class: 'desk-ux-icon-slot', x_expand: true});
            iconBox.add_child(this.icon);
            const selected = new St.Icon({icon_name: 'object-select-symbolic', icon_size: 14,
                opacity: 0});
            const selectionBox = new St.Bin({style_class: 'desk-ux-selection-box',
                visible: this.toggle_mode, x_expand: true, y_expand: true,
                x_align: Clutter.ActorAlign.END, y_align: Clutter.ActorAlign.START,
                child: selected});
            iconBox.add_child(selectionBox);
            this.connect('notify::checked', () => {
                selected.opacity = this.checked ? 255 : 0;
                if (this.checked)
                    selectionBox.add_style_pseudo_class('checked');
                else
                    selectionBox.remove_style_pseudo_class('checked');
            });
            content.add_child(iconBox);
        } else {
            const preview = new Grid(2, 8, 8);
            preview.add_style_class_name('desk-ux-folder-preview');
            // Always reserve four cells, including folders with a single app.
            for (let index = 0; index < 4; index++) {
                const cell = new St.Bin({style_class: 'desk-ux-preview-cell'});
                if (members[index])
                    cell.set_child(members[index].app.create_icon_texture(34));
                preview.add_item(cell);
            }
            content.add_child(preview);
        }
        const label = new St.Label({text: title, x_align: Clutter.ActorAlign.CENTER,
            y_align: Clutter.ActorAlign.START});
        label.clutter_text.set_single_line_mode(false);
        label.clutter_text.set_line_wrap(true);
        label.clutter_text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);
        label.clutter_text.set_ellipsize(Pango.EllipsizeMode.NONE);
        content.add_child(label);
        this.set_child(content);
        this.connect('clicked', () => owner.activateTile(this));
        const context = new Clutter.ClickGesture({required_button: Clutter.BUTTON_SECONDARY,
            recognize_on_press: true});
        context.connect('recognize', () => owner.openContext(this));
        this.add_action(context);
        this.connect('key-press-event', (_actor, event) => {
            if (event.get_key_symbol() === Clutter.KEY_Menu ||
                (event.get_key_symbol() === Clutter.KEY_F10 &&
                 (event.get_state() & Clutter.ModifierType.SHIFT_MASK))) {
                owner.openContext(this);
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });
        if (app && owner.view !== '@create') {
            this._draggable = DND.makeDraggable(this, {restoreOnSuccess: true});
            this._draggable.connect('drag-begin', () => owner.beginDrag());
            this._draggable.connect('drag-end', () => owner.endDrag());
        }
        this.connect('destroy', () => {
            if (this.menu) {
                owner.menuManager.removeMenu(this.menu);
                this.menu.destroy();
                this.menu = null;
            }
        });
    }

    getDragActor() {
        return this.app.create_icon_texture(40);
    }

    getDragActorSource() {
        return this.icon;
    }

    handleDragOver(source) {
        return this.owner.dragOver(this, source);
    }

    acceptDrop(source) {
        return this.owner.drop(this, source);
    }
});

export const DeskUxApps = GObject.registerClass({Signals: {
    'activated': {},
    'name-entry-changed': {param_types: [GObject.TYPE_BOOLEAN]},
}},
class CommunityBigDeskUxApps extends St.BoxLayout {
    _init() {
        super._init({...getOrientationProp(true), x_expand: true, y_expand: true,
            style_class: 'desk-ux-apps'});
        this.view = null;
        this._selected = new Set();
        this._appSystem = Shell.AppSystem.get_default();
        this._parental = ParentalControlsManager.getDefault();
        this._favorites = AppFavorites.getAppFavorites();
        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this._store = new AppFolders(() => this.queueRender(), () => this._appRecords(false));
        this._scroll = new ScrollView({x_expand: true, y_expand: true});
        this._content = box(true, 'desk-ux-content');
        this._scroll.set_child(this._content);
        this.add_child(this._scroll);
        this._appSystem.connectObject('installed-changed', () => this.queueRender(), this);
        this._parental.connectObject('app-filter-changed', () => this.queueRender(), this);
        this._favorites.connectObject('changed', () => this.queueRender(), this);
        this.connect('notify::mapped', () => {
            if (!this.mapped)
                this.closeMenus();
        });
        this.connect('destroy', () => {
            this._destroyed = true;
            this.endDrag();
            if (this._idle)
                GLib.source_remove(this._idle);
            this._idle = 0;
            this._store.destroy();
        });
        this._render();
    }

    _appRecords(visible = true) {
        const records = new Map();
        for (const info of Gio.AppInfo.get_all()) {
            const id = info.get_id();
            if (!id || (visible && (!info.should_show() || !this._parental.shouldShowApp(info))))
                continue;
            const app = this._appSystem.lookup_app(id);
            if (visible && !app)
                continue;
            records.set(id, {id, app, name: info.get_display_name(),
                categories: (info.get_categories?.() ?? '').split(';').filter(Boolean)});
        }
        return [...records.values()].sort((a, b) => a.name.localeCompare(b.name));
    }

    folderName(folder) {
        return (folder.translate ? Shell.util_get_translated_folder_name(folder.name) : null)
            ?? folder.name;
    }

    queueRender() {
        if (this._destroyed || this._dragging || this._idle)
            return;
        this._idle = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._idle = 0;
            this._render();
            return GLib.SOURCE_REMOVE;
        });
    }

    navigate(view = null, selected = []) {
        this.view = view;
        this._selected = new Set(selected);
        this._scroll.resetScroll();
        this._focusOnRender = view !== null;
        this.queueRender();
    }

    reset() {
        this.navigate();
    }

    back() {
        if (this.view === null)
            return false;
        this.navigate();
        return true;
    }

    closeMenus() {
        for (const tile of this._tiles ?? [])
            tile.menu?.close();
    }

    get hasNameEntry() {
        return this._nameEntry !== null;
    }

    _heading(title, action = null) {
        const row = box(false, 'desk-ux-heading');
        row.add_child(new St.Label({text: title, x_expand: true, y_align: Clutter.ActorAlign.CENTER}));
        if (action)
            row.add_child(action);
        this._content.add_child(row);
        return row;
    }

    _grid(items, folders = false) {
        const grid = new Grid(folders ? 4 : 6, 6, 6);
        grid.add_style_class_name('desk-ux-grid');
        for (const item of items) {
            const tile = new Tile(this, item);
            if (this.view === '@create' && this._selected.has(item.app.get_id()))
                tile.checked = true;
            this._tiles.push(tile);
            grid.add_item(tile);
        }
        this._content.add_child(grid);
        return grid;
    }

    _dropArea(actor, kind) {
        actor._delegate = {
            handleDragOver: source => this.dragOver({kind, actor}, source),
            acceptDrop: source => this.drop({kind, actor}, source),
        };
    }

    _render() {
        if (this._dragging)
            return;
        const focused = this._tiles?.find(t => t.has_key_focus());
        const focusId = focused?.app?.get_id() ?? focused?.folder?.id;
        const restoreFocus = this._focusOnRender || Boolean(focused);
        this._focusOnRender = false;
        const apps = this._appRecords();
        const folders = this._store.snapshot();
        const current = folders.find(f => f.id === this.view);
        // Suspend find-as-you-type before adding a second editable text actor.
        this.emit('name-entry-changed', Boolean(current || this.view === '@create'));
        if (global.stage.key_focus && this._content.contains(global.stage.key_focus))
            global.stage.set_key_focus(null);
        this._content.destroy_all_children();
        this._tiles = [];
        this._nameEntry = null;
        this._selectionCount = null;
        if (this.view && !['@all', '@create'].includes(this.view) && !current)
            this.view = null;
        if (this.view !== null) {
            const title = current ? this.folderName(current) : this.view === '@all' ? _('All Apps') : _('New Folder');
            this._heading(title, button(_('Back'), () => this.navigate()));
            if (current || this.view === '@create') {
                const row = box(false, 'desk-ux-heading');
                this._nameEntry = new St.Entry({text: current ? this.folderName(current) : _('New Folder'),
                    hint_text: _('Folder Name'), accessible_name: _('Folder Name'), can_focus: true, x_expand: true});
                row.add_child(this._nameEntry);
                const save = () => {
                    const name = this._nameEntry.get_text();
                    const id = this.perform(current
                        ? {type: 'rename', folder: current.id, name}
                        : {type: 'create', apps: [...this._selected], name});
                    if (id)
                        this.navigate(id);
                };
                this._saveButton = button(current ? _('Rename') : _('Create Folder'), save);
                row.add_child(this._saveButton);
                this._nameEntry.clutter_text.connect('text-changed', () => this._updateSave());
                this._nameEntry.clutter_text.connect('activate', () => {
                    if (this._saveButton.reactive)
                        save();
                });
                this._content.add_child(row);
                if (!current) {
                    const selectionHeading = this._heading(_('Select at least two applications'));
                    this._selectionCount = new St.Label({style_class: 'desk-ux-selection-count',
                        y_align: Clutter.ActorAlign.CENTER});
                    selectionHeading.add_child(this._selectionCount);
                }
            }
            this._grid((current ? folderMembers(current, apps) : apps).map(a => ({app: a.app})));
            if (current) {
                const remove = button(_('Move outside folders'), () => {});
                remove.reactive = false;
                remove.can_focus = false;
                this._dropArea(remove, 'ungroup');
                this._content.add_child(remove);
            }
            this._updateSave();
        } else {
            const favorites = this._favorites.getFavorites().filter(app => apps.some(a => a.id === app.get_id()));
            const heading = this._heading(_('Pinned Applications'), button(_('All Apps'), () => this.navigate('@all')));
            this._dropArea(heading, 'pin');
            const pinned = this._grid(favorites.map(app => ({app, favorite: true})));
            this._dropArea(pinned, 'pin');
            if (!favorites.length)
                this._heading(_('Right-click an application to pin it'));
            this._heading(_('Folders'), button(_('New Folder'), () => this.navigate('@create')));
            const visibleFolders = folders.map(folder => ({folder, members: folderMembers(folder, apps)}))
                .filter(f => f.members.length);
            this._grid(visibleFolders, true);
            const ungrouped = apps.filter(app => !folders.some(folder => containsApp(folder, app)) &&
                !this._favorites.isFavorite(app.id));
            const outside = this._heading(_('Other Applications'));
            this._dropArea(outside, 'ungroup');
            const loose = this._grid(ungrouped.map(a => ({app: a.app})));
            this._dropArea(loose, 'ungroup');
        }
        if (restoreFocus && this.mapped)
            (this._tiles.find(t => (t.app?.get_id() ?? t.folder?.id) === focusId) ?? this._tiles[0])?.grab_key_focus();
        this._suppressActivation = false;
    }

    _updateSave() {
        if (!this._nameEntry)
            return;
        const name = this._nameEntry.get_text().trim();
        const enabled = name.length > 0 && name.length <= 120 &&
            (this.view !== '@create' || this._selected.size >= 2);
        if (this._selectionCount)
            this._selectionCount.text = `${this._selected.size.toLocaleString()} / ${(2).toLocaleString()}`;
        this._saveButton.reactive = enabled;
        this._saveButton.can_focus = enabled;
    }

    activateTile(tile) {
        if (this._dragging || this._suppressActivation)
            return;
        if (tile.folder) {
            this.navigate(tile.folder.id);
        } else if (this.view === '@create') {
            const id = tile.app.get_id();
            if (this._selected.has(id)) {
                this._selected.delete(id);
                tile.checked = false;
            } else {
                this._selected.add(id);
                tile.checked = true;
            }
            this._updateSave();
        } else {
            tile.app.activate();
            this.emit('activated');
        }
    }

    perform(operation) {
        try {
            return this._store.edit(operation) ?? true;
        } catch (error) {
            console.error(`Community Menu folder edit: ${error.message}`);
            Main.notifyError(_('Could not update application folders'),
                _('No applications were removed. Check whether folder settings are locked.'));
            return false;
        }
    }

    openContext(tile) {
        if (this._dragging || this.view === '@create')
            return;
        this.closeMenus();
        if (tile.menu) {
            this.menuManager.removeMenu(tile.menu);
            tile.menu.destroy();
        }
        const menu = tile.app ? new AppItemMenu(tile) : new PopupMenu.PopupMenu(tile, 0.5, St.Side.TOP);
        tile.menu = menu;
        if (!tile.app)
            Main.uiGroup.add_child(menu.actor);
        else
            menu.connect('activate-window', () => this.emit('activated'));
        this.menuManager.addMenu(menu);
        if (tile.folder) {
            menu.addAction(_('Rename'), () => this.navigate(tile.folder.id));
            menu.addAction(_('Dissolve Folder'), () => this.perform({type: 'dissolve', folder: tile.folder.id}));
        } else {
            const id = tile.app.get_id();
            menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
            const move = new PopupMenu.PopupSubMenuMenuItem(_('Move to Folder'));
            for (const folder of this._store.snapshot())
                move.menu.addAction(this.folderName(folder), () => this.perform({type: 'move', folder: folder.id, apps: [id]}));
            menu.addMenuItem(move);
            menu.addAction(_('New Folder'), () => this.navigate('@create', [id]));
            menu.addAction(_('Move outside folders'), () => this.perform({type: 'ungroup', apps: [id]}));
        }
        menu.open();
    }

    beginDrag() {
        this.closeMenus();
        this._dragging = true;
        this._suppressActivation = true;
        this._monitor = {dragMotion: event => {
            this._dragPoint = [event.x, event.y];
            this._highlight?.remove_style_pseudo_class('drop');
            this._highlight = null;
            return DND.DragMotionResult.CONTINUE;
        }};
        DND.addDragMonitor(this._monitor);
        this._scrollTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, () => {
            if (!this._dragPoint || !this._scroll.mapped)
                return GLib.SOURCE_CONTINUE;
            const [x, y] = this._dragPoint;
            const [left, top] = this._scroll.get_transformed_position();
            const [width, height] = this._scroll.get_transformed_size();
            if (x < left || x > left + width || y < top || y > top + height)
                return GLib.SOURCE_CONTINUE;
            const edge = 32 * St.ThemeContext.get_for_stage(global.stage).scale_factor;
            const step = y < top + edge ? -12 : y > top + height - edge ? 12 : 0;
            const adjustment = this._scroll.vadjustment;
            adjustment.value = Math.max(adjustment.lower,
                Math.min(adjustment.upper - adjustment.page_size, adjustment.value + step));
            return GLib.SOURCE_CONTINUE;
        });
    }

    endDrag() {
        if (this._monitor)
            DND.removeDragMonitor(this._monitor);
        this._monitor = null;
        if (this._scrollTimer)
            GLib.source_remove(this._scrollTimer);
        this._scrollTimer = 0;
        this._dragPoint = null;
        this._highlight?.remove_style_pseudo_class('drop');
        this._highlight = null;
        this._dragging = false;
        this.queueRender();
    }

    _canDrop(target, source) {
        return this.view !== '@create' && source?.owner === this && source.app && source !== target &&
            (!target.app || source.app.get_id() !== target.app.get_id());
    }

    dragOver(target, source) {
        if (!this._canDrop(target, source))
            return DND.DragMotionResult.NO_DROP;
        this._highlight = target.actor ?? target;
        this._highlight.add_style_pseudo_class('drop');
        return target.favorite || target.kind === 'pin' ? DND.DragMotionResult.COPY_DROP : DND.DragMotionResult.MOVE_DROP;
    }

    drop(target, source) {
        if (!this._canDrop(target, source))
            return false;
        const id = source.app.get_id();
        if (target.favorite || target.kind === 'pin') {
            if (!global.settings.is_writable('favorite-apps'))
                return false;
            const pos = target.app ? this._favorites.getFavorites().findIndex(a => a.get_id() === target.app.get_id()) : -1;
            if (this._favorites.isFavorite(id))
                this._favorites.moveFavoriteToPos(id, pos);
            else
                this._favorites.addFavoriteAtPos(id, pos);
            return true;
        }
        if (target.kind === 'ungroup')
            return Boolean(this.perform({type: 'ungroup', apps: [id]}));
        if (target.folder)
            return Boolean(this.perform({type: 'move', folder: target.folder.id, apps: [id]}));
        if (target.app) {
            const folder = this.perform({type: 'create', name: _('New Folder'), apps: [id, target.app.get_id()]});
            if (folder)
                this.navigate(folder);
            return Boolean(folder);
        }
        return false;
    }
});
