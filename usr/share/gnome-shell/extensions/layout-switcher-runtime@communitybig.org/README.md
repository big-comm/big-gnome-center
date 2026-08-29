# Layout Switcher Shell Runtime

Unified GNOME Shell controller for the six supported Layout Switcher profiles.

The controller selects Dock, Taskbar, or native GNOME behavior from the current
layout. Dock and Taskbar actors, lifecycle, and executable modules are owned
here. Standalone compatibility UUIDs are not enabled by layout files.

The runtime binds its local Dash to Dock 106 and Dash to Panel 73 gettext
catalogs before constructing either surface. Both domains cover all 29
supported locales.

This extension has no preferences window. User-facing settings belong to the
Layout Switcher application.
