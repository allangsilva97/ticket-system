"""The login throttle and the audit trail must see the real client; a forged X-Forwarded-For must not change that."""
import sys
from pathlib import Path

from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from utils import client_ip  # noqa: E402


def _req(xff=None, peer="10.0.0.9"):
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_client_ip_ignores_forged_forwarded_for(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    assert client_ip(_req("1.2.3.4")) == "10.0.0.9"  # no trusted proxy: only the TCP peer counts
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    assert client_ip(_req("6.6.6.6, 203.0.113.7")) == "203.0.113.7"  # a forged left entry is ignored
    assert client_ip(_req()) == "10.0.0.9"  # no header: TCP peer
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)
    assert client_ip(_req("203.0.113.7")) == "10.0.0.9"  # chain shorter than expected: do not trust it
