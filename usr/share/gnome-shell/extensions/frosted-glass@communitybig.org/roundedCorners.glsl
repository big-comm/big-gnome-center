// SPDX-License-Identifier: GPL-3.0-or-later
// Adapted from Blur My Shell and yilozt/rounded-window-corners.

uniform sampler2D tex;
uniform float radius;
uniform float width;
uniform float height;

float circle_bounds(vec2 point, vec2 center, float clip_radius) {
    vec2 delta = point - center;
    float distance_squared = dot(delta, delta);
    float outer_radius = clip_radius + 0.5;
    if (distance_squared >= outer_radius * outer_radius)
        return 0.0;

    float inner_radius = clip_radius - 0.5;
    if (distance_squared <= inner_radius * inner_radius)
        return 1.0;

    return outer_radius - sqrt(distance_squared);
}

float rounded_rect_coverage(vec2 point) {
    vec2 center;
    float center_left = radius;
    float center_right = width - radius;

    if (point.x < center_left)
        center.x = center_left + 2.0;
    else if (point.x > center_right)
        center.x = center_right - 1.0;
    else
        return 1.0;

    float center_top = radius;
    float center_bottom = height - radius;
    if (point.y < center_top)
        center.y = center_top + 2.0;
    else if (point.y > center_bottom)
        center.y = center_bottom - 1.0;
    else
        return 1.0;

    return circle_bounds(point, center, radius);
}

vec4 get_texture(vec2 uv) {
    float safe_width = max(1.0, width);
    float safe_height = max(1.0, height);
    uv.x = clamp(uv.x, 2.0 / safe_width, 1.0 - 3.0 / safe_width);
    uv.y = clamp(uv.y, 2.0 / safe_height, 1.0 - 3.0 / safe_height);
    return texture2D(tex, uv);
}

void main(void) {
    vec2 uv = cogl_tex_coord_in[0].xy;
    vec4 color = get_texture(uv);
    float coverage = radius > 0.0
        ? rounded_rect_coverage(uv * vec2(width, height))
        : 1.0;
    cogl_color_out = vec4(
        color.rgb * coverage,
        min(coverage, color.a));
}
