"""The shared setup every feature spec builds on: auto-imported models_ext, the export/delete registry, one router per line."""

import sys

import pytest

from app import db as dbm
from app import privacy

from .test_api import client, login  # noqa: F401  (reuse the app fixture and login helper)


def test_models_ext_is_imported_when_the_database_is_initialised():
    dbm.configure("sqlite://")
    dbm.init_db()
    assert "app.models_ext" in sys.modules


def test_export_and_delete_hooks_run(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(privacy, "_exporters", {})
    monkeypatch.setattr(privacy, "_deleters", [])
    seen = []
    privacy.register_export("probe", lambda db, lr: {"name_length": len(lr.name)})
    privacy.register_delete(lambda db, lr: seen.append(lr.id))
    h = login(client)
    ex = client.get("/api/me/export", headers=h).json()
    assert ex["more"] == {"probe": {"name_length": len("Priya Sharma")}}
    assert "evidence" in ex and "profile" in ex            # the existing keys are untouched
    assert client.delete("/api/me", headers=h).json()["deleted"] and len(seen) == 1


def test_an_export_key_cannot_be_registered_twice_or_empty(monkeypatch):
    monkeypatch.setattr(privacy, "_exporters", {})
    privacy.register_export("a", lambda db, lr: 1)
    with pytest.raises(ValueError):
        privacy.register_export("a", lambda db, lr: 2)
    with pytest.raises(ValueError):
        privacy.register_export("", lambda db, lr: 3)


def test_export_without_registered_hooks_has_an_empty_more(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(privacy, "_exporters", {})
    h = login(client)
    assert client.get("/api/me/export", headers=h).json()["more"] == {}
