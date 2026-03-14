"""
Database setup with SQLAlchemy and SQLite.

SQLAlchemy ist ein ORM (Object-Relational Mapper) — es erlaubt uns,
mit Python-Klassen statt mit rohem SQL zu arbeiten. Die Datenbank
wird als einfache SQLite-Datei gespeichert (kein Server nötig).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///finance.db"


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Yield a database session (used by FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_engine(db_url: str = DATABASE_URL):
    """Create an engine for a specific database URL."""
    return create_engine(db_url, connect_args={"check_same_thread": False})
