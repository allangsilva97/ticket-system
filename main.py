import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config import settings, BASE_DIR
from database import engine, init_db
from routers import audit, auth, companies, dashboard, public, tickets, users
from services.sla_service import sla_monitor_loop

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ticket_system")


def _production_like() -> bool:
    """Hosting platforms set VERCEL / RENDER themselves. A deploy that forgot APP_ENV still counts as production:
    it refuses the public placeholder key (anyone who knows it can forge an administrator token) and hides the docs."""
    return settings.APP_ENV.lower() == "production" or bool(os.getenv("VERCEL") or os.getenv("RENDER"))


DOCS_ENABLED = settings.ENABLE_DOCS if settings.ENABLE_DOCS is not None else not _production_like()


@asynccontextmanager
async def lifespan(_: FastAPI):
    key = settings.SECRET_KEY
    if len(key) < 32 or key.startswith("dev-secret") or "troque" in key.lower() or "change" in key.lower():
        if _production_like():
            raise RuntimeError(
                "SECRET_KEY is a placeholder or too short: set a random value before running in production "
                "(python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
            )
        logger.warning("SECRET_KEY is a placeholder or too short - anyone knowing it can forge admin tokens. "
                       "Set a random value in .env before deploying (and APP_ENV=production to enforce it).")
    init_db()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    monitor = asyncio.create_task(sla_monitor_loop()) if settings.SLA_MONITOR_ENABLED else None
    try:
        yield
    finally:
        if monitor:
            monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Sistema de tickets de suporte multiempresa com SLA, auditoria e notificações por e-mail.",
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,  # the schema lists every route: keep it off on public hosts
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:])
    msg = f"{field}: {first.get('msg')}" if field else first.get("msg", "Validation error")
    return JSONResponse(status_code=422, content={"detail": f"Validation error - {msg}", "errors": errors})


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=400,
        content={"detail": "Database integrity error. Possible duplicate entry or record still in use."},
    )


for module in (auth, companies, tickets, users, dashboard, audit, public):
    app.include_router(module.router)

# ============ STATIC FILES & FRONTEND ============
# Attachments are NOT mounted publicly; they are served by the authenticated
# endpoint GET /api/tickets/attachments/{id}/download

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")




# Portal pages: one HTML file per route, sharing /static/portal.js and portal.css
# "/" is the login screen; after login everyone lands on /dashboard.
# The original single-page admin panel (index.html) lives at /painel.
PORTAL_PAGES = {
    "/": "login.html",
    "/login": "login.html",
    "/dashboard": "dashboard.html",
    "/painel": "index.html",
    "/perfil": "perfil.html",
    "/abrir-chamado": "abrir-chamado.html",
    "/acompanhar": "acompanhar.html",
    "/tecnico": "tecnico.html",
}


def _page_route(filename: str):
    async def serve_page():
        return FileResponse(str(static_dir / filename))
    return serve_page


for _path, _file in PORTAL_PAGES.items():
    app.add_api_route(_path, _page_route(_file), methods=["GET"], include_in_schema=False,
                      response_class=HTMLResponse)


def _database_ok() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - any failure means "not ready"
        logger.exception("Database health check failed")
        return False


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness: the process is up."""
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/health/ready", tags=["Health"])
def readiness_check():
    """Readiness: the database answers (used by Docker/Kubernetes health checks)."""
    if not _database_ok():
        return JSONResponse(status_code=503, content={"status": "not ready", "database": "disconnected"})
    return {"status": "ready", "database": "connected"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
