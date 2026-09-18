# SPDX-License-Identifier: MIT
"""Malformed remote/cache payloads must not escape into catalog consumers."""

import io
import json
import math
import time
from unittest.mock import Mock

import pytest

import ego_cache
import ego_client
import google_fonts

UUID = "valid@example.org"
INFO = {"uuid": UUID, "name": "Valid", "shell_version_map": {"50": {"version": 7}}}
QUERY = {"extensions": [INFO], "page": 1, "numpages": 2, "total": 1}


def response(payload):
    result = io.BytesIO(json.dumps(payload).encode())
    result.status = 200
    return result


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ego_cache, "EGO_CACHE_DIR", tmp_path / "ego")
    monkeypatch.setattr(google_fonts, "CACHE_FILE", tmp_path / "fonts.json")


@pytest.mark.parametrize("payload", [None, [], "unexpected", 7, True])
@pytest.mark.parametrize("endpoint", ["search", "info"])
def test_invalid_ego_envelope_is_not_cached(monkeypatch, payload, endpoint):
    fetch = Mock(return_value=response(payload))
    save = Mock()
    monkeypatch.setattr(ego_client.urllib.request, "urlopen", fetch)
    monkeypatch.setattr(ego_cache, "json_put", save)
    assert getattr(ego_client, endpoint)(UUID, use_cache=False) is None
    save.assert_not_called()


@pytest.mark.parametrize("endpoint,invalid,valid", [
    ("search", [], QUERY), ("search", {"extensions": {}}, QUERY),
    ("search", {"error": "unavailable"}, QUERY),
    ("info", [], INFO), ("info", {"uuid": [UUID]}, INFO),
    ("info", {"error": "unavailable"}, INFO),
])
def test_invalid_cache_retries_network_and_recovers(monkeypatch, endpoint, invalid, valid):
    if endpoint == "search":
        key = json.dumps({"search": UUID, "sort": "relevance", "page": "1",
                          "shell_version": "all"}, sort_keys=True)
    else:
        key = f"{UUID}|all"
    path = ego_cache._json_dir(endpoint) / f"{ego_cache._hash_key(key)}.json"
    path.write_text(json.dumps(invalid))
    fetch = Mock(return_value=response(valid))
    monkeypatch.setattr(ego_client.urllib.request, "urlopen", fetch)
    result = getattr(ego_client, endpoint)(UUID)
    assert result is not None
    fetch.assert_called_once()
    assert json.loads(path.read_text()) == valid


@pytest.mark.parametrize("endpoint,valid,invalid", [
    ("search", QUERY, {"extensions": "bad"}), ("info", INFO, {"uuid": None}),
])
def test_bad_refresh_does_not_replace_valid_cache(monkeypatch, endpoint, valid, invalid):
    monkeypatch.setattr(ego_client.urllib.request, "urlopen", lambda *a, **kw: response(valid))
    assert getattr(ego_client, endpoint)(UUID) is not None
    path = next((ego_cache.EGO_CACHE_DIR / endpoint).iterdir())
    previous = path.read_bytes()
    monkeypatch.setattr(ego_client.urllib.request, "urlopen", lambda *a, **kw: response(invalid))
    assert getattr(ego_client, endpoint)(UUID, use_cache=False) is None
    assert path.read_bytes() == previous


def test_mixed_search_entries_keep_valid_items_and_safe_display_fields(monkeypatch):
    item = {**INFO, "name": [], "description": {}, "creator": True,
            "icon": [], "pk": "bad", "downloads": {}, "rating": "NaN",
            "rating_count": 2.5, "shell_version_map": []}
    payload = {"extensions": [None, [], "bad", {"uuid": 7}, item],
               "page": [], "numpages": "bad", "total": float("inf")}
    monkeypatch.setattr(ego_client.urllib.request, "urlopen", lambda *a, **kw: response(payload))
    result = ego_client.search("valid", use_cache=False)
    assert result is not None
    assert (result.page, result.num_pages, result.total) == (1, 1, 1)
    assert len(result.extensions) == 1
    entry = result.extensions[0]
    assert entry.uuid == entry.name == UUID
    assert entry.description == entry.creator == entry.icon_url == ""
    assert (entry.pk, entry.downloads, entry.rating, entry.rating_count) == (0, 0, 0.0, 0)
    assert entry.shell_version_map == {}


@pytest.mark.parametrize("number", [True, -1, [], {}, "bad", float("nan"),
                                   float("inf"), 1.5, 10**400])
def test_invalid_counts_never_reach_display(number):
    item = ego_client._parse_summary({**INFO, "downloads": number, "pk": number})
    assert item.downloads == item.pk == 0


def test_numeric_strings_and_compatible_metadata_still_work():
    item = ego_client._parse_summary({**INFO, "downloads": "1234", "pk": "7",
                                      "rating": "4.5", "rating_count": "2"})
    assert (item.downloads, item.pk, item.rating, item.rating_count) == (1234, 7, 4.5, 2)
    detail = ego_client._info_from_dict(INFO)
    assert ego_client.version_from_info(detail, "50") == 7
    assert ego_client.version_from_info(detail, "51") is None


def test_integral_json_numbers_remain_compatible():
    item = ego_client._parse_summary({**INFO, "pk": 7.0, "downloads": 100.0})
    assert (item.pk, item.downloads) == (7, 100)
    raw = {"items": [{"family": "Second", "popularity": 2.0},
                     {"family": "First", "popularity": 1.0}]}
    assert [item.family for item in google_fonts._parse_catalog_payload(json.dumps(raw))] == [
        "First", "Second",
    ]


def test_detail_optional_fields_and_comments_are_type_safe():
    detail = ego_client._info_from_dict({
        **INFO, "url": [], "license": {}, "link": {}, "screenshot": 1,
        "screenshots": [None, 2, {}, {"url": []}, "/valid.png"],
        "comments": [None, {"text": ["bad"]},
                     {"text": "Good", "author": {}, "date": [], "rating": float("inf")}],
    })
    assert detail.homepage == detail.license == detail.screenshot_url == ""
    assert [entry.url for entry in detail.screenshots] == [ego_client.EGO_BASE_URL + "/valid.png"]
    assert len(detail.comments) == 1
    assert detail.comments[0].author == "anon"
    assert detail.comments[0].date == ""
    assert detail.comments[0].rating == 0


@pytest.mark.parametrize("payload", [None, [], "bad", {"familyMetadataList": {}},
                                    {"items": [{"family": ["bad"]}]}])
def test_invalid_font_catalog_keeps_stale_cache(monkeypatch, payload):
    old = {"saved_at": 0, "items": [{"family": "Saved Font", "category": "serif"}]}
    google_fonts.CACHE_FILE.write_text(json.dumps(old))
    before = google_fonts.CACHE_FILE.read_bytes()
    monkeypatch.setattr(google_fonts.urllib.request, "urlopen", lambda *a, **kw: response(payload))
    ok, entries, error = google_fonts.load_catalog(force_refresh=True)
    assert ok and not error
    assert entries == [google_fonts.FontFamily("Saved Font", "serif")]
    assert google_fonts.CACHE_FILE.read_bytes() == before


def test_font_payload_skips_bad_entries_and_normalizes_optional_fields():
    items = [None, "bad", {"family": []}, {"family": 7},
             {"family": "Valid", "category": {}, "popularity": float("inf")},
             {"family": "First", "category": "Sans Serif", "popularity": "0"}]
    expected = [google_fonts.FontFamily("First", "sans-serif"),
                google_fonts.FontFamily("Valid", "sans-serif")]
    assert google_fonts._parse_catalog_payload(json.dumps({"items": items})) == expected
    assert google_fonts._catalog_from_json({"items": items}) == list(reversed(expected))


@pytest.mark.parametrize("saved_at", [True, [], "NaN", float("inf"), -1])
def test_invalid_font_cache_timestamp_is_stale_but_content_remains_usable(saved_at):
    google_fonts.CACHE_FILE.write_text(json.dumps({
        "saved_at": saved_at, "items": [{"family": "Cached", "category": "serif"}],
    }))
    assert google_fonts._read_cached_catalog(True) == []
    assert google_fonts._read_cached_catalog(False) == [google_fonts.FontFamily("Cached", "serif")]


def test_valid_font_cache_does_not_need_network(monkeypatch):
    google_fonts.CACHE_FILE.write_text(json.dumps({
        "saved_at": time.time(), "items": [{"family": "Cached", "category": "serif"}],
    }))
    fetch = Mock(side_effect=AssertionError("unexpected network"))
    monkeypatch.setattr(google_fonts.urllib.request, "urlopen", fetch)
    assert google_fonts.load_catalog()[1][0].family == "Cached"
    fetch.assert_not_called()


@pytest.mark.parametrize("rating", [True, -1, 6, "NaN", float("inf"), {}, []])
def test_invalid_rating_defaults_to_zero(rating):
    result = ego_client._parse_summary({**INFO, "rating": rating})
    assert math.isfinite(result.rating) and result.rating == 0
