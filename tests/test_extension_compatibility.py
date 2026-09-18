# SPDX-License-Identifier: MIT
"""Reject incompatible EGO updates before changing installed extensions."""

import io
import json
import shutil
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ego_client
import extension_manager as manager
import update_checker


@pytest.mark.parametrize("target,other", [("50", "51"), ("51", "50")])
def test_version_never_falls_back_to_another_shell(target, other):
    detail = SimpleNamespace(shell_version_map={other: {"version": 99}})
    assert ego_client.version_from_info(detail, target) is None


@pytest.mark.parametrize("target", ["", "all"])
def test_compatible_version_requires_a_known_target(target):
    detail = SimpleNamespace(shell_version_map={"50": {"version": 99}})
    assert ego_client.version_from_info(detail, target) is None


@pytest.mark.parametrize("target,expected", [("50", 4), ("51", 2)])
def test_only_the_target_entry_controls_update_version(target, expected):
    detail = SimpleNamespace(shell_version_map={
        "49": {"version": 99}, "50": {"version": 4}, "51": {"version": "2"},
    })
    assert ego_client.version_from_info(detail, target) == expected


@pytest.mark.parametrize("entry", [None, [], "99", {}, {"version": True},
                                   {"version": 2.8}, {"version": 0},
                                   {"version": -1}, {"version": "invalid"}])
def test_invalid_target_entry_does_not_fall_back(entry):
    detail = SimpleNamespace(shell_version_map={"50": entry, "51": {"version": 99}})
    assert ego_client.version_from_info(detail, "50") is None


@pytest.mark.parametrize("versions", [None, [], "invalid"])
def test_malformed_compatibility_map_is_not_an_update(versions):
    assert ego_client.version_from_info(SimpleNamespace(shell_version_map=versions), "50") is None


def test_unknown_shell_does_not_report_a_successful_check(monkeypatch):
    monkeypatch.setattr(update_checker, "gnome_shell_version", lambda: (0, 0))
    monkeypatch.setattr(manager.ExtMgr, "list_installed", lambda: [
        {"uuid": "compat@example.org", "user": True}
    ])
    request = Mock()
    monkeypatch.setattr(ego_client, "info", request)
    with pytest.raises(update_checker.UpdateCheckError) as error:
        update_checker.check_all()
    assert error.value.updates == {}
    request.assert_not_called()


@pytest.mark.parametrize("target,other", [(50, "51"), (51, "50")])
def test_check_all_ignores_incompatible_release(monkeypatch, target, other):
    monkeypatch.setattr(update_checker, "gnome_shell_version", lambda: (target, 0))
    monkeypatch.setattr(manager.ExtMgr, "list_installed", lambda: [
        {"uuid": "compat@example.org", "user": True}
    ])
    monkeypatch.setattr(manager.ExtMgr, "installed_version", lambda uuid: 1)
    monkeypatch.setattr(ego_client, "info", lambda *args, **kwargs: SimpleNamespace(
        pk=1, shell_version_map={other: {"version": 99}}
    ))
    progress = []
    assert update_checker.check_all(lambda done, total: progress.append((done, total))) == {}
    assert progress == [(1, 1)]


def bundle(supported):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("metadata.json", json.dumps({
            "uuid": "compat@example.org", "shell-version": supported, "version": 2,
        }))
        archive.writestr("extension.js", "export default class Extension {}")
    return stream.getvalue()


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "EXT_USER_DIR", tmp_path)
    dest = tmp_path / "compat@example.org"
    dest.mkdir()
    (dest / "extension.js").write_text("original code")
    return dest


@pytest.mark.parametrize("target,other", [(50, "51"), (51, "50")])
def test_incompatible_bundle_preserves_installed_extension(installed, monkeypatch, target, other):
    response = io.BytesIO(bundle([other]))
    response.headers = {"Content-Type": "application/zip"}
    monkeypatch.setattr(manager, "gnome_shell_version", lambda: (target, 0))
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: response)
    ok, message = manager.ExtMgr._install_from_ego("compat@example.org", 1)
    assert not ok, message
    assert (installed / "extension.js").read_text() == "original code"


def test_unknown_shell_never_downloads(installed, monkeypatch):
    network = Mock()
    monkeypatch.setattr(manager, "gnome_shell_version", lambda: (0, 0))
    monkeypatch.setattr(manager.urllib.request, "urlopen", network)
    assert not manager.ExtMgr._install_from_ego("compat@example.org", 1)[0]
    network.assert_not_called()
    assert (installed / "extension.js").read_text() == "original code"


@pytest.mark.parametrize("supported", [None, "50", {"50": True}, [], [50], ["50", 51]])
def test_malformed_bundle_compatibility_is_rejected(installed, monkeypatch, supported):
    response = io.BytesIO(bundle(supported))
    response.headers = {"Content-Type": "application/zip"}
    monkeypatch.setattr(manager, "gnome_shell_version", lambda: (50, 4))
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: response)
    compile_schemas = Mock()
    monkeypatch.setattr(manager.ExtMgr, "_compile_schemas", compile_schemas)
    assert not manager.ExtMgr._install_from_ego("compat@example.org", 1)[0]
    compile_schemas.assert_not_called()
    assert (installed / "extension.js").read_text() == "original code"
    assert list(installed.parent.iterdir()) == [installed]


@pytest.mark.parametrize("detected,target", [((50, 4), "50"), ((51, 0), "51"), ((3, 38), "3.38")])
def test_compatible_bundle_is_published_with_targeted_request(
    installed, monkeypatch, detected, target
):
    response = io.BytesIO(bundle([target]))
    response.headers = {"Content-Type": "application/zip"}
    network = Mock(return_value=response)
    monkeypatch.setattr(manager, "gnome_shell_version", lambda: detected)
    monkeypatch.setattr(update_checker, "gnome_shell_version", lambda: detected)
    monkeypatch.setattr(manager.urllib.request, "urlopen", network)
    assert update_checker._shell_version_str() == target
    ok, message = manager.ExtMgr._install_from_ego("compat@example.org", 1)
    assert ok, message
    assert network.call_args.args[0].full_url.endswith(f"?shell_version={target}")
    assert (installed / "extension.js").read_text() == "export default class Extension {}"
    assert list(installed.parent.iterdir()) == [installed]


def test_rejected_update_cannot_bypass_validation_or_change_enablement(installed, monkeypatch):
    import ego_cache
    from shell_reloader import ShellReloader

    response = io.BytesIO(bundle(["51"]))
    response.headers = {"Content-Type": "application/zip"}
    monkeypatch.setattr(manager, "gnome_shell_version", lambda: (50, 4))
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: response)
    monkeypatch.setattr(manager.ExtMgr, "is_enabled", lambda uuid: True)
    bypass = Mock(return_value=(True, "unvalidated install"))
    state = Mock()
    cache = Mock()
    monkeypatch.setattr(manager.ExtMgr, "install", bypass)
    monkeypatch.setattr(ShellReloader, "apply_extension_state", state)
    monkeypatch.setattr(ego_cache, "json_invalidate", cache)
    assert not manager.ExtMgr.update("compat@example.org", 1)[0]
    bypass.assert_not_called()
    state.assert_not_called()
    cache.assert_not_called()
    assert (installed / "extension.js").read_text() == "original code"


@pytest.mark.parametrize("valid_schema", [False, True])
def test_real_schema_compiler_validates_before_publication(installed, monkeypatch, valid_schema):
    if not shutil.which("glib-compile-schemas"):
        pytest.skip("Requires glib-compile-schemas")
    output = io.BytesIO(bundle(["50"]))
    with zipfile.ZipFile(output, "a") as archive:
        schema = (
            '<schemalist><schema id="org.example.compat" path="/org/example/compat/">'
            '<key name="enabled" type="b"><default>false</default></key>'
            '</schema></schemalist>'
        ) if valid_schema else '<invalid schema>'
        archive.writestr("schemas/org.example.compat.gschema.xml", schema)
    response = io.BytesIO(output.getvalue())
    response.headers = {"Content-Type": "application/zip"}
    monkeypatch.setattr(manager, "gnome_shell_version", lambda: (50, 4))
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: response)
    ok, message = manager.ExtMgr._install_from_ego("compat@example.org", 1)
    assert ok == valid_schema, message
    if valid_schema:
        assert (installed / "schemas/gschemas.compiled").is_file()
    else:
        assert (installed / "extension.js").read_text() == "original code"
    assert list(installed.parent.iterdir()) == [installed]
