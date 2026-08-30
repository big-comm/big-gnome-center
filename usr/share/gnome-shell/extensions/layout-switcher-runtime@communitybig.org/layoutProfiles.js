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
        extended: false,
        labels: false,
        indicator: 'desk-ux',
        hover: 'default',
        magnificationIntensity: 40,
        dockOpacity: 77,
        dockSize: 39,
        visibility: 'intelligent',
        menuSide: 'right',
        skipStartupOverview: false,
    })],
    ['G-Unity', Object.freeze({
        layout: 'G-Unity',
        surface: RuntimeSurface.DOCK,
        edge: 'left',
        extended: true,
        labels: false,
        indicator: 'dot',
        hover: 'default',
        magnificationIntensity: 40,
        dockOpacity: 70,
        dockSize: 39,
        visibility: 'always-visible',
        skipStartupOverview: false,
    })],
    ['Hybrid', Object.freeze({
        layout: 'Hybrid',
        surface: RuntimeSurface.TASKBAR,
        edge: 'bottom',
        labels: false,
        indicator: 'hybrid',
        hover: 'lift',
        panelOpacity: 70,
        panelVisibility: 'always-visible',
        panelHeight: 38,
        actorHeight: 38,
        skipStartupOverview: true,
    })],
    ['Desk UX', Object.freeze({
        layout: 'Desk UX',
        surface: RuntimeSurface.TASKBAR,
        edge: 'bottom',
        labels: false,
        indicator: 'desk-ux',
        hover: 'default',
        panelOpacity: 65,
        panelVisibility: 'always-visible',
        panelHeight: 40,
        actorHeight: 46,
        skipStartupOverview: true,
    })],
    ['Classic', Object.freeze({
        layout: 'Classic',
        surface: RuntimeSurface.TASKBAR,
        edge: 'bottom',
        labels: true,
        indicator: 'none',
        hover: 'default',
        panelOpacity: 70,
        panelVisibility: 'always-visible',
        panelHeight: 38,
        actorHeight: 38,
        skipStartupOverview: true,
    })],
    ['Minimal', Object.freeze({
        layout: 'Minimal',
        surface: RuntimeSurface.NATIVE,
        edge: 'top',
        labels: false,
        indicator: 'none',
        hover: 'default',
        skipStartupOverview: false,
    })],
]);

const SAFE_FALLBACK = LAYOUT_PROFILES.get('Minimal');

export function profileForLayout(layout) {
    return LAYOUT_PROFILES.get(layout) ?? SAFE_FALLBACK;
}

export function supportedLayouts() {
    return [...LAYOUT_PROFILES.keys()];
}
