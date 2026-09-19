# SPDX-License-Identifier: MIT
"""Behavioral regression coverage for runtime controller ownership."""

import subprocess
from pathlib import Path


def test_runtime_controller_lifecycle():
    script = Path(__file__).with_name("runtime_controller_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "53 runtime controller lifecycle scenarios passed" in result.stdout


def test_taskbar_lifecycle():
    script = Path(__file__).with_name("taskbar_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "41 taskbar lifecycle scenarios passed" in result.stdout


def test_dock_lifecycle():
    script = Path(__file__).with_name("dock_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "32 dock lifecycle scenarios passed" in result.stdout


def test_dock_dwell_lifecycle():
    script = Path(__file__).with_name("dock_dwell_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "17 dock dwell lifecycle scenarios passed" in result.stdout
