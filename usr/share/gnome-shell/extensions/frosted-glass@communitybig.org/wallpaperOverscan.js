// SPDX-License-Identifier: GPL-3.0-or-later
// Keep a blurred wallpaper copy from being cached empty.
//
// Shell.BlurEffect in actor mode renders its actor offscreen once and reuses
// that copy on every stage view. Mutter clips a wallpaper whose stage origin
// matches its own (the monitor at 0,0) to the redraw clip of the view being
// painted. When another monitor's view is painted first, the copy is cached
// empty and the overview shows its plain gray instead of the wallpaper. A
// wallpaper offset by one pixel is always drawn whole; the effect still crops
// it to the container.
export const WALLPAPER_OVERSCAN = 1;

export function overscanWallpapers(container) {
    const place = actor => {
        actor.set_position(-WALLPAPER_OVERSCAN, -WALLPAPER_OVERSCAN);
        actor.set_size(container.width + 2 * WALLPAPER_OVERSCAN,
            container.height + 2 * WALLPAPER_OVERSCAN);
    };
    const placeAll = () => container.get_children().forEach(place);
    // Signals on the container end with it; no disconnect is needed.
    container.connect('child-added', (_container, actor) => place(actor));
    container.connect('notify::width', placeAll);
    container.connect('notify::height', placeAll);
    placeAll();
}
