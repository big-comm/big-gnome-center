// SPDX-License-Identifier: GPL-2.0-or-later

// Bound records received from external launcher publishers.
export const MAX_REMOTE_ENTRIES = 512;

export function parseLauncherUpdate(sender, uri, properties) {
    if (typeof sender !== 'string' || !/^:\d+\.\d+$/.test(sender) ||
        typeof uri !== 'string' || !uri.startsWith('application://') ||
        !properties || typeof properties !== 'object' || Array.isArray(properties))
        return null;
    const appId = uri.slice('application://'.length);
    if (appId.length > 255 || !/^[^/\\\s\x00-\x1f]+\.desktop$/.test(appId))
        return null;
    const updates = Object.create(null);
    for (const name of ['count', 'count-visible', 'progress', 'progress-visible',
        'urgent', 'updating', 'quicklist']) {
        if (!Object.hasOwn(properties, name))
            continue;
        let value;
        try { value = properties[name].unpack(); } catch { continue; }
        const valid = name === 'count' ? Number.isSafeInteger(value) && value >= 0
            : name === 'progress' ? Number.isFinite(value) && value >= 0 && value <= 1
            : name === 'quicklist' ? typeof value === 'string' && value.length <= 1024 &&
                /^\/(?:[A-Za-z0-9_]+(?:\/[A-Za-z0-9_]+)*)?$/.test(value)
            : typeof value === 'boolean';
        if (valid)
            updates[name] = value;
    }
    return Object.keys(updates).length ? {appId, updates} : null;
}
