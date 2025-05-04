"""Database module for persisting market data and edge calculations."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine


class Snapshot(SQLModel, table=True):
    """SQLModel for storing market snapshots."""

    id: int | None = Field(default=None, primary_key=True)
    tag: str
    exchange: str
    yes_price: Decimal
    no_price: Decimal
    ts: datetime


class Edge(SQLModel, table=True):
    """SQLModel for storing calculated edges between venues."""

    id: int | None = Field(default=None, primary_key=True)
    tag: str
    yes_exchange: str
    no_exchange: str
    edge: Decimal  # fee-adjusted
    ts: datetime


# Ensure data directory exists
Path("data").mkdir(exist_ok=True)

# Create SQLite engine
engine = create_engine("sqlite:///data/arb.db", echo=False)


def init_db() -> None:
    """Initialize the database schema."""
    SQLModel.metadata.create_all(engine)


def save_snapshot(
    tag: str,
    exchange: str,
    yes_price: Decimal,
    no_price: Decimal,
) -> None:
    """Save a market snapshot to the database.

    Args:
        tag: Event tag
        exchange: Exchange name
        yes_price: Price for YES contract
        no_price: Price for NO contract

    """
    with Session(engine) as session:
        snapshot = Snapshot(
            tag=tag,
            exchange=exchange,
            yes_price=yes_price,
            no_price=no_price,
            ts=datetime.now(tz=UTC),
        )
        session.add(snapshot)
        session.commit()


def save_edge(
    tag: str,
    yes_exchange: str,
    no_exchange: str,
    edge: Decimal,
) -> None:
    """Save a calculated edge to the database.

    Args:
        tag: Event tag
        yes_exchange: Exchange for YES position
        no_exchange: Exchange for NO position
        edge: Calculated edge (fee-adjusted)

    """
    with Session(engine) as session:
        edge_record = Edge(
            tag=tag,
            yes_exchange=yes_exchange,
            no_exchange=no_exchange,
            edge=edge,
            ts=datetime.now(tz=UTC),
        )
        session.add(edge_record)
        session.commit()
