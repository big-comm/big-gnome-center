"""A next-login target must not be presented as the live layout."""
import ast
from pathlib import Path
from types import SimpleNamespace

from helper_client import HelperClient


def test_staged_apply_keeps_active_card_and_preferences():
    path = Path(__file__).resolve().parents[1] / "usr/share/big-gnome-center/ui/page_layouts.py"
    tree = ast.parse(path.read_text())
    page = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    method = next(node for node in page.body
                  if isinstance(node, ast.FunctionDef) and node.name == "_done")
    namespace = {
        "Optional": __import__("typing").Optional, "Path": Path,
        "LayoutApplier": SimpleNamespace(last_apply_staged=True), "tr": lambda value: value,
    }
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
    values = {"active_layout": "BigGnome"}
    statuses = []
    def save(key, value):
        values[key] = value
        return True
    target = SimpleNamespace(
        get_root=lambda: SimpleNamespace(), _active_layout="BigGnome",
        _prefs=SimpleNamespace(set=save, last_error=""),
        _set_status=lambda text, style: statuses.append(text))
    namespace["_done"](target, "Classic", True, "layout staged for the next session")
    assert target._active_layout == values["active_layout"] == "BigGnome"
    assert values["pending_layout"] == "Classic"
    assert values["last_apply_ok"] is False
    assert statuses == ["Classic — Restart now"]


def test_runtime_confirmation_requires_live_enabled_runtime(monkeypatch):
    for reply, expected in [
        (None, ""), ("invalid", ""), ('{"runtime": null}', ""),
        ('{"runtime":{"layout":"Classic","enabled":false}}', ""),
        ('{"runtime":{"layout":"Classic","enabled":true}}', "Classic"),
    ]:
        monkeypatch.setattr(HelperClient, "_call", lambda *args: reply)
        assert HelperClient.active_runtime_layout() == expected
