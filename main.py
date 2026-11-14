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
from routers import audit, auth, companies, dashboard, tickets, users
from services.sla_service import sla_monitor_loop

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ticket_system")


@asynccontextmanager
async def lifespan(_: FastAPI):
    key = settings.SECRET_KEY
    if len(key) < 32 or key.startswith("dev-secret") or "change" in key.lower():
        logger.warning("SECRET_KEY is a placeholder or too short - anyone knowing it can forge admin tokens. "
                       "Set a random value in .env before deploying.")
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
    docs_url="/docs",
    redoc_url="/redoc",
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


for module in (auth, companies, tickets, users, dashboard, audit):
    app.include_router(module.router)

# ============ STATIC FILES & FRONTEND ============
# Attachments are NOT mounted publicly; they are served by the authenticated
# endpoint GET /api/tickets/attachments/{id}/download

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def read_root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("""
    <html><body style="font-family: system-ui; padding: 2rem; text-align: center;">
        <h1>Ticket System</h1>
        <p>Frontend not built yet.</p>
        <p><a href="/docs">API Documentation</a></p>
    </body></html>
    """)


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
