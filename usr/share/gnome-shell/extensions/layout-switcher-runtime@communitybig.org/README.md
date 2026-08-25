# Layout Switcher Shell Runtime

Unified GNOME Shell controller for the six supported Layout Switcher profiles.

The controller is active and selects Dock, Taskbar, or native GNOME behavior
from the current layout. Dock actor construction and lifecycle are owned here.
The accepted Community Panel engine remains an internal compatibility module
while its behavior is extracted incrementally. Standalone compatibility UUIDs
are not enabled by layout files.

This extension has no preferences window. User-facing settings belong to the
Layout Switcher application.
