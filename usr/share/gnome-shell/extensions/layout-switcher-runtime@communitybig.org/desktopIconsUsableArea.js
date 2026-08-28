/*
 * The code in this file is distributed under a "1-clause BSD license",
 * which makes it compatible with GPLv2 and GPLv3 too, and others.
 *
 * Copyright (C) 2021 Sergio Costas (rastersoft@gmail.com)
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 * this list of conditions and the following disclaimer.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

import GLib from 'gi://GLib';

import * as ExtensionUtils from 'resource:///org/gnome/shell/misc/extensionUtils.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const DING_USABLE_AREA_UUID = '130cbc66-235c-4bd6-8571-98d2d8bba5e2';

export class DesktopIconsUsableAreaClass {
    constructor(owner) {
        const ownerUuid = typeof owner === 'string' ? owner : owner?.uuid;
        if (!ownerUuid)
            throw new Error('Desktop icon margins require an owner UUID');

        this._ownerUuid = ownerUuid;
        this._extensionManager = Main.extensionManager;
        this._timedMarginsId = 0;
        this._margins = {};
        this._dispatchCount = 0;
        this._recipientUuids = [];
        this._extensionManagerId = this._extensionManager.connect(
            'extension-state-changed',
            (_manager, extension) => {
                if (!extension)
                    return;

                if (this._isEnabled(extension)) {
                    if (this._sendMarginsToExtension(extension)) {
                        this._recipientUuids = [
                            ...new Set([
                                ...this._recipientUuids,
                                extension.uuid,
                            ]),
                        ];
                        this._dispatchCount++;
                    }
                    return;
                }

                this._changedMargins();
            },
        );
    }

    setMargins(monitor, top, bottom, left, right) {
        this._margins[monitor] = {top, bottom, left, right};
        this._changedMargins();
    }

    resetMargins() {
        this._margins = {};
        this._changedMargins();
    }

    destroy() {
        if (this._extensionManagerId) {
            this._extensionManager.disconnect(this._extensionManagerId);
            this._extensionManagerId = 0;
        }
        this._cancelDispatch();
        this._margins = null;
        this._changedMargins();
    }

    diagnostics() {
        return {
            implementation: 'layout-switcher-runtime',
            ownerUuid: this._ownerUuid,
            connected: Boolean(this._extensionManagerId),
            pending: Boolean(this._timedMarginsId),
            dispatchCount: this._dispatchCount,
            recipientUuids: this._recipientUuids,
        };
    }

    _isEnabled(extension) {
        return extension?.state === ExtensionUtils.ExtensionState.ENABLED ||
            extension?.state === ExtensionUtils.ExtensionState.ACTIVE;
    }

    _changedMargins() {
        this._cancelDispatch();
        this._timedMarginsId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            100,
            () => {
                this._timedMarginsId = 0;
                this._sendMarginsToAll();
                return GLib.SOURCE_REMOVE;
            },
        );
    }

    _cancelDispatch() {
        if (!this._timedMarginsId)
            return;
        GLib.Source.remove(this._timedMarginsId);
        this._timedMarginsId = 0;
    }

    _sendMarginsToAll() {
        const recipients = [];
        for (const uuid of this._extensionManager.getUuids()) {
            const extension = this._extensionManager.lookup(uuid);
            if (this._sendMarginsToExtension(extension))
                recipients.push(uuid);
        }
        this._recipientUuids = recipients;
        this._dispatchCount++;
    }

    _sendMarginsToExtension(extension) {
        if (!this._isEnabled(extension))
            return false;

        const usableArea = extension?.stateObj?.DesktopIconsUsableArea;
        if (usableArea?.uuid !== DING_USABLE_AREA_UUID)
            return false;

        usableArea.setMarginsForExtension(this._ownerUuid, this._margins);
        return true;
    }
}
