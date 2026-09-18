# SPDX-License-Identifier: MIT
"""Concurrent cache publication and failed-write recovery."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import ego_cache
import google_fonts


@pytest.fixture(params=["ego-json", "fonts", "thumbnail"])
def cache_writer(request, tmp_path, monkeypatch):
    kind = request.param
    if kind == "ego-json":
        monkeypatch.setattr(ego_cache, "EGO_CACHE_DIR", tmp_path)
        target = tmp_path / "info" / f"{ego_cache._hash_key('test')}.json"

        def write(index):
            ego_cache.json_put("info", "test", {"name": f"item-{index}", "data": "x" * 5000})
    elif kind == "fonts":
        target = tmp_path / "fonts.json"
        monkeypatch.setattr(google_fonts, "CACHE_FILE", target)

        def write(index):
            google_fonts._write_cached_catalog([google_fonts.FontFamily(f"Font {index}", "serif")])
    else:
        monkeypatch.setattr(ego_cache, "EGO_THUMBS_DIR", tmp_path)
        target = ego_cache.thumb_path("https://example.org/test.png")

        def write(index):
            return ego_cache.thumb_put("https://example.org/test.png", bytes([index + 1]) * 5000)

    write(0)
    assert target.is_file()
    return target, write


def test_concurrent_writers_publish_independent_complete_files(cache_writer, monkeypatch):
    target, write = cache_writer
    previous = target.read_bytes()
    count = 8
    barrier = threading.Barrier(count)
    lock = threading.Lock()
    sources, published, contents = [], [], []
    replace = os.replace

    def coordinated(source, destination):
        if Path(destination) != target:
            return replace(source, destination)
        with lock:
            sources.append(Path(source))
            contents.append(Path(source).read_bytes())
        # Every writer has finished its temporary file; the old cache is still complete.
        assert target.read_bytes() == previous
        barrier.wait(timeout=5)
        replace(source, destination)
        with lock:
            published.append(Path(source))

    monkeypatch.setattr(os, "replace", coordinated)
    with ThreadPoolExecutor(max_workers=count) as pool:
        list(pool.map(write, range(1, count + 1)))
    assert len(set(sources)) == count
    assert len(published) == count
    assert len(set(contents)) == count
    assert target.read_bytes() in contents
    assert list(target.parent.iterdir()) == [target]


def test_failed_publication_keeps_previous_cache_and_cleans_temporary(cache_writer, monkeypatch):
    target, write = cache_writer
    previous = target.read_bytes()

    def fail_replace(source, destination):
        raise OSError("injected publication failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    write(1)
    assert target.read_bytes() == previous
    assert list(target.parent.iterdir()) == [target]


def test_eviction_never_removes_in_progress_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setattr(ego_cache, "EGO_THUMBS_DIR", tmp_path)
    monkeypatch.setattr(ego_cache, "EGO_THUMBS_MAX_BYTES", 100)
    cached = tmp_path / "cached.png"
    cached.write_bytes(b"c" * 100)
    private = tmp_path / ".next.png.private.tmp"
    private.write_bytes(b"p" * 500)
    ego_cache._evict_thumbs_if_needed()
    assert private.read_bytes() == b"p" * 500
    assert cached.read_bytes() == b"c" * 100


def test_invalid_json_write_preserves_cache_without_partial_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ego_cache, "EGO_CACHE_DIR", tmp_path)
    ego_cache.json_put("info", "key", {"value": "previous"})
    target = next((tmp_path / "info").iterdir())
    previous = target.read_bytes()
    ego_cache.json_put("info", "key", {"value": object()})
    assert target.read_bytes() == previous
    assert list(target.parent.iterdir()) == [target]
