# SPDX-License-Identifier: MIT
"""Recover settings before aborting a failed clean-room dconf phase."""

import configparser
from unittest.mock import Mock

import pytest

import layout_applier as module
from helper_client import HELPER_UUID

BASE = "/org/gnome/shell/extensions/"
OLD = {
    BASE + "owned/old": "'previous'",
    BASE + "owned/nested/value": "'nested'",
    BASE + "second/value": "17",
    BASE + "personal/value": "'private'",
    BASE + "owned-personal/value": "'private sibling'",
    "/org/example/changed": "'before'",
    "/org/example/untouched": "'keep'",
    "/org/gnome/shell/enabled-extensions": "['before@example.org']",
}
TARGET = (
    "[org/gnome/shell]\nenabled-extensions=['after@example.org']\n\n"
    "[org/gnome/shell/extensions/owned]\nnew='new'\n\n"
    "[org/example]\nchanged='after'\nintroduced=true\n"
)


def dump(values):
    return "\n".join(
        f"[{path.rsplit('/', 1)[0].lstrip('/')}]\n{path.rsplit('/', 1)[1]}={value}\n"
        for path, value in values.items()
    )


def values(text):
    parser = configparser.RawConfigParser(strict=False, delimiters=("=",))
    parser.optionxform = str
    parser.read_string(text)
    return {f"/{section}/{key}": value
            for section in parser.sections() for key, value in parser.items(section)}


@pytest.fixture
def session(monkeypatch):
    state = dict(OLD)
    events = []
    mocks = {}
    for owner, name, result in (
        (module.HelperClient, "ping_info", {"uuid": HELPER_UUID}),
        (module.HelperClient, "begin_switch", (True, "")),
        (module.HelperClient, "complete_switch", (True, "")),
        (module.HelperClient, "abort_switch", True),
        (module.LayoutApplier, "_restore_persisted_settings", (True, "")),
        (module.LayoutApplier, "_enabled_extensions", []),
        (module.LayoutApplier, "_managed_extension_subdirs", ["owned", "second"]),
        (module.ShellReloader, "list_extensions_state", {}),
    ):
        mocks[name] = Mock(return_value=result)
        monkeypatch.setattr(owner, name, mocks[name])

    def run(argv, **kwargs):
        events.append((argv, kwargs))
        if argv == ["dconf", "dump", "/"]:
            return True, dump(state)
        if argv[:2] == ["dconf", "reset"]:
            path = argv[-1]
            for key in list(state):
                if key.startswith(path) if "-f" in argv else key == path:
                    del state[key]
        elif argv[:2] == ["dconf", "load"]:
            state.update(values(kwargs["stdin_text"]))
        elif argv[:2] == ["dconf", "write"]:
            state[argv[2]] = argv[3]
        return True, ""

    monkeypatch.setattr(module, "run_cmd", run)
    return state, events, mocks, run


@pytest.mark.parametrize("point", ["first-reset", "second-reset", "load"])
@pytest.mark.parametrize("raises", [False, True], ids=["failed-command", "exception"])
def test_failed_phase_restores_values_before_abort(session, monkeypatch, point, raises):
    state, events, mocks, run = session
    failed = False

    def fail(argv, **kwargs):
        nonlocal failed
        match = (
            argv[:2] == ["dconf", "load"] if point == "load"
            else argv == ["dconf", "reset", "-f", BASE + (
                "owned/" if point == "first-reset" else "second/"
            )]
        )
        result = run(argv, **kwargs)
        if match and not failed:
            failed = True
            # Timeouts may report failure after the mutation reached dconf.
            state["/org/example/untouched"] = "'external update'"
            if raises:
                raise OSError("injected failure")
            return False, "injected failure"
        return result

    expected = {**OLD, "/org/example/untouched": "'external update'"}
    mocks["abort_switch"].side_effect = lambda: state == expected or pytest.fail(
        "Extensions resumed before settings recovery"
    )
    monkeypatch.setattr(module, "run_cmd", fail)
    ok, message = module.LayoutApplier._apply_via_helper_v7(TARGET)
    assert not ok
    assert "injected failure" in message
    assert state == expected
    mocks["complete_switch"].assert_not_called()
    mocks["abort_switch"].assert_called_once()
    assert all(argv != ["dconf", "reset", "-f", "/"] for argv, kw in events)
    if point != "load":
        assert not any(
            "introduced=true" in kw.get("stdin_text", "") for argv, kw in events
        )


@pytest.mark.parametrize("raises", [False, True])
def test_dump_failure_prevents_teardown_and_mutations(session, monkeypatch, raises):
    state, events, mocks, run = session
    command = Mock(return_value=(False, "unavailable"))
    if raises:
        command.side_effect = OSError("unavailable")
    monkeypatch.setattr(module, "run_cmd", command)
    ok, message = module.LayoutApplier._apply_via_helper_v7(TARGET)
    assert not ok
    assert "unavailable" in message
    command.assert_called_once_with(["dconf", "dump", "/"], timeout=15)
    mocks["begin_switch"].assert_not_called()
    mocks["abort_switch"].assert_not_called()
    assert state == OLD


@pytest.mark.parametrize("empty", [False, True])
def test_successful_phase_keeps_target_and_does_not_recover(session, empty):
    state, events, mocks, run = session
    if empty:
        state.clear()
    ok, message = module.LayoutApplier._apply_via_helper_v7(TARGET)
    assert ok, message
    assert state["/org/example/changed"] == "'after'"
    assert state[BASE + "owned/new"] == "'new'"
    assert BASE + "owned/old" not in state
    if not empty:
        assert state[BASE + "personal/value"] == "'private'"
    mocks["complete_switch"].assert_called_once()
    mocks["abort_switch"].assert_not_called()


@pytest.mark.parametrize("recovery_point", ["reset", "load"])
@pytest.mark.parametrize("raises", [False, True])
def test_recovery_failure_is_reported_and_abort_still_attempted(
    session, monkeypatch, recovery_point, raises
):
    state, events, mocks, run = session
    loading_failed = False

    def fail(argv, **kwargs):
        nonlocal loading_failed
        if loading_failed and argv[:2] == ["dconf", recovery_point]:
            if raises:
                raise OSError("recovery unavailable")
            return False, "recovery unavailable"
        result = run(argv, **kwargs)
        if argv[:2] == ["dconf", "load"] and not loading_failed:
            loading_failed = True
            return False, "original load failed"
        return result

    monkeypatch.setattr(module, "run_cmd", fail)
    ok, message = module.LayoutApplier._apply_via_helper_v7(TARGET)
    assert not ok
    assert "original load failed" in message
    assert "recovery unavailable" in message
    mocks["abort_switch"].assert_called_once()
    mocks["complete_switch"].assert_not_called()
    if recovery_point == "reset":
        assert state[BASE + "owned/old"] == "'previous'"


def test_begin_failure_does_not_attempt_settings_recovery(session):
    state, events, mocks, run = session
    mocks["begin_switch"].return_value = False, "begin failed"
    ok, message = module.LayoutApplier._apply_via_helper_v7(TARGET)
    assert not ok
    assert message == "begin failed"
    assert state == OLD
    assert all(argv[:2] == ["dconf", "dump"] for argv, kw in events)


def test_failed_reset_does_not_overwrite_unattempted_branch(session, monkeypatch):
    state, events, mocks, run = session
    failed = False

    def fail(argv, **kwargs):
        nonlocal failed
        if argv == ["dconf", "reset", "-f", BASE + "owned/"] and not failed:
            failed = True
            run(argv, **kwargs)
            state[BASE + "second/value"] = "42"
            return False, "reset failed"
        return run(argv, **kwargs)

    monkeypatch.setattr(module, "run_cmd", fail)
    assert not module.LayoutApplier._apply_via_helper_v7(TARGET)[0]
    assert state == {**OLD, BASE + "second/value": "42"}


@pytest.mark.parametrize("point", ["dump", "begin", "load", "complete"])
def test_helper_failure_leaves_persistence_to_caller(session, monkeypatch, point):
    state, events, mocks, run = session
    if point in {"begin", "complete"}:
        mocks[point + "_switch"].return_value = False, "failed"
    else:
        def fail(argv, **kwargs):
            if argv[:2] == ["dconf", point]:
                return False, "failed"
            return run(argv, **kwargs)
        monkeypatch.setattr(module, "run_cmd", fail)
    ok, message = module.LayoutApplier._apply_via_helper_v7(TARGET)
    assert not ok
    mocks["_restore_persisted_settings"].assert_not_called()


def test_serialized_variants_survive_recovery(session):
    state, events, mocks, run = session
    previous = {
        "/org/example/array": "@as []",
        "/org/example/text": "'a=b; # literal'",
        "/org/example/map": "{'display': <[1, 2]>}",
    }
    parsed = module.LayoutApplier._dconf_dump_values(dump(previous))
    assert parsed == previous
    ok, message = module.LayoutApplier._restore_dconf_values(parsed, set(parsed))
    assert ok, message
    assert all(state[path] == value for path, value in previous.items())


def test_recovery_preserves_root_key_serialization(monkeypatch):
    command = Mock(return_value=(True, ""))
    monkeypatch.setattr(module, "run_cmd", command)
    parsed = module.LayoutApplier._dconf_dump_values("[/]\nkey='root'\n")
    assert parsed == {"/key": "'root'"}
    assert module.LayoutApplier._restore_dconf_values(parsed, set(parsed))[0]
    assert command.call_args.kwargs["stdin_text"] == "[/]\nkey='root'\n"
