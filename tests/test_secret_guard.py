"""A placeholder SECRET_KEY must stop the app from starting on a hosting platform, even without APP_ENV=production."""
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_tmpdir = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(_tmpdir, 'guard.db').as_posix()}")

import main  # noqa: E402

PLACEHOLDER = "dev-secret-change-in-production-min-32-chars-long"


@pytest.mark.parametrize("platform_var", ["VERCEL", "RENDER"])
def test_placeholder_key_refused_on_hosting_platform(monkeypatch, platform_var):
    monkeypatch.setenv(platform_var, "1")
    monkeypatch.setattr(main.settings, "APP_ENV", "development")
    monkeypatch.setattr(main.settings, "SECRET_KEY", PLACEHOLDER)
    with pytest.raises(RuntimeError, match="placeholder"):
        with TestClient(main.app):
            pass


def test_docs_hidden_on_hosting_platform(monkeypatch):
    import importlib
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr(main.settings, "APP_ENV", "development")
    monkeypatch.setattr(main.settings, "ENABLE_DOCS", None)
    try:
        importlib.reload(main)  # the app is built at import time, so rebuild it under the platform settings
        assert main.app.docs_url is None and main.app.openapi_url is None
    finally:
        monkeypatch.undo()
        importlib.reload(main)
    assert main.app.docs_url == "/docs"


def test_placeholder_key_allowed_locally(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(main.settings, "APP_ENV", "development")
    monkeypatch.setattr(main.settings, "SECRET_KEY", PLACEHOLDER)
    monkeypatch.setattr(main.settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    with TestClient(main.app) as client:  # only a warning in the log, as before
        assert client.get("/health").status_code == 200
