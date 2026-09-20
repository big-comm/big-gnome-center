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
    assert "46 taskbar lifecycle scenarios passed" in result.stdout


def test_dock_lifecycle():
    script = Path(__file__).with_name("dock_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "35 dock lifecycle scenarios passed" in result.stdout


def test_dock_dwell_lifecycle():
    script = Path(__file__).with_name("dock_dwell_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "17 dock dwell lifecycle scenarios passed" in result.stdout


def test_dock_indicators_lifecycle():
    script = Path(__file__).with_name("dock_indicators_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "20 dock indicator lifecycle scenarios passed" in result.stdout


def test_panel_autohide_lifecycle():
    script = Path(__file__).with_name("panel_autohide_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "20 panel autohide lifecycle scenarios passed" in result.stdout


def test_panel_shortcuts_lifecycle():
    script = Path(__file__).with_name("panel_shortcuts_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "13 panel shortcut lifecycle scenarios passed" in result.stdout


def test_native_panel_lifecycle():
    script = Path(__file__).with_name("native_panel_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "30 native panel lifecycle scenarios passed" in result.stdout


def test_dock_panel_lifecycle():
    script = Path(__file__).with_name("dock_panel_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "46 dock panel lifecycle scenarios passed" in result.stdout


def test_dock_hover_lifecycle():
    script = Path(__file__).with_name("dock_hover_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "52 dock hover lifecycle scenarios passed" in result.stdout


def test_dock_menu_lifecycle():
    script = Path(__file__).with_name("dock_menu_lifecycle.mjs")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "14 dock menu lifecycle scenarios passed" in result.stdout
