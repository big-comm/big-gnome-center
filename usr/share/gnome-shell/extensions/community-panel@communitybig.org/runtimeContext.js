/*
 * SPDX-License-Identifier: GPL-2.0-or-later
 * Compatibility context for the inherited Taskbar/Panel modules.
 */

import Gio from 'gi://Gio'
import Shell from 'gi://Shell'

export let DTP_EXTENSION = null
export let SETTINGS = null
export let DESKTOPSETTINGS = null
export let TERMINALSETTINGS = null
export let NOTIFICATIONSSETTINGS = null
export let PERSISTENTSTORAGE = null
export let EXTENSION_PATH = null
export let tracker = null

export function initializeRuntimeContext(extension, owner) {
  if (SETTINGS) throw new Error('Taskbar runtime context is already active')

  DTP_EXTENSION = owner
  SETTINGS = extension.getSettings(
    'org.gnome.shell.extensions.dash-to-panel',
  )
  DESKTOPSETTINGS = new Gio.Settings({
    schema_id: 'org.gnome.desktop.interface',
  })
  TERMINALSETTINGS = new Gio.Settings({
    schema_id: 'org.gnome.desktop.default-applications.terminal',
  })
  NOTIFICATIONSSETTINGS = new Gio.Settings({
    schema_id: 'org.gnome.desktop.notifications',
  })
  EXTENSION_PATH = extension.path
  tracker = Shell.WindowTracker.get_default()
  PERSISTENTSTORAGE ??= {}
}

export function clearRuntimeContext(owner) {
  if (DTP_EXTENSION !== owner) return

  DTP_EXTENSION = null
  SETTINGS = null
  DESKTOPSETTINGS = null
  TERMINALSETTINGS = null
  NOTIFICATIONSSETTINGS = null
  EXTENSION_PATH = null
  tracker = null
}
