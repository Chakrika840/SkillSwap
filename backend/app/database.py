"""
Database connection (SQLAlchemy 2.0 + SQLite).

- engine:        the connection pool to the database file
- SessionLocal:  a factory for database sessions (one per HTTP request)
- Base:          parent class of every table model
- get_db():      FastAPI dependency that opens a session and always closes it
"""
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

is_sqlite = settings.database_url.startswith("sqlite")

if is_sqlite:
    # Make sure the folder for the .db file exists (e.g. backend/data/).
    db_path = settings.database_url.replace("sqlite:///", "", 1)
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    # SQLite connections may be used by FastAPI's worker threads.
    connect_args={"check_same_thread": False} if is_sqlite else {},
)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")     # SQLite ignores foreign keys unless asked
        cursor.execute("PRAGMA journal_mode=WAL")    # readers don't block the writer
        cursor.close()

# expire_on_commit=False: objects stay usable after commit (we commit before slow AI calls).
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """One session per request; closed even if the endpoint raises."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
