# SPDX-License-Identifier: MIT
"""Catalog validation through real HTTP and temporary disk caches."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import ego_cache
import ego_client
import google_fonts


@pytest.fixture
def catalog_server(tmp_path, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.requests.append(self.path)
            body = self.server.body
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # Expected when the client rejects an oversized response.

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.body = b"{}"
    server.requests = []
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(ego_client, "EGO_BASE_URL", base)
    monkeypatch.setattr(google_fonts, "CATALOG_URL", base + "/fonts")
    monkeypatch.setattr(ego_cache, "EGO_CACHE_DIR", tmp_path / "ego")
    monkeypatch.setattr(google_fonts, "CACHE_FILE", tmp_path / "fonts.json")
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


@pytest.mark.parametrize("body", [
    b"not JSON", b"[]", b'{"extensions":false}',
    b'{"nested":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}",
    b'{"number":' + b"9" * 5000 + b"}",
], ids=["syntax", "array", "wrong-field", "deep-nesting", "huge-integer"])
def test_real_http_invalid_payloads_fail_without_losing_font_cache(catalog_server, body):
    catalog_server.body = body
    assert ego_client.search("test", use_cache=False) is None
    assert ego_client.info("test@example.org", use_cache=False) is None
    saved = [google_fonts.FontFamily("Saved", "serif")]
    google_fonts._write_cached_catalog(saved)
    before = google_fonts.CACHE_FILE.read_bytes()
    ok, entries, error = google_fonts.load_catalog(force_refresh=True)
    assert ok and not error and entries == saved
    assert google_fonts.CACHE_FILE.read_bytes() == before
    assert len(catalog_server.requests) == 3


def test_real_http_filters_entries_and_then_uses_cache(catalog_server):
    catalog_server.body = json.dumps({"extensions": [
        False, ["invalid"], {"uuid": "test@example.org", "name": "Valid", "rating": []},
    ], "page": 1, "numpages": "bad"}).encode()
    result = ego_client.search("Valid")
    assert result is not None and result.extensions[0].name == "Valid"
    assert result.extensions[0].rating == 0
    assert result.num_pages == 1
    catalog_server.body = b"unavailable"
    assert ego_client.search("Valid") == result
    assert len(catalog_server.requests) == 1


def test_real_http_detail_sanitizes_metadata_without_guessing_compatibility(catalog_server):
    catalog_server.body = json.dumps({
        "uuid": "test@example.org", "name": {}, "screenshots": [None, {"url": 4}],
        "comments": [{"text": 5}, {"text": "Valid", "rating": "NaN"}],
        "shell_version_map": ["50", "51"],
    }).encode()
    detail = ego_client.info("test@example.org")
    assert detail.name == "test@example.org"
    assert detail.screenshots == [] and detail.comments[0].text == "Valid"
    assert ego_client.version_from_info(detail, "50") is None
    assert ego_client.version_from_info(detail, "51") is None


def test_real_http_font_catalog_keeps_valid_entries(catalog_server):
    catalog_server.body = json.dumps({"familyMetadataList": [
        False, {"family": 5}, {"family": "Valid", "category": [], "popularity": {}},
    ]}).encode()
    ok, entries, error = google_fonts.load_catalog(force_refresh=True)
    assert ok and not error
    assert entries == [google_fonts.FontFamily("Valid", "sans-serif")]
    assert google_fonts._read_cached_catalog(True) == entries


def test_real_http_caps_remain_enforced(catalog_server, monkeypatch):
    monkeypatch.setattr(ego_client, "_MAX_JSON_BYTES", 64)
    monkeypatch.setattr(google_fonts, "MAX_CATALOG_BYTES", 64)
    catalog_server.body = json.dumps({"uuid": "test@example.org", "name": "x" * 128}).encode()
    assert ego_client.info("test@example.org", use_cache=False) is None
    catalog_server.body = json.dumps({"items": [{"family": "x" * 128}]}).encode()
    ok, entries, error = google_fonts.load_catalog(force_refresh=True)
    assert not ok and error == "too-large"
    assert entries == google_fonts.fallback_catalog()
    assert not google_fonts.CACHE_FILE.exists()
