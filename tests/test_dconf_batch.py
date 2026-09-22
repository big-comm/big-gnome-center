# SPDX-License-Identifier: MIT
"""Single-process dconf mutation worker."""

import importlib.util
import io
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "usr/share/big-gnome-center/dconf_batch.py"
SPEC = importlib.util.spec_from_file_location("dconf_batch", MODULE_PATH)
dconf_batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dconf_batch)


def test_batch_commits_resets_and_values_as_one_changeset():
    keyfile = "[org/gnome/shell/extensions/test]\nvalue=true\n"
    with patch.object(dconf_batch, "_atomic_change") as change, patch(
        "sys.stdin", io.StringIO(keyfile)
    ):
        assert dconf_batch.main([
            "--reset-tree", "/org/gnome/shell/extensions/test/",
            "--reset", "/org/gnome/shell/extensions/test/value",
        ]) == 0

    change.assert_called_once_with(
        [
            "/org/gnome/shell/extensions/test/",
            "/org/gnome/shell/extensions/test/value",
        ],
        {"/org/gnome/shell/extensions/test/value": "true"},
    )


def test_batch_can_dump_to_a_file(tmp_path):
    output = tmp_path / "state.dconf"
    with patch.object(dconf_batch, "_run", return_value="[/]\nkey=true\n") as run:
        assert dconf_batch.main(["--dump-output", str(output)]) == 0

    run.assert_called_once_with(("dump", "/"))
    assert output.read_text() == "[/]\nkey=true\n"


@pytest.mark.parametrize("arguments", [
    ["--reset-tree", "/org/gnome/shell/"],
    ["--reset", "org/gnome/shell/key"],
    ["--reset", "/org/gnome/shell/key;touch /tmp/bad"],
])
def test_batch_rejects_untrusted_paths(arguments):
    with patch("sys.stdin", io.StringIO("")), pytest.raises(SystemExit):
        dconf_batch.main(arguments)
