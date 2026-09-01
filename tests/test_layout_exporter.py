from __future__ import annotations

import json
from pathlib import Path

import pytest

import layout_exporter
from helper_client import HELPER_UUID, LEGACY_HELPER_UUID


@pytest.fixture
def layouts_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "usr/share/layout-switcher/layouts"


def test_catalog_comes_from_packaged_layouts(layouts_dir: Path) -> None:
    catalog = layout_exporter.layout_catalog(layouts_dir)
    assert [entry["id"] for entry in catalog] == [
        "biggnome",
        "desk-ux",
        "hybrid",
        "g-unity",
        "classic",
        "minimal",
    ]
    assert catalog[0]["display_name"] == "BigGnome"


@pytest.mark.parametrize(
    ("layout_id", "display_name"),
    [
        ("biggnome", "BigGnome"),
        ("desk-ux", "Desk UX"),
        ("hybrid", "Hybrid"),
        ("g-unity", "G-Unity"),
        ("classic", "Classic"),
        ("minimal", "Minimal"),
    ],
)
def test_export_has_canonical_helper_and_active_layout(
    layouts_dir: Path,
    layout_id: str,
    display_name: str,
) -> None:
    manifest = layout_exporter.prepare_layout(
        layout_id,
        layouts_dir=layouts_dir,
        shell_major=51,
        monitor_ids={"0"},
    )
    data = str(manifest["settings_gnome"])
    assert LEGACY_HELPER_UUID not in data
    assert data.count(HELPER_UUID) == 1
    assert "[org/communitybig/layout-switcher/runtime]" in data
    assert f"active-layout='{display_name}'" in data
    assert manifest["app_settings"] == {"active_layout": display_name}


def test_gnome50_factory_defaults_are_exported(layouts_dir: Path) -> None:
    manifest = layout_exporter.prepare_layout(
        "biggnome",
        layouts_dir=layouts_dir,
        shell_major=50,
        monitor_ids={"0"},
    )
    data = str(manifest["settings_gnome"])
    assert "[org/communitybig/frosted-glass]" in data
    assert "enabled=true" in data
    assert "overview-enabled=true" in data


def test_cli_manifest_is_machine_readable(
    layouts_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = layout_exporter.main(
        [
            "biggnome",
            "--manifest",
            "--layouts-dir",
            str(layouts_dir),
            "--shell-major",
            "51",
            "--monitor-id",
            "0",
        ]
    )
    assert result == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["layout"] == "biggnome"
    assert manifest["app_settings"]["active_layout"] == "BigGnome"


def test_unknown_layout_is_rejected(layouts_dir: Path) -> None:
    with pytest.raises(ValueError, match="unknown layout"):
        layout_exporter.prepare_layout("../biggnome", layouts_dir=layouts_dir)
