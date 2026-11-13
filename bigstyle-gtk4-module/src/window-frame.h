/* big-compositor's window frame, as the `config.toml` it watches and applies
 * at once sets it, shared by the GTK 4 module and the GTK 3 module. The
 * compositor draws its frame (square corners, shadow, sides) around the
 * windows it decorates; each module gives its windows, which draw their own,
 * the same with a stylesheet above every other: the square outline BigStyle
 * writes beside its stylesheet, and the radius, shadow and border read here
 * (`window_frame_css`). */

#pragma once

#include <gio/gio.h>

typedef struct
{
  /* `[effects] reduced`, or `[decorations] square_corners = "always"`. */
  gboolean square;
  /* `[decorations] corner_radius`, -1 where the file does not set it. */
  int radius;
  /* `[decorations] shadow_size`, the window in use's, and
   * `shadow_size_inactive`, the others'; 0 under reduced effects, -1 where
   * unset: the others' then follows the window in use's. */
  int shadow;
  int shadow_inactive;
  /* `shadow_strength` and `shadow_strength_inactive`, percent of
   * libadwaita's darkness, 100 where unset. */
  int strength;
  int strength_inactive;
  /* `[decorations] border_width`, at most 8. */
  int border;
} WindowFrame;

/* The frame in effect. Only in big-compositor's session: the keys are that
 * compositor's own, and under another the windows keep their theme's. */
const WindowFrame *window_frame (void);

/* Read the keys, then call `changed` whenever the frame changes, and whenever
 * `layer` is replaced while the windows are square. */
void window_frame_watch (GFile *layer, void (*changed) (void));

/* The stylesheet that rounds, shadows and edges the windows of GTK 4, or of
 * GTK 3, as `frame` says: nothing for what the file leaves unset, and no
 * radius for square windows. Freed by the caller. */
char *window_frame_css (const WindowFrame *frame, gboolean gtk4);
