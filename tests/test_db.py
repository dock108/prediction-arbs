"""Tests for the database persistence module."""

import datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from arbscan.db import Edge, Snapshot, init_db


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    # Use in-memory database for testing
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Create tables
    SQLModel.metadata.create_all(engine)

    # Return engine for use in tests
    return engine


def test_snapshot_creation(test_engine, monkeypatch):
    """Test creating and retrieving market snapshots."""
    # Set up test session with our in-memory engine
    monkeypatch.setattr("arbscan.db.engine", test_engine)

    # Create a test timestamp
    test_time = datetime.datetime(2025, 5, 1, 12, 0, 0, tzinfo=datetime.UTC)

    # Create a test snapshot
    with Session(test_engine) as session:
        snapshot = Snapshot(
            tag="TEST-TAG",
            exchange="TestExchange",
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.55"),
            ts=test_time,
        )
        session.add(snapshot)
        session.commit()

        # Retrieve snapshot and verify data
        retrieved = session.exec(select(Snapshot)).first()
        assert retrieved is not None
        assert retrieved.tag == "TEST-TAG"
        assert retrieved.exchange == "TestExchange"
        assert retrieved.yes_price == Decimal("0.45")
        assert retrieved.no_price == Decimal("0.55")
        assert retrieved.ts.replace(tzinfo=None) == test_time.replace(tzinfo=None)


def test_edge_creation(test_engine, monkeypatch):
    """Test creating and retrieving edge calculations."""
    # Set up test session with our in-memory engine
    monkeypatch.setattr("arbscan.db.engine", test_engine)

    # Create a test timestamp
    test_time = datetime.datetime(2025, 5, 1, 12, 0, 0, tzinfo=datetime.UTC)

    # Create a test edge record
    with Session(test_engine) as session:
        edge = Edge(
            tag="TEST-TAG",
            yes_exchange="Exchange1",
            no_exchange="Exchange2",
            edge=Decimal("0.053"),
            ts=test_time,
        )
        session.add(edge)
        session.commit()

        # Retrieve edge and verify data
        retrieved = session.exec(select(Edge)).first()
        assert retrieved is not None
        assert retrieved.tag == "TEST-TAG"
        assert retrieved.yes_exchange == "Exchange1"
        assert retrieved.no_exchange == "Exchange2"
        assert retrieved.edge == Decimal("0.053")
        assert retrieved.ts.replace(tzinfo=None) == test_time.replace(tzinfo=None)


def test_init_db(test_engine, monkeypatch):
    """Test database initialization."""
    # Replace the real engine with our test engine
    monkeypatch.setattr("arbscan.db.engine", test_engine)

    # Call the initialization function
    init_db()

    # Verify that tables exist by trying to create a record
    with Session(test_engine) as session:
        # Create a test snapshot
        snapshot = Snapshot(
            tag="INIT-TEST",
            exchange="TestExchange",
            yes_price=Decimal("0.5"),
            no_price=Decimal("0.5"),
            ts=datetime.datetime.now(tz=datetime.UTC),
        )
        session.add(snapshot)
        session.commit()

        # Create a test edge
        edge = Edge(
            tag="INIT-TEST",
            yes_exchange="Exchange1",
            no_exchange="Exchange2",
            edge=Decimal("0.05"),
            ts=datetime.datetime.now(tz=datetime.UTC),
        )
        session.add(edge)
        session.commit()

        # Verify we can query the records
        assert len(session.exec(select(Snapshot)).all()) == 1
        assert len(session.exec(select(Edge)).all()) == 1
