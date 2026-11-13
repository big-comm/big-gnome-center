#include "background-effect.h"

#include <math.h>

#include <gio/gio.h>

#include "ext-background-effect-v1-client-protocol.h"

/* The radius of the corners the region follows, so the blur stays inside a
 * rounded window. BigStyle writes the corner radius it applies. */
#define DEFAULT_CORNER_RADIUS 12
#define EFFECT_KEY "bigstyle-blur-effect"
#define AREA_KEY "bigstyle-blur-area"

/* Silent unless BIGSTYLE_BLUR_DEBUG is set. */
#define note(...) G_STMT_START {                                \
    if (debug)                                                  \
      g_printerr ("bigstyle-blur: " __VA_ARGS__);               \
  } G_STMT_END

static struct ext_background_effect_manager_v1 *manager;
static gboolean blur_available;
static gboolean registry_ready;
/* Set once the first capabilities are in: later ones are changes. */
static gboolean bound;
static gboolean debug;
static int radius_setting = DEFAULT_CORNER_RADIUS;
static void (*settings_changed) (void);

static char *
settings_path (void)
{
  return g_build_filename (g_get_user_config_dir (), "bigstyle", "blur.ini", NULL);
}

gboolean
blur_configure (gboolean *menus)
{
  g_autofree char *path = settings_path ();
  g_autoptr (GKeyFile) settings = g_key_file_new ();
  g_autoptr (GError) error = NULL;
  gint64 radius;

  debug = g_getenv ("BIGSTYLE_BLUR_DEBUG") != NULL;
  *menus = FALSE;
  if (!g_key_file_load_from_file (settings, path, G_KEY_FILE_NONE, &error))
    {
      note ("off: %s\n", error->message);
      return FALSE;
    }
  radius = g_key_file_get_int64 (settings, "Blur", "Radius", NULL);
  if (radius >= 0 && radius <= 64)
    radius_setting = (int) radius;
  *menus = g_key_file_get_boolean (settings, "Blur", "Menus", NULL);
  note ("on, radius %d, menus %d\n", radius_setting, *menus);
  return TRUE;
}

static void
on_settings_changed (GFileMonitor     *monitor,
                     GFile            *file,
                     GFile            *other,
                     GFileMonitorEvent event,
                     gpointer          data)
{
  /* BigStyle replaces the file in one rename. */
  if (event == G_FILE_MONITOR_EVENT_CHANGES_DONE_HINT || event == G_FILE_MONITOR_EVENT_DELETED
      || event == G_FILE_MONITOR_EVENT_MOVED_IN || event == G_FILE_MONITOR_EVENT_RENAMED
      || event == G_FILE_MONITOR_EVENT_CREATED)
    settings_changed ();
}

void
blur_watch_settings (void (*changed) (void))
{
  g_autofree char *path = settings_path ();
  g_autofree char *folder = g_path_get_dirname (path);
  g_autoptr (GFile) file = g_file_new_for_path (path);
  GFileMonitor *monitor;

  settings_changed = changed;
  /* GLib polls a folder that does not exist yet; a person who never applied
   * BigStyle costs nothing, and the next start picks the file up. */
  if (!g_file_test (folder, G_FILE_TEST_IS_DIR))
    return;
  monitor = g_file_monitor_file (file, G_FILE_MONITOR_WATCH_MOVES, NULL, NULL);
  if (monitor != NULL)
    g_signal_connect (monitor, "changed", G_CALLBACK (on_settings_changed), NULL);
}

static void
on_capability_changed (gpointer data)
{
  if (settings_changed != NULL)
    settings_changed ();
}

static void
on_capabilities (void                                    *data,
                 struct ext_background_effect_manager_v1 *object,
                 uint32_t                                 flags)
{
  gboolean available = (flags & EXT_BACKGROUND_EFFECT_MANAGER_V1_CAPABILITY_BLUR) != 0;

  /* Sent when bound and again whenever the compositor's blur is switched.
   * An effect set before the capability went away stays unapplied after it
   * returns, so every window asks again; outside the event dispatch, which
   * may run inside a toolkit signal. */
  if (bound && available != blur_available)
    g_idle_add_once (on_capability_changed, NULL);
  blur_available = available;
  note ("capability blur=%d\n", blur_available);
}

static const struct ext_background_effect_manager_v1_listener manager_listener = {
  .capabilities = on_capabilities,
};

static void
on_global (void               *data,
           struct wl_registry *registry,
           uint32_t            name,
           const char         *interface,
           uint32_t            version)
{
  if (g_strcmp0 (interface, ext_background_effect_manager_v1_interface.name) != 0)
    return;
  manager = wl_registry_bind (registry, name, &ext_background_effect_manager_v1_interface, 1);
  ext_background_effect_manager_v1_add_listener (manager, &manager_listener, NULL);
}

static void
on_global_remove (void *data, struct wl_registry *registry, uint32_t name)
{
}

static const struct wl_registry_listener registry_listener = {
  .global = on_global,
  .global_remove = on_global_remove,
};

/* Bound on first use, on a queue of our own: the round trips run inside a
 * signal emission, where dispatching the toolkit's own queue would re-enter it. */
static gboolean
ensure_manager (struct wl_display *display)
{
  struct wl_display *wrapper;
  struct wl_event_queue *queue;
  struct wl_registry *registry;

  if (registry_ready)
    return manager != NULL && blur_available;
  registry_ready = TRUE;
  queue = wl_display_create_queue (display);
  wrapper = wl_proxy_create_wrapper (display);
  wl_proxy_set_queue ((struct wl_proxy *) wrapper, queue);
  registry = wl_display_get_registry (wrapper);
  wl_registry_add_listener (registry, &registry_listener, NULL);
  /* The first round trip delivers the globals, the second the capabilities. */
  wl_display_roundtrip_queue (display, queue);
  wl_display_roundtrip_queue (display, queue);
  bound = TRUE;
  if (manager != NULL)
    wl_proxy_set_queue ((struct wl_proxy *) manager, NULL);
  wl_registry_destroy (registry);
  wl_proxy_wrapper_destroy (wrapper);
  wl_event_queue_destroy (queue);
  note ("manager=%p blur=%d\n", (void *) manager, blur_available);
  return manager != NULL && blur_available;
}

gboolean
blur_offered (struct wl_display *display)
{
  return ensure_manager (display);
}

void
blur_add_rounded (cairo_region_t *shape, int x, int y, int width, int height, int radius)
{
  cairo_rectangle_int_t middle;

  if (width <= 0 || height <= 0)
    return;
  radius = MIN (radius, MIN (width, height) / 2);
  middle = (cairo_rectangle_int_t) { x, y + radius, width, height - 2 * radius };
  cairo_region_union_rectangle (shape, &middle);
  /* Each row of a corner starts at the first pixel wholly inside the arc. */
  for (int row = 0; row < radius; row++)
    {
      double rise = radius - row;
      int inset = (int) ceil (radius - sqrt ((double) radius * radius - rise * rise));
      cairo_rectangle_int_t top = { x + inset, y + row, width - 2 * inset, 1 };
      cairo_rectangle_int_t bottom = { x + inset, y + height - 1 - row, width - 2 * inset, 1 };

      cairo_region_union_rectangle (shape, &top);
      cairo_region_union_rectangle (shape, &bottom);
    }
}

/* TRUE when the shape was sent, FALSE when the surface already has it or
 * the compositor draws no blur. */
static gboolean
send_shape (GObject              *owner,
            struct wl_display    *display,
            struct wl_compositor *compositor,
            struct wl_surface    *surface,
            const cairo_region_t *shape)
{
  struct ext_background_effect_surface_v1 *effect;
  struct wl_region *region;
  cairo_region_t *sent;

  if (surface == NULL || cairo_region_is_empty (shape))
    return FALSE;
  /* Without the capability nothing is drawn, so nothing is asked. */
  if (!ensure_manager (display))
    {
      blur_clear (owner, surface);
      return FALSE;
    }
  /* Toolkits report a size several times over; one region per shape is enough. */
  sent = g_object_get_data (owner, AREA_KEY);
  if (sent != NULL && cairo_region_equal (sent, shape))
    return FALSE;
  g_object_set_data_full (owner, AREA_KEY, cairo_region_copy (shape),
                          (GDestroyNotify) cairo_region_destroy);

  effect = g_object_get_data (owner, EFFECT_KEY);
  if (effect == NULL)
    {
      effect = ext_background_effect_manager_v1_get_background_effect (manager, surface);
      /* Released with the surface: the protocol forbids an effect outliving it. */
      g_object_set_data_full (owner, EFFECT_KEY, effect,
                              (GDestroyNotify) ext_background_effect_surface_v1_destroy);
    }

  region = wl_compositor_create_region (compositor);
  for (int i = 0; i < cairo_region_num_rectangles (shape); i++)
    {
      cairo_rectangle_int_t part;

      cairo_region_get_rectangle (shape, i, &part);
      wl_region_add (region, part.x, part.y, part.width, part.height);
    }
  ext_background_effect_surface_v1_set_blur_region (effect, region);
  wl_region_destroy (region);
  /* Double-buffered state: it lands on the next commit. */
  wl_surface_commit (surface);
  return TRUE;
}

void
blur_set_shape (GObject              *owner,
                struct wl_display    *display,
                struct wl_compositor *compositor,
                struct wl_surface    *surface,
                const cairo_region_t *shape)
{
  cairo_rectangle_int_t extents;

  if (!send_shape (owner, display, compositor, surface, shape))
    return;
  cairo_region_get_extents (shape, &extents);
  note ("shape %dx%d at %d,%d in %d rectangles\n", extents.width, extents.height, extents.x,
        extents.y, cairo_region_num_rectangles (shape));
}

void
blur_set_region (GObject              *owner,
                 struct wl_display    *display,
                 struct wl_compositor *compositor,
                 struct wl_surface    *surface,
                 int                   x,
                 int                   y,
                 int                   width,
                 int                   height)
{
  cairo_region_t *shape = cairo_region_create ();

  blur_add_rounded (shape, x, y, width, height, radius_setting);
  if (send_shape (owner, display, compositor, surface, shape))
    note ("region %dx%d at %d,%d radius %d\n", width, height, x, y,
          MIN (radius_setting, MIN (width, height) / 2));
  cairo_region_destroy (shape);
}

void
blur_clear (GObject *owner, struct wl_surface *surface)
{
  g_object_set_data (owner, AREA_KEY, NULL);
  if (g_object_get_data (owner, EFFECT_KEY) == NULL || surface == NULL)
    return;
  /* Destroying the effect removes the blur on the next commit. */
  g_object_set_data (owner, EFFECT_KEY, NULL);
  wl_surface_commit (surface);
  note ("cleared\n");
}
