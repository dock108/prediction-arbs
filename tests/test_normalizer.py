"""Tests for the normalizer module."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.arbscan.market_schema import MarketSnapshot
from src.arbscan.normalizer import to_snapshot

# Constants
MIN_PRICE_SUM = Decimal("0.95")  # Minimum acceptable sum of YES + NO prices
MAX_PRICE_SUM = Decimal("1.05")  # Maximum acceptable sum of YES + NO prices
NADEX_STRIKE_VALUE = 40000.0  # Expected strike value in Nadex test


def _load_fixture(filename: str) -> dict:
    """Load a fixture file from the fixtures directory."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixture_path = fixtures_dir / filename

    with fixture_path.open() as f:
        return json.load(f)


def test_to_snapshot_kalshi() -> None:
    """Test conversion of Kalshi data to MarketSnapshot."""
    # Load fixture
    raw_data = _load_fixture("kalshi_example.json")

    # Convert to snapshot
    snapshot = to_snapshot(raw_data, "Kalshi")

    # Verify it's a MarketSnapshot
    assert isinstance(snapshot, MarketSnapshot)

    # Check exchange
    assert snapshot.key.exchange == "Kalshi"

    # Check prices are in range 0-1
    assert 0 <= snapshot.best_yes.price <= 1
    assert 0 <= snapshot.best_no.price <= 1

    # Check specific price conversion (Kalshi uses cents)
    assert snapshot.best_yes.price == Decimal("0.46")
    assert snapshot.best_no.price == Decimal("0.55")

    # Verify YES + NO roughly adds to ~1 (with fee spread)
    price_sum = snapshot.best_yes.price + snapshot.best_no.price
    assert MIN_PRICE_SUM <= price_sum <= MAX_PRICE_SUM  # Allow for market maker spread


def test_to_snapshot_nadex() -> None:
    """Test conversion of Nadex data to MarketSnapshot."""
    # Load fixture
    raw_data = _load_fixture("nadex_example.json")

    # Convert to snapshot
    snapshot = to_snapshot(raw_data, "Nadex")

    # Verify it's a MarketSnapshot
    assert isinstance(snapshot, MarketSnapshot)

    # Check exchange
    assert snapshot.key.exchange == "Nadex"

    # Check prices are in range 0-1
    assert 0 <= snapshot.best_yes.price <= 1
    assert 0 <= snapshot.best_no.price <= 1

    # Check specific price conversion (Nadex uses 0-100 ticks)
    assert snapshot.best_yes.price == Decimal("0.25")
    assert snapshot.best_no.price == Decimal("0.75")

    # Verify YES + NO roughly adds to ~1
    price_sum = snapshot.best_yes.price + snapshot.best_no.price
    assert MIN_PRICE_SUM <= price_sum <= MAX_PRICE_SUM  # Allow for market maker spread

    # Check strike value was properly extracted
    assert snapshot.key.strike == NADEX_STRIKE_VALUE


def test_to_snapshot_predictit() -> None:
    """Test conversion of PredictIt data to MarketSnapshot."""
    # Load fixture
    raw_data = _load_fixture("predictit_example.json")

    # Convert to snapshot
    snapshot = to_snapshot(raw_data, "PredictIt")

    # Verify it's a MarketSnapshot
    assert isinstance(snapshot, MarketSnapshot)

    # Check exchange
    assert snapshot.key.exchange == "PredictIt"

    # Check prices are in range 0-1
    assert 0 <= snapshot.best_yes.price <= 1
    assert 0 <= snapshot.best_no.price <= 1

    # Check specific price conversion (PredictIt already uses 0-1)
    assert snapshot.best_yes.price == Decimal("0.59")
    assert snapshot.best_no.price == Decimal("0.42")

    # Verify symbol format is correct
    assert snapshot.key.symbol == "5123.15789"


def test_to_snapshot_invalid_source() -> None:
    """Test that to_snapshot raises ValueError for invalid source."""
    raw_data = {}  # Empty dict, won't be used

    with pytest.raises(ValueError, match="Unsupported source"):
        to_snapshot(raw_data, "InvalidSource")
