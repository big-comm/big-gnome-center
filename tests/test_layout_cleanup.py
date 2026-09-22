# SPDX-License-Identifier: MIT
"""Layout cleanup must not erase personal extension settings."""

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from helper_client import HELPER_UUID
from layout_applier import LayoutApplier

LAYOUTS = Path(__file__).resolve().parents[1] / "usr/share/big-gnome-center/layouts"
BASE = "/org/gnome/shell/extensions/"
PROTECTED = ("personal-extension", "gsconnect", "gtk4-ding", HELPER_UUID.split("@", 1)[0])


def section(branch, values="keep=true\nstale=true\n"):
    return f"[{BASE.lstrip('/')}{branch}]\n{values}\n"


@pytest.mark.parametrize("layout", sorted(LAYOUTS.glob("*.txt")), ids=lambda p: p.stem)
@pytest.mark.parametrize("snapshot", [False, True], ids=["original", "snapshot"])
def test_cleanup_preserves_unowned_and_protected_settings(layout, snapshot):
    target = layout.read_text()
    live = "".join(section(branch) for branch in PROTECTED)
    live += section("dash-to-panel-personal")
    live += "[org/example/application]\nstale=true\n"
    live += section("arcmenu", "retired=true\n")
    if snapshot:
        target += "\n" + "".join(section(branch, "keep=true\n") for branch in PROTECTED)

    def run(argv, **kwargs):
        return (True, live) if argv == ["dconf", "dump", "/"] else (True, "")

    with patch("layout_applier.run_cmd", side_effect=run) as command:
        count = LayoutApplier._reset_orphan_keys(target)

    assert count == 1
    assert [call.args[0] for call in command.call_args_list[1:]] == [
        ["dconf", "reset", "-f", BASE + "arcmenu/"]
    ]


def test_cleanup_preserves_nested_skip_and_resets_owned_stale_key():
    live = section("dash-to-panel") + section("dash-to-panel/monitor", "private=true\n")
    target = section("dash-to-panel", "keep=true\n")
    with patch("layout_applier.run_cmd", side_effect=[(True, live), (True, "")]) as command:
        count = LayoutApplier._reset_orphan_keys(
            target, skip_subdirs={BASE + "dash-to-panel/monitor/"}
        )
    assert count == 1
    assert command.call_args.args[0] == ["dconf", "reset", BASE + "dash-to-panel/stale"]


@pytest.mark.parametrize("dump_result", [(False, "error"), (True, "")])
def test_cleanup_does_not_reset_without_live_dump(dump_result):
    with patch("layout_applier.run_cmd", return_value=dump_result) as command:
        assert LayoutApplier._reset_orphan_keys("") == 0
    command.assert_called_once_with(["dconf", "dump", "/"], timeout=15)


def test_cleanup_keeps_skipped_owned_branch():
    with patch("layout_applier.run_cmd", return_value=(True, section("dash-to-panel"))) as command:
        assert LayoutApplier._reset_orphan_keys("", skip_subdirs={BASE + "dash-to-panel/"}) == 0
    assert command.call_count == 1


def test_managed_branches_come_from_all_profiles_and_exclude_protected_data(tmp_path):
    (tmp_path / "first.txt").write_text(section("first/nested"))
    (tmp_path / "second.txt").write_text(
        section("second") + "".join(section(branch) for branch in PROTECTED[1:])
    )
    assert LayoutApplier._managed_extension_subdirs(tmp_path) == [
        "arcmenu", "blur-my-shell", "first", "second"
    ]


@pytest.mark.parametrize("missing", [False, True])
def test_missing_profiles_do_not_expand_cleanup(tmp_path, missing):
    directory = tmp_path / "missing" if missing else tmp_path
    with patch(
        "layout_applier.run_cmd", return_value=(True, section("personal-extension"))
    ) as command:
        assert LayoutApplier._reset_orphan_keys("", layouts_dir=directory) == 0
    assert command.call_count == 1


def test_unreadable_profile_does_not_expand_cleanup(tmp_path):
    profile = tmp_path / "layout.txt"
    profile.touch()
    with patch.object(Path, "read_text", side_effect=PermissionError("unreadable")):
        assert LayoutApplier._managed_extension_subdirs(tmp_path) == ["arcmenu", "blur-my-shell"]


@pytest.mark.parametrize("modern", [False, True], ids=["legacy-helper", "cleanroom"])
def test_helper_cleanup_uses_profiles_not_snapshot_ownership(tmp_path, modern):
    (tmp_path / "previous.txt").write_text(section("owned"))
    target = section("personal-extension", "keep=true\n")
    live = section("personal-extension") + section("owned")

    def run(argv, **kwargs):
        return (True, live) if argv == ["dconf", "dump", "/"] else (True, "")

    with ExitStack() as stack:
        for method, result in (
            ("HelperClient.ping_info", {"uuid": HELPER_UUID}),
            ("HelperClient.begin_switch", (True, "")),
            ("HelperClient.complete_switch", (True, "")),
            ("HelperClient.apply_layout", (True, "")),
            ("HelperClient.helper_version", 7),
            ("ShellReloader.list_extensions_state", {}),
            ("LayoutApplier._enabled_extensions", []),
        ):
            stack.enter_context(patch("layout_applier." + method, return_value=result))
        command = stack.enter_context(patch(
            "layout_applier.run_cmd",
            side_effect=run,
        ))
        apply = LayoutApplier._apply_via_helper_v7 if modern else LayoutApplier._apply_via_helper
        ok, message = apply(target, layouts_dir=tmp_path)
        assert ok, message
    if modern:
        batches = [
            call.args[0] for call in command.call_args_list
            if len(call.args[0]) > 1 and call.args[0][1].endswith("dconf_batch.py")
        ]
        assert len(batches) == 1
        reset_paths = [
            batches[0][index + 1]
            for index, argument in enumerate(batches[0])
            if argument == "--reset"
        ]
        assert BASE + "owned/keep" in reset_paths
        assert BASE + "owned/stale" in reset_paths
        assert not any("personal-extension" in path for path in reset_paths)
    else:
        resets = [
            call.args[0] for call in command.call_args_list
            if call.args[0][:2] == ["dconf", "reset"]
        ]
        assert ["dconf", "reset", "-f", BASE + "owned/"] in resets
        allowed = {BASE + branch + "/" for branch in ("owned", "arcmenu", "blur-my-shell")}
        assert all(argv[-1] in allowed for argv in resets)
