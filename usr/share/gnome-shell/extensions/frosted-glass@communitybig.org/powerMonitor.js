// SPDX-License-Identifier: GPL-3.0-or-later

import Gio from 'gi://Gio';

const SERVICES = [
    [
        Gio.BusType.SYSTEM,
        'org.freedesktop.UPower',
        '/org/freedesktop/UPower',
        'org.freedesktop.UPower',
    ],
    [
        Gio.BusType.SYSTEM,
        'net.hadess.PowerProfiles',
        '/net/hadess/PowerProfiles',
        'net.hadess.PowerProfiles',
    ],
];

export class PowerMonitor {
    constructor(onChanged) {
        this._onChanged = onChanged;
        this._proxies = [];
        this._connections = [];
        this._createProxies();
    }

    get isSavingPower() {
        const upower = this._proxies.find(proxy =>
            proxy.get_interface_name() === 'org.freedesktop.UPower');
        const profiles = this._proxies.find(proxy =>
            proxy.get_interface_name() === 'net.hadess.PowerProfiles');
        const onBattery = upower?.get_cached_property('OnBattery')?.unpack() ?? false;
        const profile = profiles?.get_cached_property('ActiveProfile')?.unpack() ?? '';
        return onBattery || profile === 'power-saver';
    }

    destroy() {
        for (const [proxy, id] of this._connections.splice(0)) {
            try {
                proxy.disconnect(id);
            } catch (error) {
                // Proxy may already be disposed.
            }
        }
        this._proxies = [];
    }

    _createProxies() {
        for (const [busType, name, path, iface] of SERVICES) {
            try {
                const proxy = Gio.DBusProxy.new_for_bus_sync(
                    busType,
                    Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                    null,
                    name,
                    path,
                    iface,
                    null
                );
                this._proxies.push(proxy);
                const id = proxy.connect('g-properties-changed', () => this._onChanged());
                this._connections.push([proxy, id]);
            } catch (error) {
                console.debug(`Frosted Glass: power service unavailable: ${iface}`);
            }
        }
    }
}
