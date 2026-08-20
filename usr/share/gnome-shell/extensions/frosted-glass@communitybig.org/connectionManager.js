// SPDX-License-Identifier: GPL-3.0-or-later

export class ConnectionManager {
    constructor() {
        this._connections = [];
    }

    connect(object, signal, callback) {
        if (!object?.connect)
            return 0;

        try {
            const id = object.connect(signal, callback);
            this._connections.push([object, id]);
            return id;
        } catch (error) {
            console.debug(`Frosted Glass: cannot connect ${signal}: ${error}`);
            return 0;
        }
    }

    disconnectAll() {
        for (const [object, id] of this._connections.splice(0)) {
            try {
                object.disconnect(id);
            } catch (error) {
                // Actors may already be disposed.
            }
        }
    }
}
