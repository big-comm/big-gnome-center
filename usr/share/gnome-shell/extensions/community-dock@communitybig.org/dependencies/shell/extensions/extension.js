import Gettext from 'gettext';
import * as ShellExtension from 'resource:///org/gnome/shell/extensions/extension.js';

const translations = Gettext.domain('dashtodock');

export const Extension = Object.freeze({
    ...ShellExtension,
    gettext: translations.gettext,
    ngettext: translations.ngettext,
});
