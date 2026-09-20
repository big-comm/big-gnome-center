// SPDX-License-Identifier: GPL-2.0-or-later
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Pango from 'gi://Pango';
import Shell from 'gi://Shell';
import St from 'gi://St';
import Gettext from 'gettext';

import * as DND from 'resource:///org/gnome/shell/ui/dnd.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as ParentalControlsManager from 'resource:///org/gnome/shell/misc/parentalControlsManager.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';

import {AppFolders} from '../appFolders.js';
import {FolderColors} from '../folderColors.js';
import {MenuPins} from '../menuPins.js';
import {FOLDER_COLORS, matchesQuery, folderTint, gridColumns, tileWidth, scrollEdge, SessionRecents} from '../deskUxModel.js';
import {folderMembers, containsApp} from '../folderModel.js';
import {getOrientationProp} from '../utils.js';
import {AppItemMenu} from './secondaryMenu.js';
import {Grid, ScrollView} from './widgets.js';

// Reuse the system theme picker's translated palette labels.
const themeText = text => Gettext.dgettext('big-gnome-center', text);

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
            toggle_mode: Boolean(app && owner.selecting),
            style_class: folder ? 'desk-ux-tile desk-ux-folder' : 'desk-ux-tile'});
        this._delegate = this;
        this.owner = owner;
        this.app = app;
        this.folder = folder;
        this.favorite = favorite;
        const list = app && owner.listMode;
        if (list)
            this.add_style_class_name('desk-ux-list-tile');
        const content = box(!list, 'desk-ux-tile-content');
        content.y_align = Clutter.ActorAlign.START;
        if (app) {
            this.icon = app.create_icon_texture(list ? 36 : 48);
            this.icon.set({x_expand: true, y_expand: true,
                x_align: Clutter.ActorAlign.CENTER, y_align: Clutter.ActorAlign.CENTER});
            const iconBox = new St.Widget({layout_manager: new Clutter.BinLayout(),
                style_class: 'desk-ux-icon-slot', x_expand: !list});
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
            const color = owner._folderColors.get(folder.id);
            this.add_style_class_name(color ? `desk-ux-color-${color}` : `desk-ux-tint-${folderTint(folder.id)}`);
            const preview = box(false, 'desk-ux-folder-preview');
            preview.add_style_class_name('desk-ux-folder-preview');
            for (let index = 0; index < 3; index++) {
                const cell = new St.Bin({style_class: 'desk-ux-preview-cell'});
                if (members[index])
                    cell.set_child(members[index].app.create_icon_texture(35));
                preview.add_child(cell);
            }
            content.add_child(preview);
        }
        const label = new St.Label({text: title, x_align: folder || list ? Clutter.ActorAlign.FILL : Clutter.ActorAlign.CENTER,
            y_align: list ? Clutter.ActorAlign.CENTER : Clutter.ActorAlign.START});
        label.clutter_text.set_single_line_mode(Boolean(list));
        label.clutter_text.set_line_wrap(!list);
        label.clutter_text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);
        label.clutter_text.set_ellipsize(list ? Pango.EllipsizeMode.END : Pango.EllipsizeMode.NONE);
        content.add_child(label);
        if (folder) {
            label.add_style_class_name('desk-ux-folder-title');
            const detail = box(false);
            detail.add_child(new St.Label({text: _('Applications: %s').replace('%s', members.length.toLocaleString()),
                style_class: 'desk-ux-caption', x_expand: true}));
            detail.add_child(new St.Icon({icon_name: 'go-next-symbolic', icon_size: 14}));
            content.add_child(detail);
        }
        if (list) {
            label.x_expand = true;
            const description = new St.Label({text: app.get_app_info()?.get_description() ?? '',
                style_class: 'desk-ux-caption', y_align: Clutter.ActorAlign.CENTER});
            description.clutter_text.ellipsize = Pango.EllipsizeMode.END;
            content.add_child(description);
        }
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
        if (app && !owner.selecting) {
            this._draggable = DND.makeDraggable(this, {restoreOnSuccess: true});
            const drags = [];
            this._draggable.connect('drag-begin', () => drags.push(owner.beginDrag()));
            this._draggable.connect('drag-end', () => owner.endDrag(drags.shift() ?? null));
            this.connect('destroy', () => {
                for (const drag of drags)
                    owner.endDrag(drag);
            });
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
        this._query = '';
        this._draftName = '';
        this._listMode = false;
        this._descending = false;
        this._columns = 5;
        this._folderColumns = 4;
        this._layoutWidth = 700;
        this._navigationSerial = 0;
        this._recents = new SessionRecents();
        this._privacy = new Gio.Settings({schema_id: 'org.gnome.desktop.privacy'});
        this._appSystem = Shell.AppSystem.get_default();
        this._parental = ParentalControlsManager.getDefault();
        this._pins = new MenuPins(() => this.queueRender());
        this._folderColors = new FolderColors(() => this.queueRender());
        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this._store = new AppFolders(() => this.queueRender(), () => this._appRecords(false));
        this._scroll = new ScrollView({x_expand: true, y_expand: true});
        this._scrollbars = this._scroll.get_children().filter(child => child instanceof St.ScrollBar);
        for (const scrollbar of this._scrollbars) {
            scrollbar.set({opacity: 0, track_hover: true});
            scrollbar.connect('captured-event', (_actor, event) => {
                const type = event.type();
                if ((type === Clutter.EventType.BUTTON_PRESS || type === Clutter.EventType.BUTTON_RELEASE) &&
                    event.get_button() === Clutter.BUTTON_PRIMARY) {
                    this._scrollbarPressed = type === Clutter.EventType.BUTTON_PRESS;
                    this.notePointerMotion();
                }
                return Clutter.EVENT_PROPAGATE;
            });
            scrollbar.connect('scroll-start', () => {
                this._scrollbarDragging = true;
                this.notePointerMotion();
            });
            scrollbar.connect('scroll-stop', () => {
                this._scrollbarDragging = false;
                this._scrollbarPressed = false;
                this.notePointerMotion();
            });
        }
        this._content = box(true, 'desk-ux-content');
        this._scroll.set_child(this._content);
        this._scroll.connect('captured-event', (_actor, event) => {
            if (event.type() !== Clutter.EventType.SCROLL)
                return Clutter.EVENT_PROPAGATE;
            const direction = event.get_scroll_direction();
            const delta = direction === Clutter.ScrollDirection.SMOOTH ? event.get_scroll_delta()[1]
                : direction === Clutter.ScrollDirection.UP ? -1
                : direction === Clutter.ScrollDirection.DOWN ? 1 : 0;
            this._pulseScrollEdge(scrollEdge(delta, this._scroll.vadjustment));
            return Clutter.EVENT_PROPAGATE;
        });
        this._toolbar = box(true, 'desk-ux-toolbar');
        this._footer = box(false, 'desk-ux-footer');
        this.add_child(this._toolbar);
        this.add_child(this._scroll);
        this.add_child(this._footer);
        this._appSystem.connectObject('installed-changed', () => this.queueRender(), this);
        this._appSystem.connectObject('app-state-changed', (_system, app) => {
            if (app.state === Shell.AppState.RUNNING)
                this._remember(app);
        }, this);
        this._privacy.connectObject('changed::remember-app-usage', () => {
            if (!this._privacy.get_boolean('remember-app-usage'))
                this._recents.clear();
            this.queueRender();
        }, this);
        this._parental.connectObject('app-filter-changed', () => this.queueRender(), this);
        this.connect('notify::mapped', () => {
            if (this.mapped) {
                const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
                this._scroll.update_fade_effect(new Clutter.Margin({top: 12 * scale, bottom: 12 * scale}));
                this.queueRender();
            } else {
                this.endDrag();
                this._cancelNavigation();
                this._resetScrollbarVisibility();
                this._resetScrollFeedback();
                this.closeMenus();
            }
        });
        this.connect('destroy', () => {
            this._destroyed = true;
            this._cancelNavigation();
            this._resetScrollbarVisibility();
            this._resetScrollFeedback();
            this.endDrag();
            if (this._idle)
                GLib.source_remove(this._idle);
            this._idle = 0;
            this._store.destroy();
            this._pins.destroy();
            this._folderColors.destroy();
            this._privacy.disconnectObject(this);
            this._privacy.run_dispose?.();
            this._privacy = null;
        });
    }

    setLayoutWidth(width) {
        // Use the parent's logical width, never child allocation feedback.
        if (width > 0 && width !== this._layoutWidth) {
            this._layoutWidth = width;
            this._columns = gridColumns(width - 64);
            // Folder rows have no nested pinned-section inset.
            this._folderColumns = gridColumns(width - 40, true);
            this.queueRender();
        }
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
        if (this._destroyed || this._dragging || this._idle || this._navigationFading)
            return;
        this._idle = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._idle = 0;
            this._render();
            return GLib.SOURCE_REMOVE;
        });
    }

    navigate(view = null, selected = [], animate = true) {
        const settings = St.Settings.get();
        animate = animate && view !== this.view && this.mapped && !this._dragging &&
            !this._destroyed && settings.enable_animations &&
            !('reduced_motion' in settings && settings.reduced_motion);
        this._cancelNavigation();
        this.closeMenus();
        this.view = view;
        this._selected = new Set(selected);
        this._query = '';
        this._draftName = '';
        this._renaming = false;
        this._choosingColor = false;
        this._resetScrollOnRender = true;
        this._focusOnRender = view !== null;
        if (!animate) {
            this.queueRender();
            return;
        }
        this._navigationFading = true;
        const serial = this._navigationSerial;
        this.ease({opacity: 0, duration: 60, mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                if (serial !== this._navigationSerial || this._destroyed || !this.mapped)
                    return;
                this._navigationFading = false;
                this._render();
                this.ease({opacity: 255, duration: 110, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
            }});
    }

    _cancelNavigation() {
        this._navigationSerial++;
        this._navigationFading = false;
        this.remove_transition('opacity');
        this.opacity = 255;
    }

    reset() {
        this.navigate(null, [], false);
    }

    back() {
        if (this.view === null)
            return false;
        const destination = this.view === '@add' ? this._targetFolder : null;
        this.navigate(destination);
        return true;
    }

    closeMenus() {
        for (const tile of this._tiles ?? [])
            tile.menu?.close();
    }

    get hasNameEntry() {
        return Boolean(this._nameEntry || this._filterEntry);
    }

    get selecting() {
        return ['@create', '@add', '@pin'].includes(this.view);
    }

    focusFilter(event) {
        if (!this._filterEntry)
            return;
        this._filterEntry.grab_key_focus();
        this._filterEntry.clutter_text.event(event, false);
    }

    get listMode() {
        return this._listMode && !this.selecting && this.view !== null && this.view !== '@move';
    }

    _remember(app) {
        if (!this._privacy.get_boolean('remember-app-usage'))
            return;
        this._recents.remember(app.get_id());
        if (this.view === '@recent')
            this.queueRender();
    }

    _heading(title, action = null, parent = this._content) {
        const row = box(false, 'desk-ux-heading');
        row.add_child(new St.Label({text: title, x_expand: true, y_align: Clutter.ActorAlign.CENTER}));
        if (action)
            row.add_child(action);
        parent.add_child(row);
        return row;
    }

    _grid(items, folders = false, parent = this._content) {
        const compact = !folders && !this.listMode;
        const columns = folders ? this._folderColumns : this.listMode ? 1 : this._columns;
        const grid = new Grid(columns, 10, 10);
        grid._tileWidth = tileWidth(this._layoutWidth, columns, folders ? 28 : compact ? 18 : 26,
            folders ? 124 : compact ? 94 : Infinity, folders ? 40 : 64);
        grid._tileStyle = `width: ${grid._tileWidth}px;`;
        if (folders || compact)
            grid._tileStyle += ` height: ${grid._tileWidth}px;`;
        if (compact)
            grid.add_style_class_name('desk-ux-compact-grid');
        grid.add_style_class_name('desk-ux-grid');
        for (const item of items) {
            const tile = new Tile(this, item);
            tile.set_style(grid._tileStyle);
            if (this.selecting && this._selected.has(item.app.get_id()))
                tile.checked = true;
            this._tiles.push(tile);
            tile.connect('key-focus-in', () => {
                const top = tile.get_transformed_position()[1];
                const bottom = top + tile.height;
                const scrollTop = this._scroll.get_transformed_position()[1];
                const adjustment = this._scroll.vadjustment;
                if (top < scrollTop)
                    adjustment.value -= scrollTop - top;
                else if (bottom > scrollTop + this._scroll.height)
                    adjustment.value += bottom - scrollTop - this._scroll.height;
            });
            grid.add_item(tile);
        }
        parent.add_child(grid);
        return grid;
    }

    _dropArea(actor, kind) {
        actor._delegate = {
            handleDragOver: source => this.dragOver({kind, actor}, source),
            acceptDrop: source => this.drop({kind, actor}, source),
        };
    }

    notePointerMotion() {
        if (!this.mapped || this._destroyed)
            return;
        this._fadeScrollbars(true);
        if (this._scrollbarHideId)
            GLib.source_remove(this._scrollbarHideId);
        this._scrollbarHideId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
            if (this._scrollbarDragging || (this._scrollbarPressed &&
                (global.get_pointer()[2] & Clutter.ModifierType.BUTTON1_MASK)))
                return GLib.SOURCE_CONTINUE;
            // Release may occur outside the menu while a native gesture owns input.
            this._scrollbarPressed = false;
            const focus = global.stage.key_focus;
            if (this._scrollbars.some(bar => bar.hover || (focus && bar.contains(focus))))
                return GLib.SOURCE_CONTINUE;
            this._scrollbarHideId = 0;
            this._fadeScrollbars(false);
            return GLib.SOURCE_REMOVE;
        });
    }

    _fadeScrollbars(visible) {
        if (this._scrollbarsVisible === visible)
            return;
        this._scrollbarsVisible = visible;
        const settings = St.Settings.get();
        const animate = settings.enable_animations &&
            !('reduced_motion' in settings && settings.reduced_motion);
        for (const scrollbar of this._scrollbars) {
            scrollbar.remove_transition('opacity');
            scrollbar.ease({opacity: visible ? 255 : 0, duration: animate ? (visible ? 120 : 2000) : 0,
                mode: visible ? Clutter.AnimationMode.EASE_OUT_QUAD : Clutter.AnimationMode.EASE_IN_OUT_QUAD});
        }
    }

    _resetScrollbarVisibility() {
        if (this._scrollbarHideId)
            GLib.source_remove(this._scrollbarHideId);
        this._scrollbarHideId = 0;
        this._scrollbarPressed = false;
        this._scrollbarDragging = false;
        this._scrollbarsVisible = false;
        for (const scrollbar of this._scrollbars) {
            scrollbar.remove_transition('opacity');
            scrollbar.opacity = 0;
        }
    }

    _resetScrollFeedback() {
        this._content.remove_transition('translation-y');
        this._content.translation_y = 0;
        this._edgeAnimating = false;
    }

    _pulseScrollEdge(edge) {
        const settings = St.Settings.get();
        if (!edge || this._edgeAnimating || !this.mapped || this._dragging ||
            !settings.enable_animations || ('reduced_motion' in settings && settings.reduced_motion))
            return;
        this._edgeAnimating = true;
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        this._content.ease({translation_y: edge * 4 * scale, duration: 80,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => {
                if (this._destroyed || !this.mapped)
                    return;
                this._content.ease({translation_y: 0, duration: 160,
                    mode: Clutter.AnimationMode.EASE_OUT_QUAD,
                    onComplete: () => { this._edgeAnimating = false; }});
            }});
    }

    _render() {
        if (this._dragging || !this.mapped || this._navigationFading)
            return;
        if (this._resetScrollOnRender) {
            this._scroll.resetScroll();
            this._resetScrollOnRender = false;
        }
        this._resetScrollFeedback();
        const nameFocused = this._nameEntry?.clutter_text.has_key_focus();
        const filterFocused = this._filterEntry?.clutter_text.has_key_focus();
        const colorFocused = this._colorButtons?.find(actor => actor.has_key_focus())?.colorKey;
        const cursor = nameFocused ? this._nameEntry.clutter_text.cursor_position
            : this._filterEntry?.clutter_text.cursor_position;
        const folders = this._store.snapshot();
        const special = ['@all', '@recent', '@categories', '@create', '@pin', '@add', '@move'];
        const current = folders.find(folder => folder.id === this.view);
        if (this.view && !special.includes(this.view) && !current)
            this.view = null;
        if (this.view === '@add' && !folders.some(folder => folder.id === this._targetFolder))
            this.view = null;
        this.emit('name-entry-changed', this.view !== null);
        if (global.stage.key_focus && this._toolbar.contains(global.stage.key_focus))
            global.stage.set_key_focus(null);
        this._toolbar.destroy_all_children();
        this._colorButtons = [];
        this._footer.destroy_all_children();
        this._nameEntry = null;
        this._filterEntry = null;
        this._saveButton = null;
        this._selectionCount = null;
        this._toolbar.visible = this.view !== null;
        this._footer.visible = this.selecting || this.view === '@move';
        if (this.view !== null) {
            const title = current ? this.folderName(current)
                : this.view === '@create' ? _('New Folder')
                : this.view === '@move' ? _('Move to Folder')
                : this.selecting ? _('Add Applications')
                : this.view === '@recent' ? _('Recent Applications')
                : this.view === '@categories' ? _('Folders') : _('All Apps');
            const heading = this._heading(title, null, this._toolbar);
            if (current) {
                const colorButton = new St.Button({can_focus: true,
                    accessible_name: themeText('Accent color'),
                    style_class: 'button desk-ux-action desk-ux-color-action',
                    child: new St.Icon({icon_name: 'color-select-symbolic', icon_size: 16})});
                colorButton.connect('clicked', () => {
                    this._choosingColor = !this._choosingColor;
                    this.queueRender();
                });
                heading.add_child(colorButton);
                heading.add_child(button(_('Rename'), () => {
                    this._renaming = !this._renaming;
                    this._draftName = this.folderName(current);
                    this.queueRender();
                }));
                heading.add_child(button(_('Add Applications'), () => {
                    this._targetFolder = current.id;
                    this.navigate('@add');
                }));
            }
            if (this.view === '@create' || this._renaming) {
                this._nameEntry = new St.Entry({text: this._draftName,
                    hint_text: _('Folder Name'), accessible_name: _('Folder Name'),
                    can_focus: true, x_expand: true, style_class: 'desk-ux-entry'});
                this._toolbar.add_child(this._nameEntry);
                this._nameEntry.clutter_text.connect('text-changed', () => {
                    this._draftName = this._nameEntry.get_text();
                    this._updateSave();
                });
                this._nameEntry.clutter_text.connect('activate', () => {
                    if (this._saveButton?.reactive)
                        this._save();
                });
                if (this._renaming) {
                    this._saveButton = button(_('Rename'), () => this._save());
                    heading.add_child(this._saveButton);
                }
            }
            heading.add_child(button(_('Back'), () => this.back()));
            if (current && this._choosingColor)
                this._colorPicker(current);
            if (['@all', '@recent', '@categories'].includes(this.view)) {
                const tabs = box(false, 'desk-ux-tabs');
                for (const [view, label] of [['@recent', _('Recent Applications')],
                    ['@all', _('All Apps')], ['@categories', _('Folders')]]) {
                    const tab = button(label, () => this.navigate(view));
                    if (this.view === view)
                        tab.add_style_pseudo_class('checked');
                    tabs.add_child(tab);
                }
                this._toolbar.add_child(tabs);
            }
            const controls = box(false, 'desk-ux-controls');
            this._filterEntry = new St.Entry({text: this._query, hint_text: _('Type to search'),
                accessible_name: _('Type to search'), can_focus: true, x_expand: true,
                style_class: 'desk-ux-entry'});
            controls.add_child(this._filterEntry);
            this._filterEntry.clutter_text.connect('text-changed', () => {
                this._query = this._filterEntry.get_text();
                this._scroll.resetScroll();
                this._renderBody();
            });
            if (!this.selecting && !['@move', '@categories'].includes(this.view)) {
                controls.add_child(button(this._listMode ? _('Grid') : _('List'), () => {
                    this._listMode = !this._listMode;
                    this.queueRender();
                }));
                if (this.view !== '@recent')
                    controls.add_child(button(this._descending ? 'Z–A' : 'A–Z', () => {
                        this._descending = !this._descending;
                        this.queueRender();
                    }));
            }
            if (this.view === '@recent')
                controls.add_child(button(_('Clear'), () => {
                    this._recents.clear();
                    this._renderBody();
                }));
            this._toolbar.add_child(controls);
        }
        if (this.selecting) {
            this._selectionCount = new St.Label({x_expand: true,
                y_align: Clutter.ActorAlign.CENTER, style_class: 'desk-ux-selection-count'});
            this._footer.add_child(this._selectionCount);
            this._saveButton = button(this.view === '@create' ? _('Create Folder') : _('Add Applications'),
                () => this._save());
            this._saveButton.add_style_class_name('suggested-action');
            this._footer.add_child(this._saveButton);
        } else if (this.view === '@move') {
            this._footer.add_child(button(_('Move outside folders'), () => {
                if (this.perform({type: 'ungroup', apps: [...this._selected]}))
                    this.navigate();
            }));
        }
        this._renderBody();
        this._updateSave();
        if (nameFocused && this._nameEntry) {
            this._nameEntry.grab_key_focus();
            this._nameEntry.clutter_text.cursor_position = cursor;
        } else if (filterFocused && this._filterEntry) {
            this._filterEntry.grab_key_focus();
            this._filterEntry.clutter_text.cursor_position = cursor;
        } else if (colorFocused) {
            this._colorButtons.find(actor => actor.colorKey === colorFocused)?.grab_key_focus();
        }
    }

    _colorPicker(folder) {
        const selected = this._folderColors.get(folder.id);
        const reset = button(themeText('Default'), () => this._folderColors.set(folder.id, null));
        reset.colorKey = 'default';
        this._colorButtons.push(reset);
        if (!selected)
            reset.add_style_pseudo_class('checked');
        reset.reactive = reset.can_focus = this._folderColors.writable;
        this._heading(themeText('Accent color'), reset, this._toolbar);
        const columns = Math.max(1, Math.min(FOLDER_COLORS.length, Math.floor((this._layoutWidth - 48) / 38)));
        const colors = new Grid(columns, 6, 6);
        colors.add_style_class_name('desk-ux-color-picker');
        for (const [color, hex, label] of FOLDER_COLORS) {
            const swatch = new St.Button({can_focus: this._folderColors.writable,
                reactive: this._folderColors.writable, toggle_mode: true, checked: color === selected,
                accessible_name: themeText(label), style_class: 'desk-ux-color-swatch',
                style: `background-color: ${hex};`,
                child: new St.Icon({icon_name: 'object-select-symbolic', icon_size: 16,
                    opacity: color === selected ? 255 : 0})});
            swatch.connect('clicked', () => {
                // Restore the saved choice even if the backend rejects the write.
                this._folderColors.set(folder.id, color);
                this.queueRender();
            });
            swatch.colorKey = color;
            this._colorButtons.push(swatch);
            colors.add_item(swatch);
        }
        this._toolbar.add_child(colors);
    }

    _actionTile(label, action, parent) {
        const tile = new St.Button({can_focus: true, style_class: 'desk-ux-tile desk-ux-add'});
        const list = this.listMode;
        if (list)
            tile.add_style_class_name('desk-ux-list-tile');
        tile.set_style(parent._tileStyle);
        const content = box(!list, 'desk-ux-tile-content');
        content.add_child(new St.Bin({style_class: 'desk-ux-icon-slot', x_expand: !list,
            child: new St.Icon({icon_name: 'list-add-symbolic', icon_size: list ? 36 : 40})}));
        const title = new St.Label({text: label, x_expand: Boolean(list),
            y_align: list ? Clutter.ActorAlign.CENTER : Clutter.ActorAlign.START});
        title.clutter_text.set_single_line_mode(Boolean(list));
        title.clutter_text.set_line_wrap(!list);
        title.clutter_text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);
        title.clutter_text.set_ellipsize(list ? Pango.EllipsizeMode.END : Pango.EllipsizeMode.NONE);
        content.add_child(title);
        tile.set_child(content);
        tile.connect('clicked', action);
        parent.add_item(tile);
    }

    _renderBody() {
        if (this._dragging)
            return;
        this.closeMenus();
        const focused = this._tiles?.find(tile => tile.has_key_focus());
        const focusId = focused?.app?.get_id() ?? focused?.folder?.id;
        const restoreFocus = this._focusOnRender || Boolean(focused);
        this._focusOnRender = false;
        if (global.stage.key_focus && this._content.contains(global.stage.key_focus))
            global.stage.set_key_focus(null);
        this._content.destroy_all_children();
        this._tiles = [];
        const apps = this._appRecords();
        const ids = new Set(apps.map(app => app.id));
        this._selected = new Set([...this._selected].filter(id => ids.has(id)));
        const folders = this._store.snapshot();
        const current = folders.find(folder => folder.id === this.view);
        const visibleFolders = folders.map(folder => ({folder, members: folderMembers(folder, apps)}))
            .filter(item => item.members.length && matchesQuery(this.folderName(item.folder), this._query));
        if (this.view === null) {
            const section = box(true, 'desk-ux-section');
            this._content.add_child(section);
            const heading = this._heading(_('Pinned Applications'),
                button(_('All Apps'), () => this.navigate('@all')), section);
            this._dropArea(heading, 'pin');
            const favorites = this._pins.ids().filter(id => ids.has(id))
                .map(id => this._appSystem.lookup_app(id));
            const pinned = this._grid(favorites.map(app => ({app, favorite: true})), false, section);
            this._actionTile(_('Add Applications'), () => this.navigate('@pin'), pinned);
            this._dropArea(pinned, 'pin');
            const folderSection = box(true, 'desk-ux-section');
            this._content.add_child(folderSection);
            this._heading(_('Folders'),
                button(_('New Folder'), () => this.navigate('@create')), folderSection);
            this._grid(visibleFolders, true, folderSection);
            const ungrouped = apps.filter(app => !folders.some(folder => containsApp(folder, app)) &&
                !this._pins.has(app.id));
            if (ungrouped.length) {
                this._dropArea(this._heading(_('Other Applications')), 'ungroup');
                this._dropArea(this._grid(ungrouped.map(record => ({app: record.app}))), 'ungroup');
            }
        } else if (this.view === '@move' || this.view === '@categories') {
            this._grid(visibleFolders, true);
            if (!visibleFolders.length)
                this._heading(_('No Results'));
        } else {
            let records = current ? folderMembers(current, apps) : apps;
            if (this.view === '@all' && !this._query) {
                const recent = this._recents.visible(apps).slice(0, this._columns);
                if (recent.length) {
                    this._heading(_('Recent Applications'), button(_('Clear'), () => {
                        this._recents.clear();
                        this._renderBody();
                    }));
                    this._grid(recent.map(record => ({app: record.app})));
                    this._heading(_('All Apps'));
                }
            }
            if (this.view === '@recent')
                records = this._recents.visible(apps);
            if (this.view === '@pin')
                records = apps.filter(app => !this._pins.has(app.id));
            if (this.view === '@add') {
                const target = folders.find(folder => folder.id === this._targetFolder);
                records = target ? apps.filter(app => !containsApp(target, app)) : [];
            }
            records = records.filter(app => matchesQuery(app.name, this._query));
            if (this._descending && this.view !== '@recent')
                records.reverse();
            if (this.view === '@create')
                this._heading(_('Select at least two applications'));
            const grid = this._grid(records.map(record => ({app: record.app})));
            if (current)
                this._actionTile(_('Add Applications'), () => {
                    this._targetFolder = current.id;
                    this.navigate('@add');
                }, grid);
            if (!records.length)
                this._heading(_('No Results'));
        }
        this._updateSave();
        if (restoreFocus && this.mapped)
            (this._tiles.find(tile => (tile.app?.get_id() ?? tile.folder?.id) === focusId) ?? this._tiles[0])?.grab_key_focus();
        this._suppressActivation = false;
    }

    _save() {
        if (!this._saveButton?.reactive)
            return;
        const apps = [...this._selected];
        if (this.view === '@pin') {
            if (this._pins.add(apps))
                this.navigate();
        } else if (this.view === '@add') {
            if (this.perform({type: 'move', folder: this._targetFolder, apps}))
                this.navigate(this._targetFolder);
        } else {
            const name = this._nameEntry.get_text();
            const id = this.perform(this.view === '@create'
                ? {type: 'create', apps, name}
                : {type: 'rename', folder: this.view, name});
            if (id)
                this.navigate(id);
        }
    }

    _updateSave() {
        if (!this._saveButton)
            return;
        const name = this._nameEntry?.get_text().trim() ?? 'unused';
        const enabled = name.length > 0 && name.length <= 120 &&
            (this.view !== '@create' || this._selected.size >= 2) &&
            (!['@pin', '@add'].includes(this.view) || this._selected.size > 0) &&
            (this.view !== '@pin' || this._pins.writable);
        if (this._selectionCount)
            this._selectionCount.text = this.view === '@create'
                ? `${this._selected.size.toLocaleString()} / ${(2).toLocaleString()}`
                : _('Selected: %s').replace('%s', this._selected.size.toLocaleString());
        this._saveButton.reactive = enabled;
        this._saveButton.can_focus = enabled;
    }

    activateTile(tile) {
        if (this._dragging || this._suppressActivation || this._navigationFading)
            return;
        if (tile.folder) {
            if (this.view !== '@move' || this.perform({type: 'move', folder: tile.folder.id, apps: [...this._selected]}))
                this.navigate(tile.folder.id);
        } else if (this.selecting) {
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
            this._remember(tile.app);
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
        if (this._dragging || this.selecting || this.view === '@move')
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
            menu.addAction(themeText('Accent color'), () => {
                this.navigate(tile.folder.id);
                this._choosingColor = true;
            });
            menu.addAction(_('Rename'), () => {
                this.navigate(tile.folder.id);
                this._renaming = true;
                this._draftName = this.folderName(tile.folder);
            });
            menu.addAction(_('Dissolve Folder'), () => this.perform({type: 'dissolve', folder: tile.folder.id}));
        } else {
            const id = tile.app.get_id();
            menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
            menu.addAction(_('Move to Folder'), () => this.navigate('@move', [id]));
            menu.addAction(_('New Folder'), () => this.navigate('@create', [id]));
            menu.addAction(_('Move outside folders'), () => this.perform({type: 'ungroup', apps: [id]}));
        }
        menu.open();
    }

    beginDrag() {
        this.endDrag(this._drag, false);
        if (this._destroyed)
            return null;
        if (this._idle) {
            GLib.source_remove(this._idle);
            this._idle = 0;
        }
        const drag = {};
        this._drag = drag;
        this._cancelNavigation();
        this._resetScrollFeedback();
        this.closeMenus();
        this._dragging = true;
        this._suppressActivation = true;
        this._monitor = {dragMotion: event => {
            if (this._drag !== drag)
                return DND.DragMotionResult.CONTINUE;
            this._dragPoint = [event.x, event.y];
            this._highlight?.remove_style_pseudo_class('drop');
            this._highlight = null;
            return DND.DragMotionResult.CONTINUE;
        }};
        DND.addDragMonitor(this._monitor);
        this._scrollTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, () => {
            if (this._drag !== drag)
                return GLib.SOURCE_REMOVE;
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
        return drag;
    }

    endDrag(drag = this._drag, render = true) {
        if (!drag || this._drag !== drag)
            return;
        this._drag = null;
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
        if (render)
            this.queueRender();
    }

    _canDrop(target, source) {
        return !this._navigationFading && !this.selecting && this.view !== '@move' && source?.owner === this && source.app && source !== target &&
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
            return this._pins.move(id, target.app?.get_id() ?? null);
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
