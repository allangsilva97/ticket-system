from datetime import datetime, timezone

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    pool_pre_ping=True,
    pool_recycle=300,
)

if is_sqlite:
    # SQLite does not enforce foreign keys unless asked to
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (the DB columns are naive UTC).
    Replaces datetime.utcnow(), deprecated since Python 3.12."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import models  # noqa: F401  (registers tables on Base.metadata)
    Base.metadata.create_all(bind=engine)
    _migrate_tracking_code()


def _migrate_tracking_code():
    """Databases created before v2.1 have no tickets.tracking_code: add it and backfill.
    create_all() only creates missing tables, never missing columns."""
    from models import Ticket, generate_tracking_code

    if "tracking_code" not in {c["name"] for c in inspect(engine).get_columns("tickets")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tickets ADD COLUMN tracking_code VARCHAR(16)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_tickets_tracking_code "
                              "ON tickets (tracking_code)"))

    db = SessionLocal()
    try:
        missing = db.query(Ticket).filter(Ticket.tracking_code.is_(None)).all()
        for ticket in missing:
            ticket.tracking_code = generate_tracking_code()
        if missing:
            db.commit()
    finally:
        db.close()
