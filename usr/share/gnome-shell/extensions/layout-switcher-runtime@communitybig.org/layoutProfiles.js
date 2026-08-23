// SPDX-License-Identifier: GPL-2.0-or-later

export const RuntimeSurface = Object.freeze({
    DOCK: 'dock',
    TASKBAR: 'taskbar',
    NATIVE: 'native',
});

const LAYOUT_PROFILES = new Map([
    ['BigGnome', Object.freeze({
        layout: 'BigGnome',
        surface: RuntimeSurface.DOCK,
        edge: 'bottom',
        labels: false,
        indicator: 'desk-ux',
    })],
    ['G-Unity', Object.freeze({
        layout: 'G-Unity',
        surface: RuntimeSurface.DOCK,
        edge: 'left',
        labels: false,
        indicator: 'dot',
    })],
    ['Hybrid', Object.freeze({
        layout: 'Hybrid',
        surface: RuntimeSurface.TASKBAR,
        edge: 'bottom',
        labels: false,
        indicator: 'hybrid',
    })],
    ['Desk UX', Object.freeze({
        layout: 'Desk UX',
        surface: RuntimeSurface.TASKBAR,
        edge: 'bottom',
        labels: false,
        indicator: 'desk-ux',
    })],
    ['Classic', Object.freeze({
        layout: 'Classic',
        surface: RuntimeSurface.TASKBAR,
        edge: 'bottom',
        labels: true,
        indicator: 'none',
    })],
    ['Minimal', Object.freeze({
        layout: 'Minimal',
        surface: RuntimeSurface.NATIVE,
        edge: 'top',
        labels: false,
        indicator: 'none',
    })],
]);

const SAFE_FALLBACK = LAYOUT_PROFILES.get('Minimal');

export function profileForLayout(layout) {
    return LAYOUT_PROFILES.get(layout) ?? SAFE_FALLBACK;
}

export function supportedLayouts() {
    return [...LAYOUT_PROFILES.keys()];
}
