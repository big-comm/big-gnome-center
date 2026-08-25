// SPDX-License-Identifier: GPL-2.0-or-later

import {DockedDash} from './dockSurface.js';

export class DockActorFactory {
    create(params) {
        return new DockedDash(params);
    }
}
