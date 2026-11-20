"""Small helpers shared by the routers."""
from fastapi import Request

from config import settings

LIKE_ESCAPE = "\\"


def like_contains(term: str) -> str:
    """Pattern for a case-insensitive "contains" search that treats % and _ literally.

    Use with ``column.ilike(like_contains(term), escape=LIKE_ESCAPE)``.
    """
    escaped = (term.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
                   .replace("%", LIKE_ESCAPE + "%")
                   .replace("_", LIKE_ESCAPE + "_"))
    return f"%{escaped}%"


def client_ip(request: Request) -> str:
    """Address used by the login throttle and the audit trail.

    Behind trusted proxies, TRUSTED_PROXY_HOPS says how many sit in front of the app: the client is then the N-th
    X-Forwarded-For entry counted from the RIGHT, the one our own proxy appended. Entries further left come from the
    client and can be forged, so they never count. With 0 (default) only the TCP peer counts.
    """
    hops = settings.TRUSTED_PROXY_HOPS
    if hops > 0:
        chain = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(chain) >= hops:
            return chain[-hops]
    return request.client.host if request.client else "unknown"
