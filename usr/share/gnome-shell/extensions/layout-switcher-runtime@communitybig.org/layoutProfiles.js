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
        hover: 'default',
        visibility: 'intelligent',
    })],
    ['G-Unity', Object.freeze({
        layout: 'G-Unity',
        surface: RuntimeSurface.DOCK,
        edge: 'left',
        labels: false,
        indicator: 'dot',
        hover: 'default',
        visibility: 'always-visible',
    })],
    ['Hybrid', Object.freeze({
        layout: 'Hybrid',
        surface: RuntimeSurface.TASKBAR,
        edge: 'bottom',
        labels: false,
        indicator: 'hybrid',
        hover: 'lift',
    })],
    ['Desk UX', Object.freeze({
        layout: 'Desk UX',
        surface: RuntimeSurface.TASKBAR,
        edge: 'bottom',
        labels: false,
        indicator: 'desk-ux',
        hover: 'default',
    })],
    ['Classic', Object.freeze({
        layout: 'Classic',
        surface: RuntimeSurface.TASKBAR,
        edge: 'bottom',
        labels: true,
        indicator: 'none',
        hover: 'default',
    })],
    ['Minimal', Object.freeze({
        layout: 'Minimal',
        surface: RuntimeSurface.NATIVE,
        edge: 'top',
        labels: false,
        indicator: 'none',
        hover: 'default',
    })],
]);

const SAFE_FALLBACK = LAYOUT_PROFILES.get('Minimal');

export function profileForLayout(layout) {
    return LAYOUT_PROFILES.get(layout) ?? SAFE_FALLBACK;
}

export function supportedLayouts() {
    return [...LAYOUT_PROFILES.keys()];
}
