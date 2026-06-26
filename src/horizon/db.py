"""SQLite database engine and session management (via SQLModel)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from horizon.config import settings

# Ensure the data directory exists before SQLite tries to create the file.
Path(settings.database).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.database}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create tables if they do not yet exist."""
    # Import models so SQLModel registers them on the metadata.
    from horizon import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with Session(engine) as session:
        yield session
