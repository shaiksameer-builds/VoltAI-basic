"""
VoltAI Database Connection & Engine Configuration

Provides database engine creation, session management, and table initialization.
Defaults to local SQLite storage (data/voltai.db) while remaining fully compatible
with PostgreSQL or any standard SQL database via the DATABASE_URL environment variable.
"""

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Base class for declarative models
Base = declarative_base()


def get_default_db_url() -> str:
    """
    Compute the default SQLite database URL pointing to data/voltai.db
    at the repository root.
    """
    # backend/app/database/connection.py -> parent x 4 = VoltAI root
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / "voltai.db"
    return f"sqlite:///{db_file.as_posix()}"


def get_database_url() -> str:
    """
    Retrieve database URL from environment variable or return default SQLite URL.
    """
    return os.getenv("DATABASE_URL", get_default_db_url())


def create_db_engine(url: str | None = None) -> Engine:
    """
    Create a SQLAlchemy Engine with appropriate settings for SQLite or PostgreSQL.
    """
    db_url = url or get_database_url()
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        db_url,
        connect_args=connect_args,
        echo=False,
    )


# Default engine and session maker for application runtime
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine: Engine | None = None) -> None:
    """
    Initialize database schema by creating required tables.
    Uses SQLAlchemy's create_all which creates tables only if they do not already exist,
    preserving existing data across application runs.
    """
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a database session per request,
    ensuring proper closure upon completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
