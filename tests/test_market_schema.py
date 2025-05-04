"""Unit tests for the market_schema module."""

import datetime as dt
from decimal import Decimal

import pytest

from arbscan.market_schema import (
    EventKey,
    MarketSnapshot,
    Quote,
    from_json,
    to_json,
)

# Constants for test values
PRICE_YES = Decimal("0.65")
PRICE_NO = Decimal("0.38")
SIZE_100 = 100
SIZE_50 = 50
STRIKE_40000 = 40000.0


def test_event_key_creation() -> None:
    """Test that EventKey objects can be created properly."""
    now = dt.datetime.now(dt.UTC)

    # Test successful creation
    event_key = EventKey(
        exchange="PredictIt",
        symbol="BIDEN.PRES.123456",
        question="Will Biden win the 2025 election?",
        expiry=now,
    )

    assert event_key.exchange == "PredictIt"
    assert event_key.symbol == "BIDEN.PRES.123456"
    assert event_key.question == "Will Biden win the 2025 election?"
    assert event_key.expiry == now
    assert event_key.strike is None
    assert event_key.settlement == "boolean"

    # Test with explicit optional values
    event_key_with_strike = EventKey(
        exchange="Kalshi",
        symbol="SPX-40000",
        question="Will SPX close above 40000?",
        expiry=now,
        strike=STRIKE_40000,
        settlement="price",
    )

    assert event_key_with_strike.strike == STRIKE_40000
    assert event_key_with_strike.settlement == "price"


def test_event_key_validation() -> None:
    """Test that EventKey objects are validated correctly."""
    # Test with timezone-naive datetime (should raise ValueError)
    with pytest.raises(ValueError, match="timezone-aware"):
        EventKey(
            exchange="PredictIt",
            symbol="BIDEN.PRES.123456",
            question="Will Biden win the 2025 election?",
            expiry=dt.datetime.now(dt.UTC).replace(tzinfo=None),  # No timezone
        )


def test_quote_creation() -> None:
    """Test that Quote objects can be created properly."""
    now = dt.datetime.now(dt.UTC)

    # Test successful creation
    quote = Quote(
        side="YES",
        price=PRICE_YES,
        size=SIZE_100,
        ts=now,
    )

    assert quote.side == "YES"
    assert quote.price == PRICE_YES
    assert quote.size == SIZE_100
    assert quote.ts == now


def test_quote_validation() -> None:
    """Test that Quote objects are validated correctly."""
    now = dt.datetime.now(dt.UTC)

    # Test with price out of range (should raise ValueError)
    with pytest.raises(ValueError, match="between 0 and 1"):
        Quote(
            side="YES",
            price=Decimal("1.2"),  # Invalid price
            size=SIZE_100,
            ts=now,
        )

    # Test with price out of range (should raise ValueError)
    with pytest.raises(ValueError, match="between 0 and 1"):
        Quote(
            side="NO",
            price=Decimal("-0.1"),  # Invalid price
            size=SIZE_50,
            ts=now,
        )

    # Test with timezone-naive datetime (should raise ValueError)
    with pytest.raises(ValueError, match="timezone-aware"):
        Quote(
            side="YES",
            price=Decimal("0.5"),
            size=SIZE_100,
            ts=dt.datetime.now(dt.UTC).replace(tzinfo=None),  # No timezone
        )


def test_market_snapshot_creation() -> None:
    """Test that MarketSnapshot objects can be created properly."""
    now = dt.datetime.now(dt.UTC)

    event_key = EventKey(
        exchange="PredictIt",
        symbol="BIDEN.PRES.123456",
        question="Will Biden win the 2025 election?",
        expiry=now,
    )

    yes_quote = Quote(
        side="YES",
        price=PRICE_YES,
        size=SIZE_100,
        ts=now,
    )

    no_quote = Quote(
        side="NO",
        price=PRICE_NO,
        size=SIZE_50,
        ts=now,
    )

    # Test successful creation
    snapshot = MarketSnapshot(
        key=event_key,
        best_yes=yes_quote,
        best_no=no_quote,
    )

    assert snapshot.key == event_key
    assert snapshot.best_yes == yes_quote
    assert snapshot.best_no == no_quote


def test_market_snapshot_validation() -> None:
    """Test that MarketSnapshot objects are validated correctly."""
    now = dt.datetime.now(dt.UTC)

    event_key = EventKey(
        exchange="PredictIt",
        symbol="BIDEN.PRES.123456",
        question="Will Biden win the 2025 election?",
        expiry=now,
    )

    yes_quote = Quote(
        side="YES",
        price=PRICE_YES,
        size=SIZE_100,
        ts=now,
    )

    no_quote = Quote(
        side="NO",
        price=PRICE_NO,
        size=SIZE_50,
        ts=now,
    )

    # Create quotes with wrong sides
    wrong_yes_quote = Quote(
        side="NO",  # Wrong side
        price=PRICE_YES,
        size=SIZE_100,
        ts=now,
    )

    wrong_no_quote = Quote(
        side="YES",  # Wrong side
        price=PRICE_NO,
        size=SIZE_50,
        ts=now,
    )

    # Test with wrong side for yes quote
    with pytest.raises(ValueError, match="best_yes quote must have YES side"):
        MarketSnapshot(
            key=event_key,
            best_yes=wrong_yes_quote,
            best_no=no_quote,
        )

    # Test with wrong side for no quote
    with pytest.raises(ValueError, match="best_no quote must have NO side"):
        MarketSnapshot(
            key=event_key,
            best_yes=yes_quote,
            best_no=wrong_no_quote,
        )


def test_json_serialization() -> None:
    """Test that objects can be serialized to and from JSON."""
    now = dt.datetime.now(dt.UTC)

    # Create sample objects
    event_key = EventKey(
        exchange="PredictIt",
        symbol="BIDEN.PRES.123456",
        question="Will Biden win the 2025 election?",
        expiry=now,
        strike=None,
        settlement="boolean",
    )

    yes_quote = Quote(
        side="YES",
        price=PRICE_YES,
        size=SIZE_100,
        ts=now,
    )

    no_quote = Quote(
        side="NO",
        price=PRICE_NO,
        size=SIZE_50,
        ts=now,
    )

    snapshot = MarketSnapshot(
        key=event_key,
        best_yes=yes_quote,
        best_no=no_quote,
    )

    # Test EventKey serialization
    event_key_json = to_json(event_key)
    event_key_deserialized = from_json(event_key_json, EventKey)
    assert event_key == event_key_deserialized

    # Test Quote serialization
    yes_quote_json = to_json(yes_quote)
    yes_quote_deserialized = from_json(yes_quote_json, Quote)
    assert yes_quote == yes_quote_deserialized

    # Test MarketSnapshot serialization
    snapshot_json = to_json(snapshot)
    snapshot_deserialized = from_json(snapshot_json, MarketSnapshot)
    assert snapshot == snapshot_deserialized


def test_json_decimal_handling() -> None:
    """Test that Decimal values are properly handled in JSON serialization."""
    now = dt.datetime.now(dt.UTC)

    # Create a quote with a Decimal price
    quote = Quote(
        side="YES",
        price=PRICE_YES,
        size=SIZE_100,
        ts=now,
    )

    # Serialize and deserialize
    quote_json = to_json(quote)
    quote_deserialized = from_json(quote_json, Quote)

    # Check that the price is still a Decimal
    assert isinstance(quote_deserialized.price, Decimal)
    assert quote_deserialized.price == PRICE_YES


def test_json_datetime_handling() -> None:
    """Test that datetime values are properly handled in JSON serialization."""
    now = dt.datetime.now(dt.UTC)

    # Create an EventKey with a datetime
    event_key = EventKey(
        exchange="PredictIt",
        symbol="BIDEN.PRES.123456",
        question="Will Biden win the 2025 election?",
        expiry=now,
    )

    # Serialize and deserialize
    event_key_json = to_json(event_key)
    event_key_deserialized = from_json(event_key_json, EventKey)

    # Check that the expiry is still a timezone-aware datetime
    assert isinstance(event_key_deserialized.expiry, dt.datetime)
    assert event_key_deserialized.expiry.tzinfo is not None
    assert event_key_deserialized.expiry == now
