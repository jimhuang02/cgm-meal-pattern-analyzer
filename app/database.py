"""Database engine and session dependency."""

import os
from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cgm_analyzer.db")

# Render (and some other providers) supply postgres:// but SQLAlchemy requires postgresql://
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False; PostgreSQL ignores the kwarg via connect_args
_connect_args = {"check_same_thread": False} if _DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(_DATABASE_URL, echo=False, connect_args=_connect_args)


def create_db_and_tables() -> None:
    """Create all tables defined in SQLModel metadata."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: yields a database session per request."""
    with Session(engine) as session:
        yield session
