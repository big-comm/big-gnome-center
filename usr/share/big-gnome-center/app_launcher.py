# SPDX-License-Identifier: MIT
"""Nonblocking GUI launches and bounded preparation commands."""

import logging
import shutil
from typing import Callable, Optional

from gi.repository import Gio, GLib

log = logging.getLogger("big-gnome-center")
ErrorCallback = Optional[Callable[[str], None]]


def report_launch_error(detail: str, on_error: ErrorCallback = None) -> None:
    log.warning("launch failed: %s", detail)
    if on_error is not None:
        on_error(detail)


def launch_command(
    argv: list[str],
    on_error: ErrorCallback = None,
    *,
    on_success: Optional[Callable[[], None]] = None,
    timeout: int = 0,
) -> None:
    """Observe exit asynchronously. Only preparation commands use a timeout."""
    try:
        process = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_SILENCE)
    except GLib.Error as exc:
        report_launch_error(str(exc), on_error)
        return

    timer = 0
    expired = False

    def expire() -> bool:
        nonlocal timer, expired
        timer = 0
        expired = True
        process.force_exit()
        report_launch_error(f"{argv[0]}: timed out after {timeout}s", on_error)
        return GLib.SOURCE_REMOVE

    def finished(child, result) -> None:
        nonlocal timer
        if timer:
            GLib.source_remove(timer)
            timer = 0
        try:
            child.wait_check_finish(result)
        except GLib.Error as exc:
            if not expired:
                report_launch_error(f"{argv[0]}: {exc}", on_error)
            return
        if not expired and on_success is not None:
            on_success()

    process.wait_check_async(None, finished)
    if timeout:
        timer = GLib.timeout_add_seconds(timeout, expire)


def launch_uri(uri: str, on_error: ErrorCallback = None) -> None:
    """Let GIO activate the default handler without waiting for its exit."""
    def finished(source, result) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri_finish(result)
        except GLib.Error as exc:
            report_launch_error(str(exc), on_error)

    try:
        Gio.AppInfo.launch_default_for_uri_async(uri, None, None, finished)
    except GLib.Error as exc:
        report_launch_error(str(exc), on_error)


def launch_extensions_app(on_error: ErrorCallback = None) -> None:
    """Try installed managers, then the website, only after a real failure."""
    candidates = iter(("gnome-extensions-app", "gnome-shell-extension-prefs"))

    def next_candidate(detail=None) -> None:
        for command in candidates:
            if shutil.which(command):
                launch_command([command], next_candidate)
                return
        launch_uri("https://extensions.gnome.org", on_error)

    next_candidate()
