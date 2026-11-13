/* GTK 4 module: mark the windows whose regions can paint themselves, and ask
 * the compositor to blur behind every window while BigStyle's theme is
 * translucent, and behind the windows BigLinux's own programs mark.
 *
 * GTK 4 loads no modules, but every GTK 4 program scans its `immodules`
 * directory for GIO modules when it starts. Installed there, this library
 * reaches all of them and nothing else.
 *
 * Blur shows only where the window's own alpha is below 255, so the region
 * declared here is the whole content and the stylesheet decides what is seen
 * through. A window another stylesheet makes translucent, as Big GNOME
 * Center's window material does, is blurred inside its plane.
 *
 * It also widens the caret while high contrast is on, which GTK takes from a
 * setting rather than the stylesheet, and under big-compositor it gives the
 * windows the compositor's frame above every stylesheet (`window-frame.h`).
 */

#include <math.h>

#include <gdk/wayland/gdkwayland.h>
#include <gtk/gtk.h>

#include "background-effect.h"
#include "window-frame.h"

#define WATCHED_KEY "bigstyle-blur-watched"
#define CARET_KEY "bigstyle-caret-watched"
#define FRAME_KEY "bigstyle-frame-watched"
/* Twice GTK's stock share of the line height (BigStyle's
 * `HIGH_CONTRAST_CARET_ASPECT`). */
#define CONTRAST_CARET_ASPECT 0.08
/* BigStyle's stylesheet clears a window with this class and paints its
 * regions instead (`region_planes_css`). */
#define REGIONS_CLASS "bigstyle-regions"
/* A window whose content is a sidebar beside its content: the layouts that take
 * the two apart paint its plane (`panels_css`). */
#define SPLIT_CLASS "bigstyle-split"
/* big-workspace marks a window of BigLinux's own programs (BigTerminal,
 * BigFiles, BigEditor) with this class while it is translucent. On GTK 4.24
 * the program asks for its blur through KDE's protocol where the compositor
 * offers it (big-compositor) and leaves it to GTK's effect object elsewhere
 * (KWin), which this module takes; older GTK leaves the effect to the program. */
#define BLUR_BEHIND_CLASS "big-blur-behind"
#define BLUR_BEHIND_KEY "bigstyle-blur-behind"
#define KDE_BLUR_MANAGER "org_kde_kwin_blur_manager"
/* GTK asks the compositor to blur behind a `backdrop-filter` from this blur
 * radius on, and blurs smaller ones inside its own drawing
 * (BACKGROUND_BLUR_THRESHOLD in GSK's gskblurutils.c). */
#define BACKDROP_BLUR_RADIUS 20.0
/* In BigStyle's sessions, a window or menu asking for a backdrop blur, or a
 * window translucent by another stylesheet, that BigStyle's theme keeps opaque
 * takes this class, and the rules below put its planes back to the opaque
 * colours they are named after. */
#define UNBLURRED_CLASS "bigstyle-unblurred"
/* A window whose blur the module asks for. A `backdrop-filter` on the window
 * itself blurs only what the window drew below it, which is nothing, and asks
 * the compositor for the blur the module asks for already, while GTK draws
 * its blurred copy into every frame: the rules below take it away, here and
 * on what the theme keeps opaque. */
#define BLURRED_CLASS "bigstyle-blurred"
#define RULES_KEY "bigstyle-rules-provider"
#define DISABLE_VARIABLE "GDK_WAYLAND_DISABLE"
#define EFFECT_MANAGER "ext_background_effect_manager_v1"

static gboolean blur_windows;
static gboolean blur_menus;
/* Whether the session's compositor is one whose blur BigStyle switches,
 * big-compositor or KWin (`session_compositor` in compositor.py). There
 * BigStyle's theme decides what is seen through; elsewhere, as in GNOME, the
 * session's own tools do. */
static gboolean bigstyle_session;
/* GTK 4.23.3 and newer create an `ext_background_effect_surface_v1` for every
 * surface, and a second one is a protocol error that ends the program. On
 * those versions the module takes the effect manager from GDK and blurs only
 * the display GDK opened without it, asking for every blur GTK would have
 * asked. */
static gboolean gtk_has_effect;
static GdkDisplay *effect_display;
/* The user's GDK_WAYLAND_DISABLE, put back once that display is open. */
static char *user_disabled;
/* Every window and popover shown, so a change of settings reaches them. */
static GPtrArray *natives;
/* On every display, made when the first window maps. */
static GtkCssProvider *frame_provider;
static GFile *square_stylesheet;
/* Added to a display when its first window takes one of the classes. */
static GtkCssProvider *rules_provider;

static const char rules_css[] =
  "window." UNBLURRED_CLASS " {"
  "  --window-bg-color: @window_bg_color;"
  "  --view-bg-color: @view_bg_color;"
  "  --headerbar-bg-color: @headerbar_bg_color;"
  "  --headerbar-backdrop-color: @headerbar_backdrop_color;"
  "  --sidebar-bg-color: @sidebar_bg_color;"
  "  --sidebar-backdrop-color: @sidebar_backdrop_color;"
  "  --secondary-sidebar-bg-color: @secondary_sidebar_bg_color;"
  "  --secondary-sidebar-backdrop-color: @secondary_sidebar_backdrop_color;"
  "  background-color: @window_bg_color;"
  "}"
  "popover." UNBLURRED_CLASS " { --popover-bg-color: @popover_bg_color; }"
  "popover." UNBLURRED_CLASS " > contents, popover." UNBLURRED_CLASS " > arrow {"
  "  background-color: @popover_bg_color;"
  "}"
  "window." UNBLURRED_CLASS ", window." BLURRED_CLASS ","
  "popover." UNBLURRED_CLASS " > contents { backdrop-filter: none; }";

/* The content rectangle of a native in its surface: a window without its
 * client-side shadow, a popover's contents node without its arrow. */
static gboolean
content_area (GtkWidget *native, graphene_rect_t *area)
{
  double inset_x = 0, inset_y = 0;

  gtk_native_get_surface_transform (GTK_NATIVE (native), &inset_x, &inset_y);
  if (GTK_IS_POPOVER (native))
    {
      GtkWidget *contents = gtk_widget_get_first_child (native);

      while (contents != NULL && g_strcmp0 (gtk_widget_get_css_name (contents), "contents") != 0)
        contents = gtk_widget_get_next_sibling (contents);
      /* Before its first layout the contents lie outside the popover. */
      if (contents == NULL || !gtk_widget_compute_bounds (contents, native, area)
          || area->origin.x < 0 || area->origin.y < 0)
        return FALSE;
    }
  else
    graphene_rect_init (area, 0, 0, gtk_widget_get_width (native), gtk_widget_get_height (native));
  area->origin.x += inset_x;
  area->origin.y += inset_y;
  return TRUE;
}

static gboolean
in_marked_window (GtkWidget *popover)
{
  GtkRoot *root = gtk_widget_get_root (popover);

  return GTK_IS_WINDOW (root) && gtk_widget_has_css_class (GTK_WIDGET (root), BLUR_BEHIND_CLASS);
}

/* Whether `node` is the filter chain GTK draws for a `backdrop-filter`
 * (gtk_widget_create_render_node): filters with one child each down to the
 * paste of what lies behind, one of them a blur GTK leaves to the compositor. */
static gboolean
pastes_blurred (GskRenderNode *node, gboolean blurred)
{
  GskRenderNode **children;
  gsize n_children;

  switch (gsk_render_node_get_node_type (node))
    {
    case GSK_PASTE_NODE:
      return blurred;
    case GSK_BLUR_NODE:
      blurred = blurred || gsk_blur_node_get_radius (node) >= BACKDROP_BLUR_RADIUS;
      break;
    case GSK_COLOR_MATRIX_NODE:
    case GSK_COMPONENT_TRANSFER_NODE:
    case GSK_OPACITY_NODE:
    case GSK_SHADOW_NODE:
    case GSK_REPEAT_NODE:
      break;
    default:
      return FALSE;
    }
  children = gsk_render_node_get_children (node, &n_children);
  return n_children == 1 && pastes_blurred (children[0], blurred);
}

/* The box inside `clip`, rounded by its widest corner. */
static void
add_box (cairo_region_t *shape, const GskRoundedRect *box, double x, double y,
         const graphene_rect_t *clip)
{
  cairo_region_t *part = cairo_region_create ();
  cairo_rectangle_int_t inside = {
    (int) floor (clip->origin.x), (int) floor (clip->origin.y),
    (int) ceil (clip->origin.x + clip->size.width) - (int) floor (clip->origin.x),
    (int) ceil (clip->origin.y + clip->size.height) - (int) floor (clip->origin.y),
  };
  int left = (int) floor (box->bounds.origin.x + x);
  int top = (int) floor (box->bounds.origin.y + y);
  int right = (int) ceil (box->bounds.origin.x + box->bounds.size.width + x);
  int bottom = (int) ceil (box->bounds.origin.y + box->bounds.size.height + y);
  float radius = 0;

  for (int i = 0; i < 4; i++)
    radius = MAX (radius, MAX (box->corner[i].width, box->corner[i].height));
  blur_add_rounded (part, left, top, right - left, bottom - top, (int) ceilf (radius));
  cairo_region_intersect_rectangle (part, &inside);
  cairo_region_union (shape, part);
  cairo_region_destroy (part);
}

/* Add to `shape` the border box of each widget in `node` whose stylesheet
 * asks for a backdrop blur: GTK clips the blurred backdrop to that box, with
 * a rounded clip, or a plain one when no corner is rounded. `x`, `y` place
 * the node in the surface and `clip` bounds it there. A part under a
 * transform other than a translation is left out. */
static void
add_backdrops (GskRenderNode *node, double x, double y, const graphene_rect_t *clip,
               cairo_region_t *shape)
{
  GskRenderNode **children;
  gsize n_children;
  graphene_rect_t inside;

  switch (gsk_render_node_get_node_type (node))
    {
    case GSK_TRANSFORM_NODE:
      {
        GskTransform *transform = gsk_transform_node_get_transform (node);
        float dx, dy;

        if (gsk_transform_get_category (transform) < GSK_TRANSFORM_CATEGORY_2D_TRANSLATE)
          return;
        gsk_transform_to_translate (transform, &dx, &dy);
        add_backdrops (gsk_transform_node_get_child (node), x + dx, y + dy, clip, shape);
        return;
      }
    case GSK_CLIP_NODE:
      /* A box without rounded corners clips square. */
      if (pastes_blurred (gsk_clip_node_get_child (node), FALSE))
        {
          GskRoundedRect box;

          gsk_rounded_rect_init_from_rect (&box, gsk_clip_node_get_clip (node), 0);
          add_box (shape, &box, x, y, clip);
          return;
        }
      graphene_rect_offset_r (gsk_clip_node_get_clip (node), x, y, &inside);
      if (graphene_rect_intersection (&inside, clip, &inside))
        add_backdrops (gsk_clip_node_get_child (node), x, y, &inside, shape);
      return;
    case GSK_ROUNDED_CLIP_NODE:
      {
        const GskRoundedRect *box = gsk_rounded_clip_node_get_clip (node);
        GskRenderNode *child = gsk_rounded_clip_node_get_child (node);

        if (pastes_blurred (child, FALSE))
          {
            add_box (shape, box, x, y, clip);
            return;
          }
        graphene_rect_offset_r (&box->bounds, x, y, &inside);
        if (graphene_rect_intersection (&inside, clip, &inside))
          add_backdrops (child, x, y, &inside, shape);
        return;
      }
    default:
      children = gsk_render_node_get_children (node, &n_children);
      for (gsize i = 0; i < n_children; i++)
        add_backdrops (children[i], x, y, clip, shape);
    }
}

/* The first colour `node` paints over the whole of `area`, alone or inside a
 * rounded clip, as `box` in the surface: a window's own plane, which GTK
 * paints before anything the window holds. */
static gboolean
find_plane (GskRenderNode *node, double x, double y, const graphene_rect_t *area,
            GskRoundedRect *box, float *alpha)
{
  GskRenderNode **children;
  gsize n_children;
  graphene_rect_t bounds;

  switch (gsk_render_node_get_node_type (node))
    {
    case GSK_COLOR_NODE:
      gsk_render_node_get_bounds (node, &bounds);
      graphene_rect_offset (&bounds, x, y);
      /* Snapped to the pixel, a box may fall short of the area by a fraction. */
      graphene_rect_inset (&bounds, -1, -1);
      if (!graphene_rect_contains_rect (&bounds, area))
        return FALSE;
      graphene_rect_inset (&bounds, 1, 1);
      gsk_rounded_rect_init_from_rect (box, &bounds, 0);
      *alpha = gsk_color_node_get_color (node)->alpha;
      return TRUE;
    case GSK_ROUNDED_CLIP_NODE:
      {
        GskRenderNode *child = gsk_rounded_clip_node_get_child (node);

        if (gsk_render_node_get_node_type (child) == GSK_COLOR_NODE
            && find_plane (child, x, y, area, box, alpha))
          {
            gsk_rounded_rect_init_copy (box, gsk_rounded_clip_node_get_clip (node));
            gsk_rounded_rect_offset (box, x, y);
            return TRUE;
          }
        return find_plane (child, x, y, area, box, alpha);
      }
    case GSK_TRANSFORM_NODE:
      {
        GskTransform *transform = gsk_transform_node_get_transform (node);
        float dx, dy;

        if (gsk_transform_get_category (transform) < GSK_TRANSFORM_CATEGORY_2D_TRANSLATE)
          return FALSE;
        gsk_transform_to_translate (transform, &dx, &dy);
        return find_plane (gsk_transform_node_get_child (node), x + dx, y + dy, area, box, alpha);
      }
    /* A `backdrop-filter` wraps all its widget draws in a copy. */
    case GSK_COPY_NODE:
    case GSK_CONTAINER_NODE:
    case GSK_DEBUG_NODE:
    case GSK_OPACITY_NODE:
    case GSK_CLIP_NODE:
      children = gsk_render_node_get_children (node, &n_children);
      for (gsize i = 0; i < n_children; i++)
        if (find_plane (children[i], x, y, area, box, alpha))
          return TRUE;
      return FALSE;
    default:
      return FALSE;
    }
}

/* What the native's last frame asks to have blurred behind it, in its surface:
 * the backdrops its stylesheet blurs, and the plane of a window it makes
 * translucent. A window that dropped GTK's `background` class is meant to show
 * what lies behind it as it is. */
static cairo_region_t *
backdrop_shape (GtkWidget *native, gboolean *translucent)
{
  cairo_region_t *shape = cairo_region_create ();
  g_autoptr (GdkPaintable) paintable = NULL;
  g_autoptr (GskRenderNode) node = NULL;
  GtkSnapshot *snapshot;
  graphene_rect_t bounds, clip, area;
  GskRoundedRect plane;
  float alpha;
  double x, y;

  *translucent = FALSE;
  if (!gtk_widget_compute_bounds (native, native, &bounds))
    return shape;
  /* The widget's own render node, which the paintable shows translated by
   * the bounds' origin. */
  paintable = gtk_widget_paintable_new (native);
  snapshot = gtk_snapshot_new ();
  gdk_paintable_snapshot (paintable, snapshot, ceilf (bounds.size.width),
                          ceilf (bounds.size.height));
  node = gtk_snapshot_free_to_node (snapshot);
  if (node == NULL)
    return shape;
  gtk_native_get_surface_transform (GTK_NATIVE (native), &x, &y);
  x += bounds.origin.x;
  y += bounds.origin.y;
  gsk_render_node_get_bounds (node, &clip);
  graphene_rect_offset (&clip, x, y);
  add_backdrops (node, x, y, &clip, shape);
  if (GTK_IS_WINDOW (native) && gtk_widget_has_css_class (native, "background")
      && content_area (native, &area) && find_plane (node, x, y, &area, &plane, &alpha)
      && alpha < 1)
    {
      add_box (shape, &plane, 0, 0, &clip);
      *translucent = TRUE;
    }
  return shape;
}

/* Give `native` the class `name`, or take it away, with the rules that go with it. */
static void
follow_class (GtkWidget *native, const char *name, gboolean on)
{
  GdkDisplay *display = gtk_widget_get_display (native);

  if (on == gtk_widget_has_css_class (native, name))
    return;
  if (!on)
    {
      gtk_widget_remove_css_class (native, name);
      return;
    }
  if (g_object_get_data (G_OBJECT (display), RULES_KEY) == NULL)
    {
      g_object_set_data (G_OBJECT (display), RULES_KEY, GINT_TO_POINTER (1));
      if (rules_provider == NULL)
        {
          rules_provider = gtk_css_provider_new ();
          gtk_css_provider_load_from_string (rules_provider, rules_css);
        }
      gtk_style_context_add_provider_for_display (display, GTK_STYLE_PROVIDER (rules_provider),
                                                  GTK_STYLE_PROVIDER_PRIORITY_USER + 1);
    }
  gtk_widget_add_css_class (native, name);
}

static void
follow_unblurred (GtkWidget *native, gboolean unblurred)
{
  follow_class (native, UNBLURRED_CLASS, unblurred);
}

static void
follow_blurred (GtkWidget *native, gboolean blurred)
{
  follow_class (native, BLURRED_CLASS, blurred && GTK_IS_WINDOW (native));
}

static void
apply (GtkWidget *native)
{
  GdkSurface *surface = gtk_native_get_surface (GTK_NATIVE (native));
  GdkDisplay *display;
  struct wl_display *wl_display;
  struct wl_surface *wl_surface;
  cairo_region_t *shape;
  graphene_rect_t area;
  gboolean whole, asked, offered, translucent;

  if (surface == NULL)
    return;
  display = gdk_surface_get_display (surface);
  if (!GDK_IS_WAYLAND_DISPLAY (display) || (gtk_has_effect && display != effect_display))
    return;
  wl_display = gdk_wayland_display_get_wl_display (display);
  wl_surface = gdk_wayland_surface_get_wl_surface (surface);
  /* A surface takes one request: KDE's blur beside this one blurs it twice,
   * and a second effect object ends the program. */
  if (GTK_IS_WINDOW (native) && gtk_widget_has_css_class (native, BLUR_BEHIND_CLASS))
    {
      follow_unblurred (native, FALSE);
      whole = gtk_has_effect && !gdk_wayland_display_query_registry (display, KDE_BLUR_MANAGER);
      if (!whole)
        {
          follow_blurred (native, FALSE);
          blur_clear (G_OBJECT (surface), wl_surface);
          return;
        }
    }
  else if (GTK_IS_POPOVER (native))
    /* A blurred menu over a blurred window pays twice, so menus only while
     * they are translucent, and in a window big-workspace marks, whose
     * stylesheet asks for their blur (`backdrop-filter`): GTK cannot ask
     * while this module holds the effect. */
    whole = (blur_windows && blur_menus) || in_marked_window (native);
  else
    whole = blur_windows;
  if (whole)
    {
      follow_unblurred (native, FALSE);
      follow_blurred (native, TRUE);
      if (content_area (native, &area))
        blur_set_region (G_OBJECT (surface), wl_display,
                         gdk_wayland_display_get_wl_compositor (display), wl_surface,
                         (int) area.origin.x, (int) area.origin.y,
                         (int) area.size.width, (int) area.size.height);
      return;
    }
  /* In BigStyle's sessions its theme wins over another program's material:
   * what the theme keeps opaque stays opaque, blur or not. Elsewhere the
   * module asks for the blur and changes nothing else. */
  shape = backdrop_shape (native, &translucent);
  /* The opaque planes the class gives hide the translucent one that asked. */
  asked = !cairo_region_is_empty (shape) || gtk_widget_has_css_class (native, UNBLURRED_CLASS);
  offered = asked && !bigstyle_session && blur_offered (wl_display);
  follow_unblurred (native, asked && bigstyle_session);
  follow_blurred (native, offered && translucent);
  if (offered)
    blur_set_shape (G_OBJECT (surface), wl_display, gdk_wayland_display_get_wl_compositor (display),
                    wl_surface, shape);
  else
    blur_clear (G_OBJECT (surface), wl_surface);
  cairo_region_destroy (shape);
}

/* The first region, and each one after a resize, is set after the next frame:
 * the surface has its first size before anything can listen for it, and a new
 * size before the window is laid out at it. */
static void
on_after_paint (GdkFrameClock *clock, gpointer native)
{
  if (gtk_widget_get_width (GTK_WIDGET (native)) <= 0)
    return;
  g_signal_handlers_disconnect_by_func (clock, on_after_paint, native);
  apply (GTK_WIDGET (native));
}

static void
apply_after_paint (GtkWidget *native)
{
  GdkSurface *surface = gtk_native_get_surface (GTK_NATIVE (native));
  GdkFrameClock *clock = surface != NULL ? gdk_surface_get_frame_clock (surface) : NULL;

  if (clock == NULL)
    {
      apply (native);
      return;
    }
  g_signal_handlers_disconnect_by_func (clock, on_after_paint, native);
  g_signal_connect_object (clock, "after-paint", G_CALLBACK (on_after_paint), native, 0);
}

static void
on_surface_resized (GObject *surface, GParamSpec *pspec, gpointer native)
{
  apply_after_paint (GTK_WIDGET (native));
}

/* The mark comes and goes as the program turns translucent or opaque. It is
 * followed at once, by the window and its open popovers: the program asks
 * through KDE's blur right after marking, and the surface's next frame must
 * carry one request. Any other class may change what the stylesheet asks to
 * blur, which the frame drawn in it shows. */
static void
on_classes_changed (GObject *window, GParamSpec *pspec, gpointer data)
{
  gboolean marked = gtk_widget_has_css_class (GTK_WIDGET (window), BLUR_BEHIND_CLASS);

  if (marked == GPOINTER_TO_INT (g_object_get_data (window, BLUR_BEHIND_KEY)))
    {
      apply_after_paint (GTK_WIDGET (window));
      return;
    }
  g_object_set_data (window, BLUR_BEHIND_KEY, GINT_TO_POINTER (marked));
  for (guint i = 0; i < natives->len; i++)
    {
      GtkWidget *native = g_ptr_array_index (natives, i);

      if (native == GTK_WIDGET (window)
          || (GTK_IS_POPOVER (native) && gtk_widget_get_root (native) == GTK_ROOT (window)))
        apply (native);
    }
}

static void
on_settings_changed (void)
{
  blur_windows = blur_configure (&blur_menus);
  for (guint i = 0; i < natives->len; i++)
    apply (g_ptr_array_index (natives, i));
}

/* The node that holds a window's content, past what libadwaita and programs
 * wrap around it: a container with one visible child, the main child of an
 * overlay, which comes first, or the page a stack shows. */
static GtkWidget *
content_root (GtkWindow *window)
{
  GtkWidget *node = gtk_window_get_child (window);

  while (node != NULL)
    {
      const char *name = gtk_widget_get_css_name (node);
      GtkWidget *only = NULL;
      int shown = 0;

      if (g_str_equal (name, "dialog-host") || g_str_equal (name, "toastoverlay")
          || g_str_equal (name, "overlay"))
        {
          node = gtk_widget_get_first_child (node);
          continue;
        }
      if (GTK_IS_STACK (node))
        {
          node = gtk_stack_get_visible_child (GTK_STACK (node));
          continue;
        }
      for (GtkWidget *child = gtk_widget_get_first_child (node); child != NULL;
           child = gtk_widget_get_next_sibling (child))
        if (gtk_widget_get_visible (child))
          only = child, shown++;
      if (shown != 1)
        return node;
      node = only;
    }
  return NULL;
}

/* A window laid out in libadwaita's regions has nothing outside them, so
 * the window itself can stay clear. Anything else keeps its plane. */
static void
mark_regions (GtkWindow *window)
{
  GtkWidget *root = content_root (window);
  const char *name = root != NULL ? gtk_widget_get_css_name (root) : NULL;

  if (g_strcmp0 (name, "toolbarview") == 0 || g_strcmp0 (name, "overlay-split-view") == 0
      || g_strcmp0 (name, "navigation-split-view") == 0
      || g_strcmp0 (name, "navigation-view") == 0)
    gtk_widget_add_css_class (GTK_WIDGET (window), REGIONS_CLASS);
  if (g_strcmp0 (name, "overlay-split-view") == 0 || g_strcmp0 (name, "navigation-split-view") == 0)
    gtk_widget_add_css_class (GTK_WIDGET (window), SPLIT_CLASS);
}

/* Programs set their content before the first frame. */
static void
on_first_paint (GdkFrameClock *clock, gpointer window)
{
  g_signal_handlers_disconnect_by_func (clock, on_first_paint, window);
  mark_regions (GTK_WINDOW (window));
}

static void
forget (gpointer data, GObject *native)
{
  g_ptr_array_remove_fast (natives, native);
}

/* A desktop component on a layer surface (a panel, the wallpaper) and its menus.
 * Its surface is larger than what it draws, and it asks for its own blur where it
 * does draw: a region over the whole surface would blur the windows under its
 * transparent margin. gtk4-layer-shell keeps its state on the window under this
 * key, which is what gtk_layer_is_layer_window() reads; reading it here keeps that
 * library out of every GTK program. */
static gboolean
on_layer_surface (GtkWidget *native)
{
  GtkRoot *root = gtk_widget_get_root (native);

  return root != NULL && g_object_get_data (G_OBJECT (root), "wayland_layer_surface") != NULL;
}

/* Only a caret this module widened is put back, so a program's own stays. */
static void
follow_contrast (GtkSettings *settings)
{
  GtkInterfaceContrast contrast;
  gboolean widened = GPOINTER_TO_INT (g_object_get_data (G_OBJECT (settings), CARET_KEY)) == 2;

  g_object_get (settings, "gtk-interface-contrast", &contrast, NULL);
  if (contrast == GTK_INTERFACE_CONTRAST_MORE)
    {
      g_object_set (settings, "gtk-cursor-aspect-ratio", CONTRAST_CARET_ASPECT, NULL);
      g_object_set_data (G_OBJECT (settings), CARET_KEY, GINT_TO_POINTER (2));
    }
  else if (widened)
    {
      gtk_settings_reset_property (settings, "gtk-cursor-aspect-ratio");
      g_object_set_data (G_OBJECT (settings), CARET_KEY, GINT_TO_POINTER (1));
    }
}

static void
on_contrast_changed (GtkSettings *settings, GParamSpec *pspec, gpointer data)
{
  follow_contrast (settings);
}

/* The square outline while the windows are square, which a missing layer (a
 * restore) leaves out, then their radius, shadow and border. */
static void
follow_frame (void)
{
  const WindowFrame *frame = window_frame ();
  g_autofree char *square = NULL;
  g_autofree char *rest = window_frame_css (frame, TRUE);
  g_autofree char *css = NULL;

  if (frame->square)
    g_file_load_contents (square_stylesheet, NULL, &square, NULL, NULL, NULL);
  css = g_strconcat (square != NULL ? square : "", rest, NULL);
  gtk_css_provider_load_from_string (frame_provider, css);
}

/* Above the user's gtk.css and a program's own stylesheets, whatever their
 * selectors: every window wears the frame. */
static void
frame_windows (GdkDisplay *display)
{
  if (g_object_get_data (G_OBJECT (display), FRAME_KEY) != NULL)
    return;
  g_object_set_data (G_OBJECT (display), FRAME_KEY, GINT_TO_POINTER (1));
  if (frame_provider == NULL)
    {
      square_stylesheet = g_file_new_build_filename (g_get_user_config_dir (), "gtk-4.0",
                                                     "bigstyle-reduced.css", NULL);
      frame_provider = gtk_css_provider_new ();
      window_frame_watch (square_stylesheet, follow_frame);
      follow_frame ();
    }
  gtk_style_context_add_provider_for_display (display, GTK_STYLE_PROVIDER (frame_provider),
                                              GTK_STYLE_PROVIDER_PRIORITY_USER + 1);
}

static gboolean
on_widget_mapped (GSignalInvocationHint *hint,
                  guint                  n_values,
                  const GValue          *values,
                  gpointer               data)
{
  GtkWidget *widget = g_value_get_object (&values[0]);
  gboolean window = GTK_IS_WINDOW (widget);
  GdkSurface *surface;
  GdkFrameClock *clock;

  if (!window && !GTK_IS_POPOVER (widget))
    return TRUE;
  /* Settings belong to a display, which exists once a window maps. */
  if (window)
    {
      GtkSettings *settings = gtk_widget_get_settings (widget);

      if (g_object_get_data (G_OBJECT (settings), CARET_KEY) == NULL)
        {
          g_object_set_data (G_OBJECT (settings), CARET_KEY, GINT_TO_POINTER (1));
          g_signal_connect (settings, "notify::gtk-interface-contrast",
                            G_CALLBACK (on_contrast_changed), NULL);
          follow_contrast (settings);
        }
      frame_windows (gtk_widget_get_display (widget));
    }
  if (on_layer_surface (widget))
    return TRUE;
  surface = gtk_native_get_surface (GTK_NATIVE (widget));
  if (surface == NULL || (window && !GDK_IS_TOPLEVEL (surface))
      || g_object_get_data (G_OBJECT (surface), WATCHED_KEY) != NULL)
    return TRUE;
  g_object_set_data (G_OBJECT (surface), WATCHED_KEY, GINT_TO_POINTER (1));

  clock = gdk_surface_get_frame_clock (surface);
  if (window && clock != NULL)
    g_signal_connect_object (clock, "after-paint", G_CALLBACK (on_first_paint), widget, 0);
  if (!g_ptr_array_find (natives, widget, NULL))
    {
      g_ptr_array_add (natives, widget);
      g_object_weak_ref (G_OBJECT (widget), forget, NULL);
      if (window)
        {
          gboolean marked = gtk_widget_has_css_class (widget, BLUR_BEHIND_CLASS);

          g_object_set_data (G_OBJECT (widget), BLUR_BEHIND_KEY, GINT_TO_POINTER (marked));
          g_signal_connect (widget, "notify::css-classes", G_CALLBACK (on_classes_changed), NULL);
        }
    }
  g_signal_connect_object (surface, "notify::width", G_CALLBACK (on_surface_resized), widget, 0);
  g_signal_connect_object (surface, "notify::height", G_CALLBACK (on_surface_resized), widget, 0);
  if (clock != NULL)
    g_signal_connect_object (clock, "after-paint", G_CALLBACK (on_after_paint), widget, 0);
  return TRUE;
}

static void
on_display_opened (GdkDisplayManager *manager, GdkDisplay *display, gpointer data)
{
  g_signal_handlers_disconnect_by_func (manager, on_display_opened, data);
  effect_display = display;
  g_object_add_weak_pointer (G_OBJECT (display), (gpointer *) &effect_display);
  if (user_disabled != NULL)
    g_setenv (DISABLE_VARIABLE, user_disabled, TRUE);
  else
    g_unsetenv (DISABLE_VARIABLE);
  g_clear_pointer (&user_disabled, g_free);
}

static gboolean
in_bigstyle_session (void)
{
  const char *desktop = g_getenv ("XDG_CURRENT_DESKTOP");
  g_auto (GStrv) names = g_strsplit (desktop != NULL ? desktop : "", ":", -1);

  return g_strv_contains ((const char *const *) names, "big-compositor")
         || g_strv_contains ((const char *const *) names, "KDE");
}

/* GDK reads GDK_WAYLAND_DISABLE once, when it opens a display, and GTK opens
 * its first one right after it loads its modules. A display a program opened
 * before GTK's own keeps GTK's effect and goes without blur. */
static void
leave_effect_to_module (void)
{
  GdkDisplayManager *manager = gdk_display_manager_get ();
  g_autofree char *disabled = NULL;

  if (gdk_display_manager_get_default_display (manager) != NULL)
    return;
  user_disabled = g_strdup (g_getenv (DISABLE_VARIABLE));
  disabled = user_disabled != NULL ? g_strconcat (user_disabled, ":", EFFECT_MANAGER, NULL)
                                   : g_strdup (EFFECT_MANAGER);
  g_setenv (DISABLE_VARIABLE, disabled, TRUE);
  g_signal_connect (manager, "display-opened", G_CALLBACK (on_display_opened), NULL);
}

/* GIO calls this when it scans the directory. The library is linked with
 * -z nodelete: GIO unloads a module that registers no type, and the hook
 * below would then point at unmapped code. */
G_MODULE_EXPORT void
g_io_module_load (GIOModule *module)
{
  guint map_signal;

  if (natives != NULL)
    return;
  natives = g_ptr_array_new ();
  blur_windows = blur_configure (&blur_menus);
  bigstyle_session = in_bigstyle_session ();
  gtk_has_effect = gtk_check_version (4, 23, 3) == NULL;
  if (gtk_has_effect)
    leave_effect_to_module ();
  blur_watch_settings (on_settings_changed);
  /* Referencing the class registers the type without a display. */
  g_type_class_unref (g_type_class_ref (GTK_TYPE_WIDGET));
  map_signal = g_signal_lookup ("map", GTK_TYPE_WIDGET);
  /* GtkWidget::map sees every window and popover the process shows. */
  if (map_signal != 0)
    g_signal_add_emission_hook (map_signal, 0, on_widget_mapped, NULL, NULL);
}

G_MODULE_EXPORT void
g_io_module_unload (GIOModule *module)
{
}
