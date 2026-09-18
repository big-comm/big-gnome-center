# SPDX-License-Identifier: MIT
"""Retention environment errors must not abort import or discard valid backups."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import backup_manager


@pytest.mark.parametrize("primary,legacy,expected", [
    (None, None, 10), ("broken", "3", 10), ("", None, 10), ("-2", None, 10),
    ("0", None, 1), ("+3", None, 3), (" 4 ", None, 4), (None, "bad", 10),
    (None, "2", 2), ("5", "2", 5), ("1.5", None, 10),
])
def test_import_and_retention_are_safe(tmp_path, primary, legacy, expected):
    env = os.environ.copy()
    for key, value in (("BIG_GNOME_CENTER_N_KEEP", primary), ("LAYOUT_SWITCHER_N_KEEP", legacy)):
        env.pop(key, None)
        if value is not None:
            env[key] = value
    env["PYTHONPATH"] = str(Path(backup_manager.__file__).parent)
    script = """
import json, os, sys
from pathlib import Path
import backup_manager
root = Path(sys.argv[1])
backup_manager.BACKUP_DIR = root
for index in range(12):
    path = root / f'backup_{index:02}.dconf'
    path.write_text('x' * 100)
    os.utime(path, (index + 1, index + 1))
backup_manager.BackupManager._prune()
print(json.dumps([backup_manager.BackupManager.N_KEEP,
                  sorted(path.name for path in root.iterdir())]))
"""
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=env,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    count, remaining = json.loads(result.stdout)
    assert count == expected
    assert remaining == [f"backup_{index:02}.dconf" for index in range(12 - expected, 12)]
