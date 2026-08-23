# Shell Runtime Baseline

Captured: 2026-08-23

This directory is the visual and runtime reference for incremental compatibility
engine extraction. It does not define new behavior.

## Environments

| Target | Shell | Session | Resolution | Result |
|---|---|---|---:|---|
| GNOME 50 | 50.4 | Wayland | 1280x800 | 12 references and 8 transitions passed |
| GNOME 51 | 51 beta | Wayland | 1280x800 | 12 references and 8 transitions passed |

Each target contains:

- `screenshots/`: six layouts in light and dark mode;
- `data/`: strict live-audit snapshots for the 12 reference states;
- `transitions/`: the clean-session transition matrix.

## Surface measurements

Actor boxes are Shell allocations. A full-edge Dock allocation may be wider
than its visible content. Minimal intentionally has no managed surface actor.

| Layout | GNOME 50 actor | GNOME 51 actor | Edge | Indicator |
|---|---:|---:|---|---|
| BigGnome | 368x57 | 1280x53 | bottom | Desk UX |
| G-Unity | 57x771 | 57x771 | left | dot |
| Hybrid | 1280x38 | 1280x46 | bottom | Hybrid |
| Desk UX | 1280x46 | 1280x46 | bottom | Desk UX |
| Classic | 1280x38 | 1280x46 | bottom | none |
| Minimal | none | none | top/native | none |

Accepted indicator geometry:

| Style | Inactive | Active | Radius |
|---|---:|---:|---:|
| dot | 6x6 | 6x6 | 99 px |
| Hybrid | 18x4 | 18x4 | 2 px |
| Desk UX | 8x3 | 18x3 | 2 px |

Accepted Taskbar spacing remains fixed and is not user-configurable:

| Layout | Icon margin | Icon padding |
|---|---:|---:|
| Hybrid | 0 px | 1 px |
| Desk UX | 0 px | 2 px |
| Classic | 2 px | 2 px |

BigGnome and G-Unity use the compatibility Dock's accepted internal spacing
with a 39 px maximum icon size.

## Transition coverage

Both Shell versions passed these clean-session transitions:

1. Dock to Dock: BigGnome to G-Unity.
2. Dock to Taskbar: G-Unity to Hybrid.
3. Taskbar to Dock: Hybrid to BigGnome.
4. Taskbar to Taskbar: Hybrid to Desk UX.
5. Native to Dock: Minimal to BigGnome.
6. Dock to native: BigGnome to Minimal.
7. Native to Taskbar: Minimal to Classic.
8. Taskbar to native: Classic to Minimal.

The audit rejects parallel runtime UUIDs, inactive helper/runtime extensions,
unexpected surface actors, stage residue, duplicate monitor actors, invalid
geometry, wrong edge, wrong original-layout indicator, menu drift, and desktop
icon drift.

## Deployment checksums

The local tree and both test VMs matched before capture:

| Payload | SHA-256 tree hash |
|---|---|
| Community Dock engine | `15c556efe553d3a83e99b9957c38a4829d7a1aa1d3f51c78fb865cbffaf1d827` |
| Community Panel engine | `5dc54d2cf64fc0a441305566adefc39344b4852d53192a85cfebbee4f7f7c6d7` |
| Layout Switcher Helper | `da9b44721d28e905444a286edee9a0fb87b6fb95e793b1774911d00e5c185b66` |
| Layout Switcher Runtime | `c8c716a6bc0adef0f019977c557e1d178dad06f402fbcd2ece1db9fdb8d3b522` |
| Runtime audit | `70bdfe1b9d37528ee26c1241b4a341e50a974897315ffda27ed9a32116011591` |
| Baseline runner | `fed2f3f958cda6ec29ffe0307fa1e3ee30aab4881be62794886feb928aba895a` |

Recompute source hashes with:

```bash
layout-switcher-runtime-audit --hashes-only
```
