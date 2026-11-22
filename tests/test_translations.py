# SPDX-License-Identifier: MIT
"""The application catalogs cover every source string in every language."""

import gettext
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCALE_DIR = ROOT / "usr/share/locale"
TEMPLATE = LOCALE_DIR / "big-gnome-center.pot"
EXTENSIONS = ROOT / "usr/share/gnome-shell/extensions"
RUNTIME_LOCALE_DIR = EXTENSIONS / "layout-switcher-runtime@communitybig.org/locale"
CATALOGS = sorted(LOCALE_DIR.glob("*.po"))

pytestmark = pytest.mark.skipif(shutil.which("msgcmp") is None, reason="gettext tools are required")


def _run(*command: str) -> subprocess.CompletedProcess:
    environment = {"LC_ALL": "C", "PATH": "/usr/bin"}
    return subprocess.run(command, capture_output=True, text=True, check=False, env=environment)


def _compiled(catalog: Path) -> Path:
    locale = catalog.stem.replace("-", "_")
    return LOCALE_DIR / locale / "LC_MESSAGES/big-gnome-center.mo"


def test_template_lists_every_source_string(tmp_path):
    sources = sorted(str(path) for path in (ROOT / "usr/share/big-gnome-center").rglob("*.py"))
    extracted = tmp_path / "extracted.pot"
    subprocess.run(
        [
            "xgettext",
            "--keyword=tr",
            "--language=Python",
            "--from-code=UTF-8",
            f"--output={extracted}",
            *sources,
        ],
        check=True,
    )

    result = _run("msgcmp", "--use-untranslated", str(TEMPLATE), str(extracted))

    assert result.returncode == 0, result.stderr


def test_every_language_has_a_catalog():
    assert len(CATALOGS) == 29


@pytest.mark.parametrize("catalog", CATALOGS, ids=lambda path: path.stem)
def test_catalog_translates_every_template_string(catalog):
    result = _run("msgcmp", str(catalog), str(TEMPLATE))

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("catalog", CATALOGS, ids=lambda path: path.stem)
def test_compiled_catalog_matches_its_source(catalog, tmp_path):
    fresh = tmp_path / "fresh.mo"
    subprocess.run(["msgfmt", "--check", f"--output-file={fresh}", str(catalog)], check=True)

    expected = _run("msgunfmt", str(fresh))
    shipped = _run("msgunfmt", str(_compiled(catalog)))

    assert expected.returncode == 0 and shipped.returncode == 0
    assert shipped.stdout == expected.stdout


@pytest.mark.parametrize("system_locale", ["nb_NO", "pt_BR", "pt_PT", "zh_CN", "zh_TW"])
@pytest.mark.parametrize(
    ("domain", "directory"),
    [
        ("big-gnome-center", LOCALE_DIR),
        ("community-menu", LOCALE_DIR),
        ("dashtodock", RUNTIME_LOCALE_DIR),
        ("dash-to-panel", RUNTIME_LOCALE_DIR),
    ],
)
def test_system_locale_finds_a_catalog(domain, directory, system_locale):
    assert gettext.find(domain, directory, [system_locale]) is not None
