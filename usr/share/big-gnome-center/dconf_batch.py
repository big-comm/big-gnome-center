#!/usr/bin/python
"""Apply validated dconf resets and an optional keyfile in one worker."""

import argparse
import ctypes
import ctypes.util
import re
import subprocess
import sys
from pathlib import Path

TREE_RE = re.compile(r"^/org/gnome/shell/extensions/[A-Za-z0-9_-]+/$")
KEY_RE = re.compile(r"^/[A-Za-z0-9_./-]+$")


def _run(arguments, *, text=None):
    result = subprocess.run(
        ["dconf", *arguments],
        input=text,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "dconf command failed")
    return result.stdout


class _GError(ctypes.Structure):
    _fields_ = [
        ("domain", ctypes.c_uint),
        ("code", ctypes.c_int),
        ("message", ctypes.c_char_p),
    ]


def _parse_keyfile(text):
    values = {}
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip("/")
            continue
        key, separator, value = line.partition("=")
        if section is None or not separator or not key.strip():
            raise ValueError("invalid dconf keyfile")
        path = "/" + "/".join(part for part in (section, key.strip()) if part)
        if not KEY_RE.fullmatch(path):
            raise ValueError(f"invalid dconf key: {path}")
        values[path] = value.strip()
    return values


def _atomic_change(resets, values):
    """Commit resets and writes as one libdconf changeset."""
    dconf = ctypes.CDLL(ctypes.util.find_library("dconf") or "libdconf.so.1")
    glib = ctypes.CDLL(ctypes.util.find_library("glib-2.0") or "libglib-2.0.so.0")
    gobject = ctypes.CDLL(
        ctypes.util.find_library("gobject-2.0") or "libgobject-2.0.so.0"
    )

    dconf.dconf_changeset_new.restype = ctypes.c_void_p
    dconf.dconf_changeset_set.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    dconf.dconf_changeset_unref.argtypes = [ctypes.c_void_p]
    dconf.dconf_client_new.restype = ctypes.c_void_p
    dconf.dconf_client_change_sync.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_char_p),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    dconf.dconf_client_change_sync.restype = ctypes.c_int
    glib.g_variant_parse.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    glib.g_variant_parse.restype = ctypes.c_void_p
    glib.g_error_free.argtypes = [ctypes.c_void_p]
    glib.g_free.argtypes = [ctypes.c_void_p]
    gobject.g_object_unref.argtypes = [ctypes.c_void_p]

    changeset = dconf.dconf_changeset_new()
    client = dconf.dconf_client_new()
    if not changeset or not client:
        raise RuntimeError("cannot allocate dconf changeset")

    try:
        for path in resets:
            dconf.dconf_changeset_set(changeset, path.encode(), None)
        for path, serialized in values.items():
            error = ctypes.c_void_p()
            variant = glib.g_variant_parse(
                None, serialized.encode(), None, None, ctypes.byref(error)
            )
            if not variant:
                message = "invalid GVariant"
                if error.value:
                    detail = ctypes.cast(error, ctypes.POINTER(_GError)).contents
                    message = detail.message.decode(errors="replace")
                    glib.g_error_free(error)
                raise ValueError(f"{path}: {message}")
            dconf.dconf_changeset_set(changeset, path.encode(), variant)

        tag = ctypes.c_char_p()
        error = ctypes.c_void_p()
        changed = dconf.dconf_client_change_sync(
            client, changeset, ctypes.byref(tag), None, ctypes.byref(error)
        )
        if tag:
            glib.g_free(tag)
        if not changed:
            message = "dconf changeset failed"
            if error.value:
                detail = ctypes.cast(error, ctypes.POINTER(_GError)).contents
                message = detail.message.decode(errors="replace")
                glib.g_error_free(error)
            raise RuntimeError(message)
    finally:
        dconf.dconf_changeset_unref(changeset)
        gobject.g_object_unref(client)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset-tree", action="append", default=[])
    parser.add_argument("--reset", action="append", default=[])
    parser.add_argument("--input-file")
    parser.add_argument("--dump-output")
    args = parser.parse_args(argv)

    if any(not TREE_RE.fullmatch(path) for path in args.reset_tree):
        parser.error("invalid reset tree")
    if any(not KEY_RE.fullmatch(path) for path in args.reset):
        parser.error("invalid reset key")

    if args.dump_output:
        if args.reset_tree or args.reset or args.input_file:
            parser.error("dump cannot be combined with mutation")
        Path(args.dump_output).write_text(_run(("dump", "/")), encoding="utf-8")
        return 0

    keyfile = (
        Path(args.input_file).read_text(encoding="utf-8")
        if args.input_file
        else sys.stdin.read()
    )
    values = _parse_keyfile(keyfile)
    _atomic_change([*args.reset_tree, *args.reset], values)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"dconf batch: {error}", file=sys.stderr)
        raise SystemExit(1)
