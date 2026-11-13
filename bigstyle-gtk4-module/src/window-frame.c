#include "window-frame.h"

#include <stdlib.h>
#include <string.h>

/* The spread big-compositor's own shadow takes the size of libadwaita's at:
 * its lengths are measured in `shadow_size / UNIT`. */
#define UNIT 19.0
/* The widest sides the compositor draws. */
#define MOST_BORDER 8

/* What the file leaves to the theme. */
#define UNSET_FRAME                                                                              \
  { .square = FALSE, .radius = -1, .shadow = -1, .shadow_inactive = -1, .strength = 100,         \
    .strength_inactive = 100, .border = 0 }

static WindowFrame frame = UNSET_FRAME;
static void (*frame_changed) (void);

static gboolean
in_big_compositor (void)
{
  const char *desktop = g_getenv ("XDG_CURRENT_DESKTOP");
  g_auto (GStrv) names = g_strsplit (desktop != NULL ? desktop : "", ":", -1);

  return g_strv_contains ((const char *const *) names, "big-compositor");
}

/* A whole number from 0 to `most`, or -1. */
static int
number (const char *value, int most)
{
  char *end = NULL;
  gint64 read = g_ascii_strtoll (value, &end, 10);

  if (end == value || *end != '\0' || read < 0)
    return -1;
  return (int) MIN (read, most);
}

/* A shadow's strength, at most 200; 100, libadwaita's, where it does not read. */
static int
strength (const char *value)
{
  int read = number (value, 200);

  return read < 0 ? 100 : read;
}

/* The keys of the `[effects]` and `[decorations]` tables, read line by line
 * as BigStyle reads them: what does not read leaves the theme's frame. No
 * table name or key holds a `#`, so a comment, or a string after a key, is
 * cut there; the one string read, `square_corners`, holds none. */
static WindowFrame
read_frame (GFile *config)
{
  WindowFrame read = UNSET_FRAME;
  gboolean reduced = FALSE, always = FALSE;
  g_autofree char *text = NULL;
  g_auto (GStrv) lines = NULL;
  const char *table = "";

  if (!g_file_load_contents (config, NULL, &text, NULL, NULL, NULL))
    return read;
  lines = g_strsplit (text, "\n", -1);
  for (char **line = lines; *line != NULL; line++)
    {
      char *comment = strchr (*line, '#');
      char *equals;
      char *key;
      char *value;

      if (comment != NULL)
        *comment = '\0';
      g_strstrip (*line);
      if (**line == '[')
        {
          table = g_str_equal (*line, "[effects]")       ? "effects"
                  : g_str_equal (*line, "[decorations]") ? "decorations"
                                                         : "";
          continue;
        }
      equals = strchr (*line, '=');
      if (equals == NULL)
        continue;
      *equals = '\0';
      key = g_strstrip (*line);
      value = g_strstrip (equals + 1);
      if (g_str_equal (table, "effects") && g_str_equal (key, "reduced"))
        reduced = g_str_equal (value, "true");
      else if (g_str_equal (table, "decorations"))
        {
          if (g_str_equal (key, "square_corners"))
            always = g_str_equal (value, "\"always\"");
          else if (g_str_equal (key, "corner_radius"))
            read.radius = number (value, 64);
          else if (g_str_equal (key, "shadow_size"))
            read.shadow = number (value, 48);
          else if (g_str_equal (key, "shadow_size_inactive"))
            read.shadow_inactive = number (value, 48);
          else if (g_str_equal (key, "shadow_strength"))
            read.strength = strength (value);
          else if (g_str_equal (key, "shadow_strength_inactive"))
            read.strength_inactive = strength (value);
          else if (g_str_equal (key, "border_width"))
            read.border = MAX (number (value, MOST_BORDER), 0);
        }
    }
  /* What the compositor draws by: fewer effects square every frame and
   * take its shadows. */
  read.square = reduced || always;
  if (reduced)
    read.shadow = read.shadow_inactive = 0;
  return read;
}

static gboolean
same (const WindowFrame *one, const WindowFrame *other)
{
  return memcmp (one, other, sizeof *one) == 0;
}

static void
on_changed (GFileMonitor     *monitor,
            GFile            *file,
            GFile            *other,
            GFileMonitorEvent event,
            gpointer          config)
{
  WindowFrame now;

  /* Both files are replaced in one rename. */
  if (event != G_FILE_MONITOR_EVENT_CHANGES_DONE_HINT && event != G_FILE_MONITOR_EVENT_DELETED
      && event != G_FILE_MONITOR_EVENT_MOVED_IN && event != G_FILE_MONITOR_EVENT_RENAMED
      && event != G_FILE_MONITOR_EVENT_CREATED)
    return;
  if (config == NULL)
    {
      if (frame.square)
        frame_changed ();
      return;
    }
  /* The compositor's settings rewrite the file for every key they change. */
  now = read_frame (G_FILE (config));
  if (!same (&now, &frame))
    {
      frame = now;
      frame_changed ();
    }
}

/* GLib polls for a file in a folder that does not exist yet; without the
 * folder there is nothing to follow, and the next start picks it up. */
static void
watch (GFile *file, gpointer config)
{
  g_autoptr (GFile) folder = g_file_get_parent (file);
  GFileMonitor *monitor;

  if (g_file_query_file_type (folder, G_FILE_QUERY_INFO_NONE, NULL) != G_FILE_TYPE_DIRECTORY)
    return;
  monitor = g_file_monitor_file (file, G_FILE_MONITOR_WATCH_MOVES, NULL, NULL);
  if (monitor != NULL)
    g_signal_connect (monitor, "changed", G_CALLBACK (on_changed), config);
}

const WindowFrame *
window_frame (void)
{
  return &frame;
}

void
window_frame_watch (GFile *layer, void (*changed) (void))
{
  GFile *config;

  if (!in_big_compositor ())
    return;
  /* Kept for the life of the process, as the monitors are. */
  config = g_file_new_build_filename (g_get_user_config_dir (), "big-compositor", "config.toml",
                                      NULL);
  frame_changed = changed;
  frame = read_frame (config);
  watch (config, config);
  watch (layer, NULL);
}

/* `length` in pixels, with a point whatever the locale. */
static void
add_px (GString *css, double length)
{
  char number[G_ASCII_DTOSTR_BUF_SIZE];

  g_string_append (css, g_ascii_formatd (number, sizeof number, "%.2f", length));
  g_string_append (css, "px");
}

/* One `0 0 BLUR SPREAD rgba(0, 0, 0, ALPHA)` shadow, and a comma before the next. */
static void
add_shadow (GString *css, double blur, double spread, double alpha, gboolean more)
{
  char number[G_ASCII_DTOSTR_BUF_SIZE];

  g_string_append (css, "0 0 ");
  add_px (css, blur);
  g_string_append_c (css, ' ');
  add_px (css, spread);
  g_string_append_printf (css, " rgba(0, 0, 0, %s)%s",
                          g_ascii_formatd (number, sizeof number, "%.4f", alpha),
                          more ? ", " : "");
}

/* The window's sides `border` wide in the colour of its title bar. */
static void
add_sides (GString *css, int border, const char *bar)
{
  g_string_append (css, "0 0 0 ");
  add_px (css, border);
  g_string_append_printf (css, " %s, ", bar);
}

/* The compositor's shadow (`pieces.rs`), libadwaita's at `UNIT`: in focus
 * 14/5 at 15% and 5/2 at 10%, out of it 10/5 at 8%, and a one-pixel ring at
 * 5%, each length `size / UNIT` as large and each alpha `strength` percent as
 * dark, from `shadow` and `strength` in focus, `shadow_inactive` and
 * `strength_inactive` out of it; none at 0. Around the window first, the
 * sides `frame->border` wide, which the shadows reach past. With no shadow,
 * a transparent band keeps the edges GTK 4 resizes from outside the window. */
static void
add_box_shadow (GString *css, const WindowFrame *frame, gboolean focused, const char *bar)
{
  int size = focused || frame->shadow_inactive < 0 ? frame->shadow : frame->shadow_inactive;
  double unit = (size < 0 ? UNIT : size) / UNIT;
  double dark = (focused ? frame->strength : frame->strength_inactive) / 100.0;
  int border = frame->border;

  g_string_append (css, "  box-shadow: ");
  if (border > 0)
    add_sides (css, border, bar);
  if (unit == 0 || dark == 0)
    {
      g_string_append (css, "0 0 0 20px transparent;\n");
      return;
    }
  if (focused)
    {
      add_shadow (css, 14 * unit, 5 * unit + border, 0.15 * dark, TRUE);
      add_shadow (css, 5 * unit, 2 * unit + border, 0.1 * dark, TRUE);
    }
  else
    add_shadow (css, 10 * unit, 5 * unit + border, 0.08 * dark, TRUE);
  add_shadow (css, 0, 1 + border, 0.05 * dark, FALSE);
  g_string_append (css, ";\n");
}

/* A window's own outline, never maximised, fullscreen, tiled or drawn
 * without a compositor: those keep the theme's square edges. */
#define FREE_WINDOW                                                                              \
  ".csd:not(.popup):not(.maximized):not(.fullscreen):not(.tiled):not(.tiled-top)"               \
  ":not(.tiled-right):not(.tiled-bottom):not(.tiled-left):not(.solid-csd)"

/* GTK 3 names a dialog's toplevel after its class. */
static const char *const gtk3_toplevels[] = { "window", "dialog", "messagedialog", "assistant",
                                              NULL };

/* `toplevel` and `suffix` for each GTK 3 toplevel, or for GTK 4's window. */
static void
add_selectors (GString *css, gboolean gtk4, const char *suffix)
{
  if (gtk4)
    {
      g_string_append_printf (css, "window" FREE_WINDOW "%s", suffix);
      return;
    }
  for (const char *const *toplevel = gtk3_toplevels; *toplevel != NULL; toplevel++)
    g_string_append_printf (css, "%s%s" FREE_WINDOW "%s", toplevel == gtk3_toplevels ? "" : ",\n",
                            *toplevel, suffix);
}

char *
window_frame_css (const WindowFrame *frame, gboolean gtk4)
{
  GString *css = g_string_new (NULL);
  gboolean round = !frame->square && frame->radius >= 0;
  gboolean shadow = frame->shadow >= 0 || frame->shadow_inactive >= 0 || frame->strength != 100
                     || frame->strength_inactive != 100 || frame->border > 0;
  const char *node = gtk4 ? "" : " > decoration";

  if (round)
    {
      add_selectors (css, gtk4, node);
      if (gtk4)
        g_string_append_printf (css, " {\n  --window-radius: %dpx;\n}\n", frame->radius);
      else
        {
          g_string_append_printf (css, " {\n  border-radius: %dpx %dpx 0 0;\n}\n", frame->radius,
                                  frame->radius);
          add_selectors (css, gtk4, " > .titlebar");
          g_string_append_printf (css,
                                  " {\n  border-top-left-radius: %dpx;\n"
                                  "  border-top-right-radius: %dpx;\n}\n",
                                  frame->radius, frame->radius);
        }
    }
  if (shadow)
    {
      add_selectors (css, gtk4, node);
      g_string_append (css, " {\n");
      add_box_shadow (css, frame, TRUE,
                      gtk4 ? "var(--headerbar-bg-color)" : "@headerbar_bg_color");
      g_string_append (css, "}\n");
      add_selectors (css, gtk4, gtk4 ? ":backdrop" : ":backdrop > decoration");
      g_string_append (css, " {\n");
      add_box_shadow (css, frame, FALSE,
                      gtk4 ? "var(--headerbar-backdrop-color)" : "@headerbar_backdrop_color");
      g_string_append (css, "}\n");
    }
  return g_string_free (css, FALSE);
}
