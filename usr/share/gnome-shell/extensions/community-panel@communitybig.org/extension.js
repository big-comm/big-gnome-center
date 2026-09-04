/*
 * SPDX-License-Identifier: GPL-2.0-or-later
 * Rollback adapter for the Big Gnome Center-owned Taskbar/Panel lifecycle.
 */

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js'

import {TaskbarSurfaceManager} from '../layout-switcher-runtime@communitybig.org/taskbarSurface.js'

export {TaskbarSurfaceManager as CommunityPanelRuntime}

export default class CommunityPanelExtension extends Extension {
  async enable() {
    this._runtime = new TaskbarSurfaceManager(this)
    await this._runtime.enable()
  }

  disable() {
    this._runtime?.destroy()
    this._runtime = null
  }
}
