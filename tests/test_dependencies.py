"""pyproject.toml feeds hosts that build from it (Vercel); it must not drift from requirements.txt."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _pins(lines):
    return {re.sub(r"\s+", "", line.split("#")[0]) for line in lines if line.split("#")[0].strip()}


def test_pyproject_runtime_pins_match_requirements():
    tomllib = pytest.importorskip("tomllib")  # Python 3.11+
    declared = set(tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"])
    required = _pins((ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines())
    assert declared == required, sorted(declared ^ required)


def test_postgres_urls_use_psycopg3():
    import sys
    sys.path.insert(0, str(ROOT))
    from config import normalize_database_url
    assert normalize_database_url("postgresql://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("sqlite:///x.db") == "sqlite:///x.db"
