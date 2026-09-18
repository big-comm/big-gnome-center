# SPDX-License-Identifier: MIT
"""
snapshot_manager.py — Snapshots personalizados por layout.

Replica o comportamento do KDE Plasma: cada layout tem um snapshot
dedicado ("sua versao modificada") que persiste quando o usuario troca
e volta. Ao retornar, o app oferece:

  * **Retomar** — carrega o snapshot salvo (modificacoes do usuario)
  * **Original** — carrega o arquivo padrao da distro (em ``layouts/``)

Os snapshots sao armazenados em
``~/.config/big-gnome-center/layout-snapshots/<layout_id>.dconf`` — formato
identico ao ``dconf dump /``.

``layout_id`` e o stem do arquivo de layout (ex.: ``"biggnome"`` para
``biggnome.txt``), estavel entre releases.

DEVELOPER NOTE - DO NOT name any variable `_` in this file.
"""

import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from gi.repository import GLib

from constants import CONFIG_DIR, LAYOUTS
from layout_persistence import SETTINGS_GNOME, open_store
from settings_store import Settings
from utils import atomic_write_text, run_cmd

log = logging.getLogger("big-gnome-center")

SNAPSHOTS_DIR = CONFIG_DIR / "layout-snapshots"
MIN_SNAPSHOT_BYTES = 100


class SnapshotManager:
    """Gerencia snapshots de layout (versoes modificadas pelo usuario)."""

    @staticmethod
    def _path_for(layout_id: str) -> Path:
        """Caminho do snapshot para um layout_id (ex.: 'biggnome')."""
        if not isinstance(layout_id, str) or not layout_id:
            raise ValueError("invalid layout_id")
        safe = "".join(
            c for c in layout_id.lower() if c in "abcdefghijklmnopqrstuvwxyz0123456789-_"
        )
        # Preserve canonical filenames; never alias lossy or oversized IDs.
        if safe != layout_id or not safe or len(safe) > 80:
            digest = hashlib.sha256(layout_id.encode("utf-8")).hexdigest()
            safe = f"{safe[:48] or 'layout'}.{digest}"
        return SNAPSHOTS_DIR / f"{safe}.dconf"

    # ── Save ─────────────────────────────────────────────────────────────────

    @classmethod
    def save(cls, layout_id: str) -> Tuple[bool, str]:
        """
        Salva o estado atual do dconf como snapshot do ``layout_id``.

        Retorna (True, caminho) em sucesso ou (False, mensagem_erro).
        Silencioso: falhas nao devem bloquear a troca de layout.
        """
        try:
            dest = cls._path_for(layout_id)
            store = open_store(SETTINGS_GNOME)
            # Same stable lock as layout application, autosave and login recovery.
            with store.lock():
                state = store.read()
                if state.get("transaction") or state.get("staged") or store.marker.exists():
                    return False, "snapshot paused: layout recovery or staging pending"
                prefs = Settings()
                if prefs.last_error:
                    return False, f"cannot read snapshot preferences: {prefs.last_error}"
                if prefs.get("last_apply_ok") is False or prefs.get("pending_layout"):
                    return False, "snapshot paused: previous layout application incomplete"
                ok, data = run_cmd(["dconf", "dump", "/"], timeout=15)
                if not ok:
                    return False, f"dconf dump failed: {data}"
                if not data or len(data.encode("utf-8")) < MIN_SNAPSHOT_BYTES:
                    return False, "dconf dump produced empty/tiny output"
                # A stale page must not save another layout under its old ID.
                keyfile = GLib.KeyFile()
                keyfile.load_from_data(data, len(data.encode("utf-8")), GLib.KeyFileFlags.NONE)
                group = "org/communitybig/layout-switcher/runtime"
                if keyfile.has_group(group):
                    keys = keyfile.get_keys(group)[0]
                    if "active-layout" in keys:
                        active = GLib.Variant.parse(
                            None, keyfile.get_value(group, "active-layout"), None, None
                        ).unpack()
                        expected = next(
                            (name for name, cfg, *rest in LAYOUTS if Path(cfg).stem == layout_id),
                            None,
                        )
                        if expected and active and active != expected:
                            return False, "snapshot paused: active layout changed"
                atomic_write_text(dest, data)
                log.debug("snapshot saved: %s (%d bytes)", dest, len(data.encode("utf-8")))
                return True, str(dest)
        except BlockingIOError:
            return False, "snapshot paused: a layout operation is already in progress"
        except Exception as exc:
            return False, f"snapshot failed: {exc}"

    # ── Load ─────────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, layout_id: str) -> Optional[Path]:
        """Retorna o Path do snapshot se existir e for valido; senao None."""
        if not layout_id:
            return None
        try:
            p = cls._path_for(layout_id)
            if p.is_file() and p.stat().st_size >= MIN_SNAPSHOT_BYTES:
                return p
        except Exception:
            pass
        return None

    @classmethod
    def has(cls, layout_id: str) -> bool:
        """True se existe snapshot valido para o layout."""
        return cls.load(layout_id) is not None

    @classmethod
    def read(cls, layout_id: str) -> Optional[str]:
        """Retorna o conteudo do snapshot ou None se ausente/invalido."""
        try:
            data = cls._path_for(layout_id).read_text(encoding="utf-8")
            return data if len(data.encode("utf-8")) >= MIN_SNAPSHOT_BYTES else None
        except Exception as exc:
            log.debug("snapshot read failed: %s -> %s", layout_id, exc)
            return None

    # ── Delete / list ────────────────────────────────────────────────────────

    @classmethod
    def delete(cls, layout_id: str) -> bool:
        """Remove o snapshot (idempotente)."""
        if not layout_id:
            return False
        try:
            path = cls._path_for(layout_id)
            with open_store(SETTINGS_GNOME).lock():
                path.unlink(missing_ok=True)
            return True
        except Exception as exc:
            log.debug("snapshot delete failed: %s", exc)
            return False

    @classmethod
    def list_all(cls) -> List[Path]:
        """Lista todos os snapshots existentes (mais recentes primeiro)."""
        try:
            SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            return sorted(
                [
                    p
                    for p in SNAPSHOTS_DIR.glob("*.dconf")
                    if p.stat().st_size >= MIN_SNAPSHOT_BYTES
                ],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            return []
