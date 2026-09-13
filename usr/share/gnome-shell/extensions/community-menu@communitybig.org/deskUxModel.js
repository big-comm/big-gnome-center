// SPDX-License-Identifier: GPL-2.0-or-later
export function matchesQuery(name, query) {
    const normalize = text => text.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase();
    return normalize(name).includes(normalize(query.trim()));
}

export function folderTint(id) {
    let hash = 0;
    for (const char of id)
        hash = (hash * 31 + char.codePointAt(0)) >>> 0;
    return hash % 6;
}

export function gridColumns(width, folders = false) {
    return Math.max(1, Math.min(folders ? 4 : 6, Math.floor((width + 10) / (folders ? 162 : 116))));
}

export function tileWidth(width, columns, inset = 26, maximum = Infinity, reserved = 64) {
    return Math.max(48, Math.min(maximum,
        Math.floor((width - reserved - (columns - 1) * 10) / columns - inset)));
}

export function scrollEdge(delta, {lower, upper, page_size, value}) {
    const end = upper - page_size;
    if (end <= lower)
        return 0;
    if (delta < 0 && value <= lower + 0.5)
        return 1;
    if (delta > 0 && value >= end - 0.5)
        return -1;
    return 0;
}

export class SessionRecents {
    constructor() { this.ids = []; }
    remember(id) {
        this.ids = [id, ...this.ids.filter(value => value !== id)].slice(0, 24);
    }
    clear() { this.ids = []; }
    visible(apps) {
        const byId = new Map(apps.map(app => [app.id, app]));
        return this.ids.map(id => byId.get(id)).filter(Boolean);
    }
}
