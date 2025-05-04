"""Tests for edge calculator."""

import datetime as dt
from decimal import Decimal
from unittest import mock

import pytest

from src.arbscan.edge import adjusted_price, calc_edge
from src.arbscan.market_schema import EventKey, MarketSnapshot, Quote

# Test constants
NOW = dt.datetime.now(dt.UTC)
MOCK_FEE_DATA = {
    "Kalshi": {
        "entry_fee": Decimal("0.02"),
        "exit_fee_pct": Decimal("0.00"),
    },
    "Nadex": {
        "entry_fee": Decimal("0.01"),
        "exit_fee_pct": Decimal("0.01"),
    },
    "PredictIt": {
        "entry_fee": Decimal("0.00"),
        "exit_fee_pct": Decimal("0.10"),
    },
}

# Mock tag map for testing
MOCK_TAG_MAP = {
    "Kalshi:SYM1": "TEST-TAG",
    "Nadex:SYM1": "TEST-TAG",
    "PredictIt:SYM1": "TEST-TAG",
    "Kalshi:SYM2": "TAG-A",
    "PredictIt:SYM2": "TAG-B",
}


@pytest.fixture(autouse=True)
def mock_fees():
    """Fixture to mock the fee data for consistent testing."""
    fee_config = {
        "Kalshi": {
            "entry_fee": Decimal("0.02"),
            "exit_fee_pct": Decimal("0.00"),
        },
        "Nadex": {
            "entry_fee": Decimal("0.01"),
            "exit_fee_pct": Decimal("0.01"),
        },
        "PredictIt": {
            "entry_fee": Decimal("0.00"),
            "exit_fee_pct": Decimal("0.10"),
        },
    }

    with (
        mock.patch("src.arbscan.edge._FEE_DATA", MOCK_FEE_DATA),
        mock.patch("src.arbscan.edge._get_fee_config") as mock_get_fee,
    ):
        # Set up mock to return appropriate values
        mock_get_fee.side_effect = lambda exchange: fee_config.get(
            exchange,
            {"entry_fee": Decimal("0"), "exit_fee_pct": Decimal("0")},
        )
        yield


def create_event_key(exchange, symbol="SYM1"):
    """Create event keys for testing."""
    return EventKey(
        exchange=exchange,
        symbol=symbol,
        question="Test question?",
        expiry=NOW,
    )


def create_snapshot(exchange, yes_price, no_price, symbol="SYM1"):
    """Create market snapshots for testing."""
    key = create_event_key(exchange=exchange, symbol=symbol)

    best_yes = Quote(
        side="YES",
        price=Decimal(str(yes_price)),
        size=100,
        ts=NOW,
    )

    best_no = Quote(
        side="NO",
        price=Decimal(str(no_price)),
        size=100,
        ts=NOW,
    )

    return MarketSnapshot(key=key, best_yes=best_yes, best_no=best_no)


def test_adjusted_price_yes_kalshi():
    """Test fee adjustment for Kalshi YES positions."""
    # Kalshi: 2 cent entry fee, no exit fee
    # YES at 0.6 → 0.6 + 0.02 = 0.62
    price = adjusted_price("Kalshi", "YES", Decimal("0.6"))
    assert price == Decimal("0.62")


def test_adjusted_price_no_kalshi():
    """Test fee adjustment for Kalshi NO positions."""
    # Kalshi: 2 cent entry fee, no exit fee
    # NO at 0.4 → (1 - 0.4) + 0.02 = 0.62
    price = adjusted_price("Kalshi", "NO", Decimal("0.4"))
    assert price == Decimal("0.62")


def test_adjusted_price_yes_nadex():
    """Test fee adjustment for Nadex YES positions."""
    # Nadex: 1 cent entry fee, 1% exit fee on profit
    # YES at 0.7:
    price = adjusted_price("Nadex", "YES", Decimal("0.7"))
    assert price == Decimal("0.71") + (Decimal("1") - Decimal("0.71")) * Decimal("0.01")


def test_adjusted_price_yes_predictit():
    """Test fee adjustment for PredictIt YES positions."""
    # PredictIt: no entry fee, 10% exit fee on profit
    # YES at 0.65:
    price = adjusted_price("PredictIt", "YES", Decimal("0.65"))
    assert price == Decimal("0.65") + (Decimal("1") - Decimal("0.65")) * Decimal("0.1")


def test_adjusted_price_limit_case():
    """Test fee adjustment when price would exceed 1.0."""
    # Adjusted price should be capped at 1.0
    price = adjusted_price("Kalshi", "YES", Decimal("0.99"))
    assert price == Decimal("1.0")


def test_calc_edge_arbitrage_opportunity():
    """Test edge calculation with an arbitrage opportunity."""
    # Create snapshots with an arbitrage opportunity
    # Kalshi YES at 0.45, PredictIt NO at 0.48
    snapshot_kalshi = create_snapshot("Kalshi", "0.45", "0.55")
    snapshot_predictit = create_snapshot("PredictIt", "0.52", "0.48")

    # So result should be 0 (no edge)
    edge = calc_edge(snapshot_kalshi, snapshot_predictit, MOCK_TAG_MAP)
    assert edge == Decimal("0")


def test_calc_edge_with_edge():
    """Test edge calculation with a positive edge."""
    # Create snapshots with a clear edge opportunity
    # Kalshi YES at 0.10, PredictIt NO at 0.10
    # This creates a wide spread that should result in a clear edge
    snapshot_kalshi = create_snapshot("Kalshi", "0.10", "0.90")
    snapshot_predictit = create_snapshot("PredictIt", "0.90", "0.10")

    with mock.patch("src.arbscan.edge.adjusted_price") as mock_adjusted_price:
        # Set up mock to return values that will create a positive edge
        mock_adjusted_price.side_effect = lambda exchange, side, price: {
            ("Kalshi", "YES", Decimal("0.10")): Decimal("0.35"),
            ("Kalshi", "NO", Decimal("0.90")): Decimal("0.75"),
            ("PredictIt", "YES", Decimal("0.90")): Decimal("0.73"),
            ("PredictIt", "NO", Decimal("0.10")): Decimal("0.33"),
        }[(exchange, side, price)]

        edge = calc_edge(snapshot_kalshi, snapshot_predictit, MOCK_TAG_MAP)

        # Expected edge: (1 - 0.35) - 0.33 = 0.65 - 0.33 = 0.32
        assert edge == Decimal("0.32")


def test_calc_edge_mismatched_tags():
    """Test edge calculation with mismatched tags."""
    snapshot_a = create_snapshot("Kalshi", "0.5", "0.5", symbol="SYM2")
    snapshot_b = create_snapshot("PredictIt", "0.5", "0.5", symbol="SYM2")

    with pytest.raises(ValueError, match="Snapshots must have matching tags"):
        calc_edge(snapshot_a, snapshot_b, MOCK_TAG_MAP)


def test_calc_edge_missing_tag():
    """Test edge calculation with missing tag."""
    # Create snapshots with symbols not in the tag map
    snapshot_a = create_snapshot("Kalshi", "0.5", "0.5", symbol="UNKNOWN")
    snapshot_b = create_snapshot("PredictIt", "0.5", "0.5", symbol="UNKNOWN")

    with pytest.raises(ValueError, match="Snapshots must include event tags"):
        calc_edge(snapshot_a, snapshot_b, MOCK_TAG_MAP)
