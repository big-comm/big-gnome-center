/* The `ext-background-effect-v1` half of the blur, shared by the GTK 4 module
 * and the GTK 3 module: each finds a window's surface and content, this asks
 * the compositor to blur behind it. */

#pragma once

#include <cairo.h>
#include <glib-object.h>
#include <wayland-client.h>

/* Read `bigstyle/blur.ini` from the user's configuration. FALSE without it:
 * BigStyle's theme lets nothing through. `menus` is whether menus and
 * popovers are translucent, and so blurred too. */
gboolean blur_configure (gboolean *menus);

/* Call `changed` whenever BigStyle rewrites or removes `blur.ini`, and
 * whenever the compositor's blur capability comes or goes, so a running
 * program follows both. */
void blur_watch_settings (void (*changed) (void));

/* Blur the content rectangle of `surface` inside rounded corners, or take
 * the blur away while the compositor offers none. The effect is released with
 * `owner`, the toolkit object that owns the surface. */
void blur_set_region (GObject              *owner,
                      struct wl_display    *display,
                      struct wl_compositor *compositor,
                      struct wl_surface    *surface,
                      int                   x,
                      int                   y,
                      int                   width,
                      int                   height);

/* Blur `shape`, in the coordinates of `surface`, as `blur_set_region` does. */
void blur_set_shape (GObject              *owner,
                     struct wl_display    *display,
                     struct wl_compositor *compositor,
                     struct wl_surface    *surface,
                     const cairo_region_t *shape);

/* Add a rectangle to `shape` with its corners rounded by `radius`, to the pixel. */
void blur_add_rounded (cairo_region_t *shape, int x, int y, int width, int height, int radius);

/* Whether the compositor on `display` draws blur now. */
gboolean blur_offered (struct wl_display *display);

/* Take the blur away from a surface `blur_set_region` gave it. */
void blur_clear (GObject *owner, struct wl_surface *surface);
