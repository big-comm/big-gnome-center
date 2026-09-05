# SPDX-License-Identifier: MIT
"""Focused tests for asynchronous extension search state."""

from types import SimpleNamespace

from ui.ext_browse_view import ExtBrowseView


class _Stack:
    def __init__(self):
        self.visible = None

    def set_visible_child_name(self, name):
        self.visible = name


def _view(generation=2):
    view = ExtBrowseView.__new__(ExtBrowseView)
    view._search_generation = generation
    view._loading = True
    view._has_loaded_once = False
    view._num_pages = 1
    view._total = 0
    view._stack = _Stack()
    view._render_results = lambda items: setattr(view, "rendered", items)
    view._update_pager_state = lambda: setattr(view, "pager_updated", True)
    return view


def test_stale_response_cannot_replace_current_results():
    view = _view(generation=4)

    assert view._on_search_done(3, SimpleNamespace()) is False
    assert view._loading is True
    assert not hasattr(view, "rendered")


def test_latest_response_updates_results_and_pagination():
    view = _view(generation=4)
    result = SimpleNamespace(extensions=["exact match"], num_pages=13, total=10)

    assert view._on_search_done(4, result) is False
    assert view._loading is False
    assert view.rendered == ["exact match"]
    assert view._num_pages == 13
    assert view._total == 10
    assert view._stack.visible == "results"
    assert view.pager_updated is True
