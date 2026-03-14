"""
Shared test fixtures.

Creates a fresh in-memory SQLite database for each test,
so tests never interfere with each other or with real data.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base


@pytest.fixture
def db():
    """Yield a database session backed by an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
