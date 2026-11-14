"""
Shared test fixtures.

Creates a fresh in-memory SQLite database for each test,
so tests never interfere with each other or with real data.
"""

import pytest
from sqlalchemy import create_engine, text
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


@pytest.fixture
def refuse_rows_described_as():
    """Return a function that makes the database refuse one kind of transaction.

    ``install(engine, description)`` creates a real SQLite trigger that aborts
    every INSERT into ``transactions`` whose description equals ``description``.
    The refusal comes from the database engine and surfaces as a genuine
    ``sqlalchemy.exc.IntegrityError`` at commit time, the same way a violated
    constraint would, while every other row is stored normally. The rollback
    regression tests use it to fail exactly one save in the middle of an import.
    """

    def install(engine, description):
        literal = description.replace("'", "''")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TRIGGER refuse_described_row BEFORE INSERT ON transactions "
                    f"WHEN NEW.description = '{literal}' "
                    "BEGIN SELECT RAISE(ABORT, 'row refused by test trigger'); END"
                )
            )

    return install
