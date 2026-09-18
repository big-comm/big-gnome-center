# Legacy session migration

The package replaces Layout Switcher; per-user extension identities migrate
before GNOME Shell starts through a systemd `ExecStartPre` drop-in. This uses the
existing [GNOME Shell service](https://gitlab.gnome.org/GNOME/gnome-shell/-/blob/50.4/data/org.gnome.Shell%40.service.in),
not a live helper reload. The bounded, fail-open command skips GDM and refuses
to run if the session bus already has a Shell owner.

- Rename helper, Community Menu and Big Shot UUIDs only when replacements exist.
- Preserve enabled/disabled intent, unrelated extensions and all layout settings.
- Migrate committed `settings.gnome` generations under the shared persistence
  lock. Preserve next-login staging and defer migration during pending recovery.
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

## Persistence coordination

Requires comm-gnome-config persistence protocol 1. Deploy both packages together
and reopen the GTK application after updating Python modules. Before each apply,
refresh the existing dconf sync service under the writer lock; never restart the
graphical session. A failed refresh stops the operation before file/live writes.

The text export remains `~/.config/dconf/settings.gnome`. Its adjacent state JSON
holds three checksummed text generations and an application journal. Failed or
interrupted applications quarantine automatic saves until successful reapplication
or the next pre-Shell login. This preserves the last confirmed snapshot; it does
not promise automatic visual recovery of partially disabled extensions.

Direct text edits require explicit validation/import for the next login:

```sh
python /usr/share/comm-gnome-config/dconf_persistence.py import /path/to/reviewed-settings.txt
```

See comm-gnome-config's `docs/DCONF_PERSISTENCE.md` for commit ordering, backup
recovery, deployment and failure boundaries. Keep the whole dconf directory when
backing up generation history. Never run its login reset command in a live Shell.
