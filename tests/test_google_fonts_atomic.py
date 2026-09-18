# SPDX-License-Identifier: MIT
"""Whole-family publication, failure recovery and serialization."""

import errno
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import google_fonts as fonts


@pytest.fixture(autouse=True)
def isolated_font_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(fonts, "FONT_STAGING_DIR", tmp_path / "staging")


@pytest.fixture
def installer(tmp_path, monkeypatch):
    root = tmp_path / "fonts"
    root.mkdir()
    monkeypatch.setattr(fonts, "USER_FONT_DIR", root)
    monkeypatch.setattr(fonts, "_fetch_css", lambda family: " ".join(
        f"url(https://fonts.gstatic.com/{name}.ttf)" for name in ("regular", "bold")
    ))
    monkeypatch.setattr(fonts, "_download_font", lambda url: Path(url).stem.encode())
    monkeypatch.setattr(fonts, "run_cmd", lambda *args, **kwargs: (True, "Family"))
    return root


def seed(root):
    dest = root / "family"
    dest.mkdir()
    for name in ("regular.ttf", "bold.ttf", "notes.txt"):
        (dest / name).write_bytes(b"old " + name.encode())
    return dest


def contents(dest):
    return {p.name: p.read_bytes() for p in dest.iterdir()} if dest.exists() else None


def assert_no_staging(root):
    assert not list(fonts.FONT_STAGING_DIR.glob(".family-*"))


def test_update_publishes_all_fonts_and_preserves_other_files(installer):
    dest = seed(installer)
    assert fonts.install_for_user("Family") == (True, str(dest))
    assert contents(dest) == {
        "regular.ttf": b"regular", "bold.ttf": b"bold", "notes.txt": b"old notes.txt"
    }
    assert_no_staging(installer)


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    "failure", ["empty", "invalid", "scan-empty", "write", "sync", "publish", "cache"]
)
def test_failed_install_leaves_previous_family(installer, monkeypatch, existing, failure):
    dest = seed(installer) if existing else installer / "family"
    before = contents(dest)
    if failure == "empty":
        monkeypatch.setattr(fonts, "_download_font", lambda url: b"")
    elif failure in ("invalid", "scan-empty", "cache"):
        def run(args, **kwargs):
            if failure == "scan-empty" and args[0] == "fc-scan":
                return True, ""
            failed = args[0] == ("fc-cache" if failure == "cache" else "fc-scan")
            return not failed, "invalid" if failed else "Family"
        monkeypatch.setattr(fonts, "run_cmd", run)
    elif failure == "write":
        original_open = Path.open
        def fail_write(path, mode="r", *args, **kwargs):
            if mode == "wb" and path.name == "bold.ttf":
                raise OSError(errno.ENOSPC, "Full disk")
            return original_open(path, mode, *args, **kwargs)
        monkeypatch.setattr(Path, "open", fail_write)
    elif failure == "sync":
        def fail_sync(path):
            raise OSError(errno.EIO, "fsync failed")
        monkeypatch.setattr(fonts, "_sync_directory", fail_sync)
    elif failure == "publish":
        def fail_publish(*args, **kwargs):
            raise OSError(errno.EOPNOTSUPP, "Atomic exchange unavailable")
        monkeypatch.setattr(fonts, "_rename_family", fail_publish)
    ok, code = fonts.install_for_user("Family")
    assert not ok
    download_error = failure in ("empty", "invalid", "scan-empty")
    assert code == ("download-failed" if download_error else "write-failed")
    assert contents(dest) == before
    assert_no_staging(installer)


def test_sync_failure_after_publication_rolls_back(installer, monkeypatch):
    dest = seed(installer)
    before = contents(dest)
    original_sync = fonts._sync_directory
    failed = False
    def sync(path):
        nonlocal failed
        if path == installer and not failed:
            failed = True
            raise OSError(errno.EIO, "Publication sync failed")
        original_sync(path)
    monkeypatch.setattr(fonts, "_sync_directory", sync)
    assert fonts.install_for_user("Family") == (False, "write-failed")
    assert contents(dest) == before
    assert_no_staging(installer)


def test_failed_rollback_retains_recovery_copy(installer, monkeypatch):
    dest = seed(installer)
    before = contents(dest)
    original_rename = fonts._rename_family
    calls = 0
    def rename(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError(errno.EIO, "Rollback unavailable")
        original_rename(*args, **kwargs)
    monkeypatch.setattr(fonts, "_rename_family", rename)
    monkeypatch.setattr(fonts, "run_cmd", lambda args, **kwargs: (args[0] != "fc-cache", "Family"))
    assert fonts.install_for_user("Family") == (False, "write-failed")
    backups = list(fonts.FONT_STAGING_DIR.glob(".family-*/family"))
    assert len(backups) == 1
    assert contents(backups[0]) == before
    assert (dest / "regular.ttf").read_bytes() == b"regular"
    assert (dest / "bold.ttf").read_bytes() == b"bold"


def test_distinct_urls_with_same_basename_are_not_lost(installer, monkeypatch):
    monkeypatch.setattr(fonts, "_fetch_css", lambda family: " ".join(
        f"url(https://fonts.gstatic.com/{subset}/font.ttf)" for subset in ("latin", "greek")
    ))
    monkeypatch.setattr(fonts, "_download_font", lambda url: Path(url).parent.name.encode())
    assert fonts.install_for_user("Family")[0]
    assert set(contents(installer / "family").values()) == {b"latin", b"greek"}


@pytest.mark.parametrize("family", [".", ".."])
def test_dot_family_cannot_replace_parent(installer, family):
    assert fonts.install_for_user(family) == (False, "write-failed")
    assert list(installer.iterdir()) == []


def test_symlink_family_is_not_followed(installer, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "regular.ttf").write_bytes(b"external")
    (installer / "family").symlink_to(outside, target_is_directory=True)
    assert fonts.install_for_user("Family") == (False, "write-failed")
    assert contents(outside) == {"regular.ttf": b"external"}


def test_symlink_font_does_not_overwrite_external_target(installer, tmp_path):
    outside = tmp_path / "external.ttf"
    outside.write_bytes(b"external")
    dest = seed(installer)
    (dest / "regular.ttf").unlink()
    (dest / "regular.ttf").symlink_to(outside)
    assert fonts.install_for_user("Family")[0]
    assert outside.read_bytes() == b"external"
    assert not (dest / "regular.ttf").is_symlink()


def test_same_family_serializes_but_other_families_can_install(installer, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    second_started = threading.Event()
    calls = []
    original_css = fonts._fetch_css
    def css(family):
        calls.append(family)
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
        return original_css(family)
    def second():
        second_started.set()
        return fonts.install_for_user("Family")
    monkeypatch.setattr(fonts, "_fetch_css", css)
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(fonts.install_for_user, "Family")
        try:
            assert entered.wait(5)
            waiting = pool.submit(second)
            assert second_started.wait(5)
            assert pool.submit(fonts.install_for_user, "Other").result(timeout=5)[0]
            assert calls == ["Family", "Other"]
        finally:
            release.set()
        assert first.result(timeout=5)[0]
        assert waiting.result(timeout=5)[0]
    assert calls == ["Family", "Other", "Family"]


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("crash_at", ["download", "published"])
def test_process_exit_leaves_complete_family_and_releases_lock(installer, existing, crash_at):
    dest = seed(installer) if existing else installer / "family"
    before = contents(dest)
    script = '''
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import google_fonts as f
f.USER_FONT_DIR = Path(sys.argv[2])
f.FONT_STAGING_DIR = f.USER_FONT_DIR.parent / 'staging'
f._fetch_css = lambda family: 'url(https://fonts.gstatic.com/regular.ttf) url(https://fonts.gstatic.com/bold.ttf)'
def download(url):
    if sys.argv[3] == 'download' and 'bold' in url:
        os._exit(81)
    return Path(url).stem.encode()
f._download_font = download
def run(args, **kwargs):
    if sys.argv[3] == 'published' and args[0] == 'fc-cache':
        os._exit(81)
    return True, 'Family'
f.run_cmd = run
f.install_for_user('Family')
'''
    result = subprocess.run([sys.executable, "-c", script, str(Path(fonts.__file__).parent),
                             str(installer), crash_at], timeout=15, capture_output=True)
    assert result.returncode == 81, result.stderr.decode()
    if crash_at == "download":
        assert contents(dest) == before
    else:
        assert (dest / "regular.ttf").read_bytes() == b"regular"
        assert (dest / "bold.ttf").read_bytes() == b"bold"
    # A new process must acquire the lock left by the terminated writer.
    result = subprocess.run([sys.executable, "-c", script, str(Path(fonts.__file__).parent),
                             str(installer), "none"], timeout=15, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert (dest / "bold.ttf").read_bytes() == b"bold"


def test_native_fontconfig_validation_and_hidden_staging(tmp_path, monkeypatch):
    for command in ("fc-match", "fc-scan", "fc-cache", "fc-list"):
        if not shutil.which(command):
            pytest.skip(f"Requires {command}")
    match = subprocess.run(["fc-match", "--format", "%{file}", "sans-serif"],
                           check=True, capture_output=True, text=True).stdout
    if not match or not Path(match).is_file():
        pytest.skip("Requires a system font")
    data = Path(match).read_bytes()
    root = tmp_path / "fonts"
    cache = tmp_path / "cache"
    config = tmp_path / "fonts.conf"
    config.write_text(f'<fontconfig><dir>{root}</dir><cachedir>{cache}</cachedir></fontconfig>')
    monkeypatch.setenv("FONTCONFIG_FILE", str(config))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    monkeypatch.setattr(fonts, "USER_FONT_DIR", root)
    monkeypatch.setattr(fonts, "_fetch_css", lambda family: "url(https://fonts.gstatic.com/real.ttf)")
    monkeypatch.setattr(fonts, "_download_font", lambda url: data)
    assert fonts.install_for_user("Native")[0]
    dest = root / "native" / "real.ttf"
    hidden = fonts.FONT_STAGING_DIR / ".interrupted" / "family"
    hidden.mkdir(parents=True)
    (hidden / "partial.ttf").write_bytes(data)
    subprocess.run(["fc-cache", "-f", str(root)], check=True, capture_output=True)
    discovered = subprocess.run(["fc-list", "--format", "%{file}\n"], check=True,
                                capture_output=True, text=True).stdout.splitlines()
    assert str(dest) in discovered
    assert not any(".interrupted" in name for name in discovered)
    monkeypatch.setattr(fonts, "_download_font", lambda url: b"not a font")
    assert fonts.install_for_user("Native") == (False, "download-failed")
    assert dest.read_bytes() == data
