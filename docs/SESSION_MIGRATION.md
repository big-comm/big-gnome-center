# Legacy session migration

The package replaces Layout Switcher; per-user extension identities migrate
before GNOME Shell starts through a systemd `ExecStartPre` drop-in. This uses the
existing [GNOME Shell service](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/50.4/data/org.gnome.Shell%40.service.in),
not a live helper reload. The bounded, fail-open command skips GDM and refuses
to run if the session bus already has a Shell owner.

- Rename helper, Community Menu and Big Shot UUIDs only when replacements exist.
- Preserve enabled/disabled intent, unrelated extensions and all layout settings.
- Migrate the persisted `settings.gnome` lists too, with the existing atomic
  writer and backup. Do not overwrite a separately staged layout with live data.
- Keep legacy dock/panel engines until explicit layout application: a UUID-only
  conversion to the new runtime would not preserve all custom layout settings.
- Keep the live-session guard conservative during package upgrades. Two helper
  implementations must never contend for the shared D-Bus object.

A layout staged during a legacy session is pending, not applied. The UI retains
the active card and blocks snapshots until the runtime confirms the pending
layout after login. No original layout is applied automatically.

Regression coverage: enabled/disabled and duplicate UUIDs, missing replacement,
idempotence, preference preservation, staged Classic preservation, backup,
live-Shell refusal, and pending-layout UI state.
