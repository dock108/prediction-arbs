"""Tests for edge calculation."""

import datetime as dt
from decimal import Decimal
from unittest import mock

import pytest

from arbscan.edge import adjusted_price, calc_edge
from arbscan.market_schema import EventKey, MarketSnapshot, Quote

# Constants for testing
MOCK_TAG_MAP: dict[str, str] = {
    "Kalshi:TEST-Kalshi": "TEST-TAG",
    "PredictIt:TEST-PredictIt": "TEST-TAG",
}

# Create a timezone-aware datetime for testing
TEST_DATE = dt.datetime(2025, 5, 31, 23, 59, 59, tzinfo=dt.UTC)


@pytest.fixture
def fee_data():
    """Mock fee data for testing."""
    return {
        "Kalshi": {"entry_fee": 0.02, "exit_fee_pct": 0.02},
        "PredictIt": {"entry_fee": 0, "exit_fee_pct": 0.1},
        "Nadex": {"entry_fee": 0.03, "exit_fee_pct": 0.0},
    }


def create_snapshot(exchange, yes_price, no_price):
    """Create a test market snapshot with specified prices."""
    key = EventKey(
        exchange=exchange,
        symbol=f"TEST-{exchange}",
        question="Will BTC close above $70K on May 31?",
        expiry=TEST_DATE,
        strike=None,
        settlement="boolean",
    )
    best_yes = Quote(
        side="YES",
        price=Decimal(yes_price),
        size=100,
        ts=TEST_DATE,
    )
    best_no = Quote(
        side="NO",
        price=Decimal(no_price),
        size=100,
        ts=TEST_DATE,
    )
    return MarketSnapshot(key=key, best_yes=best_yes, best_no=best_no)


def test_adjusted_price_yes_no_diff():
    """Test that YES and NO positions are adjusted differently."""
    exchange = "Kalshi"
    yes_price = Decimal("0.60")
    no_price = Decimal("0.40")

    # Mock the fee config
    with mock.patch("arbscan.edge._get_fee_config") as mock_get_fee:
        mock_get_fee.return_value = {
            "entry_fee": Decimal("0.02"),
            "exit_fee_pct": Decimal("0.05"),
        }

        yes_adjusted = adjusted_price(exchange, "YES", yes_price)
        no_adjusted = adjusted_price(exchange, "NO", no_price)

        # Fee adjustments should increase prices
        assert yes_adjusted > yes_price
        assert no_adjusted > Decimal("1") - no_price

        # Verify different adjustment logic
        assert yes_adjusted != no_adjusted


def test_adjusted_price_yes_kalshi():
    """Test fee adjustment for Kalshi YES positions."""
    # Kalshi has a 2 cent entry fee based on the actual implementation
    price = adjusted_price("Kalshi", "YES", Decimal("0.60"))
    assert price == Decimal("0.62")


def test_adjusted_price_no_kalshi():
    """Test fee adjustment for Kalshi NO positions."""
    # Kalshi has a 2 cent entry fee based on the actual implementation
    price = adjusted_price("Kalshi", "NO", Decimal("0.40"))
    assert price == Decimal("0.62")


def test_adjusted_price_yes_predictit():
    """Test fee adjustment for PredictIt YES positions."""
    # PredictIt: no entry fee, 10% exit fee on profit
    # YES at 0.65:
    with mock.patch("arbscan.edge._get_fee_config") as mock_get_fee:
        mock_get_fee.return_value = {
            "entry_fee": Decimal("0"),
            "exit_fee_pct": Decimal("0.1"),
        }

        price = adjusted_price("PredictIt", "YES", Decimal("0.65"))
        # Expected profit fee calculation
        yes_price = Decimal("0.65")
        profit = Decimal("1") - yes_price
        profit_fee = profit * Decimal("0.1")
        assert price == yes_price + profit_fee


def test_adjusted_price_no_predictit():
    """Test fee adjustment for PredictIt NO positions."""
    # PredictIt: no entry fee, 10% exit fee on profit
    # NO at 0.35:
    with mock.patch("arbscan.edge._get_fee_config") as mock_get_fee:
        mock_get_fee.return_value = {
            "entry_fee": Decimal("0"),
            "exit_fee_pct": Decimal("0.1"),
        }

        price = adjusted_price("PredictIt", "NO", Decimal("0.35"))
        # Expected profit fee calculation
        no_price = Decimal("0.35")
        no_cost = Decimal("1") - no_price
        profit_fee = no_price * Decimal("0.1")
        assert price == no_cost + profit_fee


def test_calc_edge_arbitrage_opportunity():
    """Test edge calculation with an arbitrage opportunity."""
    # Create snapshots with an arbitrage opportunity
    # Kalshi YES at 0.45, PredictIt NO at 0.48
    snapshot_kalshi = create_snapshot("Kalshi", "0.45", "0.55")
    snapshot_predictit = create_snapshot("PredictIt", "0.52", "0.48")

    # Mock the fee calculation to ensure consistent test results
    with mock.patch("arbscan.edge.adjusted_price") as mock_adjusted_price:
        # No edge after fees
        mock_adjusted_price.side_effect = lambda exchange, side, price: {
            ("Kalshi", "YES", Decimal("0.45")): Decimal("0.50"),
            ("Kalshi", "NO", Decimal("0.55")): Decimal("0.50"),
            ("PredictIt", "YES", Decimal("0.52")): Decimal("0.50"),
            ("PredictIt", "NO", Decimal("0.48")): Decimal("0.50"),
        }[(exchange, side, price)]

        # Calculate edge with mocked fee adjustments
        edge = calc_edge(snapshot_kalshi, snapshot_predictit, MOCK_TAG_MAP)

        # Should be 0 after fees
        assert edge == Decimal("0")


def test_calc_edge_with_edge():
    """Test edge calculation with a positive edge."""
    # Create snapshots with a clear edge opportunity
    # Kalshi YES at 0.10, PredictIt NO at 0.10
    # This creates a wide spread that should result in a clear edge
    snapshot_kalshi = create_snapshot("Kalshi", "0.10", "0.90")
    snapshot_predictit = create_snapshot("PredictIt", "0.90", "0.10")

    with mock.patch("arbscan.edge.adjusted_price") as mock_adjusted_price:
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


def test_calc_edge_no_edge():
    """Test edge calculation with no edge."""
    # Create snapshots with no edge opportunity
    snapshot_kalshi = create_snapshot("Kalshi", "0.55", "0.45")
    snapshot_predictit = create_snapshot("PredictIt", "0.45", "0.55")

    with mock.patch("arbscan.edge.adjusted_price") as mock_adjusted_price:
        # Set up mock to return values that will not create an edge
        mock_adjusted_price.side_effect = lambda exchange, side, price: {
            ("Kalshi", "YES", Decimal("0.55")): Decimal("0.60"),
            ("Kalshi", "NO", Decimal("0.45")): Decimal("0.60"),
            ("PredictIt", "YES", Decimal("0.45")): Decimal("0.60"),
            ("PredictIt", "NO", Decimal("0.55")): Decimal("0.60"),
        }[(exchange, side, price)]

        edge = calc_edge(snapshot_kalshi, snapshot_predictit, MOCK_TAG_MAP)

        # Expected edge: max(0, -0.20, -0.20) = 0
        assert edge == Decimal("0")
