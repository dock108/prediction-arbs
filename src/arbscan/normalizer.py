"""Normalizers for converting venue-specific data to canonical MarketSnapshot format."""

import datetime as dt
from decimal import Decimal
from typing import Any, Protocol

from src.arbscan.market_schema import EventKey, MarketSnapshot, Quote


class VenueAdapter(Protocol):
    """Protocol for venue-specific adapters."""

    def __call__(self, raw: dict[str, Any]) -> MarketSnapshot:
        """Convert venue-specific raw data to MarketSnapshot."""
        ...


def _kalshi_adapter(raw: dict[str, Any]) -> MarketSnapshot:
    """Convert Kalshi API data to MarketSnapshot.

    Kalshi prices are in cents (0-100), needs conversion to Decimal(0-1).
    """
    # Extract common fields for EventKey
    event_data = raw["event"]
    market_data = raw["market"]

    # Parse expiry time
    expiry = dt.datetime.fromisoformat(event_data["close_time"])

    # Create EventKey
    key = EventKey(
        exchange="Kalshi",
        symbol=market_data["ticker"],
        question=market_data["title"],
        expiry=expiry,
        strike=None,  # Kalshi markets are typically binary
        settlement="boolean",
    )

    # Extract YES side data
    yes_bids = market_data.get("yes_bids", [])
    # Break long ternary into separate steps
    if yes_bids:
        yes_price = Decimal(str(yes_bids[0]["price"])) / Decimal("100")
        yes_size = yes_bids[0]["size"]
    else:
        yes_price = Decimal("0")
        yes_size = 0

    # Extract NO side data
    no_bids = market_data.get("no_bids", [])
    # Break long ternary into separate steps
    if no_bids:
        no_price = Decimal(str(no_bids[0]["price"])) / Decimal("100")
        no_size = no_bids[0]["size"]
    else:
        no_price = Decimal("0")
        no_size = 0

    # Get timestamp (using current time if not provided)
    timestamp_str = raw.get("timestamp", dt.datetime.now(dt.UTC).isoformat())
    timestamp = dt.datetime.fromisoformat(timestamp_str)

    # Create Quotes
    best_yes = Quote(
        side="YES",
        price=yes_price,
        size=yes_size,
        ts=timestamp,
    )

    best_no = Quote(
        side="NO",
        price=no_price,
        size=no_size,
        ts=timestamp,
    )

    # Create and return MarketSnapshot
    return MarketSnapshot(
        key=key,
        best_yes=best_yes,
        best_no=best_no,
    )


def _nadex_adapter(raw: dict[str, Any]) -> MarketSnapshot:
    """Convert Nadex API data to MarketSnapshot.

    Nadex prices are in ticks (0-100), needs division by 100.
    """
    # Extract data
    market_data = raw["contract"]

    # Parse expiry time
    expiry_str = market_data["expiry"]
    expiry = dt.datetime.fromisoformat(expiry_str)

    # Create EventKey
    key = EventKey(
        exchange="Nadex",
        symbol=market_data["id"],
        question=market_data["name"],
        expiry=expiry,
        strike=(
            float(market_data.get("strike", 0)) if market_data.get("strike") else None
        ),
        settlement="boolean",
    )

    # Extract YES/NO prices
    yes_price = Decimal(str(market_data["yes_price"])) / Decimal("100")
    no_price = Decimal(str(market_data["no_price"])) / Decimal("100")

    # Get sizes (default to 1 if not provided)
    yes_size = market_data.get("yes_volume", 1)
    no_size = market_data.get("no_volume", 1)

    # Get timestamp
    updated_at = market_data.get("updated_at", dt.datetime.now(dt.UTC).isoformat())
    timestamp = dt.datetime.fromisoformat(updated_at)

    # Create Quotes
    best_yes = Quote(
        side="YES",
        price=yes_price,
        size=yes_size,
        ts=timestamp,
    )

    best_no = Quote(
        side="NO",
        price=no_price,
        size=no_size,
        ts=timestamp,
    )

    # Create and return MarketSnapshot
    return MarketSnapshot(
        key=key,
        best_yes=best_yes,
        best_no=best_no,
    )


def _predictit_adapter(raw: dict[str, Any]) -> MarketSnapshot:
    """Convert PredictIt API data to MarketSnapshot.

    PredictIt prices already in 0-1 range.
    """
    # Extract data
    market_data = raw["market"]
    contract = market_data["contracts"][0]  # Assuming we're passing a single contract

    # Parse expiry time (assuming dateCloses is ISO format)
    expiry_str = market_data.get("dateCloses", market_data.get("dateEnd"))
    expiry = dt.datetime.fromisoformat(expiry_str)

    # Create EventKey
    key = EventKey(
        exchange="PredictIt",
        symbol=f"{market_data['id']}.{contract['id']}",
        question=contract["name"],
        expiry=expiry,
        strike=None,  # PredictIt markets are binary
        settlement="boolean",
    )

    # Extract YES/NO prices, already in 0-1 range
    yes_price = Decimal(str(contract["bestBuyYesCost"]))
    no_price = Decimal(str(contract["bestBuyNoCost"]))

    # Get sizes (default to 1 if not provided)
    yes_size = contract.get("bestBuyYesShares", 1)
    no_size = contract.get("bestBuyNoShares", 1)

    # Get timestamp (using current time if not provided)
    timestamp = dt.datetime.now(dt.UTC)
    if "lastTradePrice" in contract:
        # If available, try to use last trade timestamp
        timestamp_str = contract.get("lastTradeTime")
        if timestamp_str:
            timestamp = dt.datetime.fromisoformat(timestamp_str)

    # Create Quotes
    best_yes = Quote(
        side="YES",
        price=yes_price,
        size=yes_size,
        ts=timestamp,
    )

    best_no = Quote(
        side="NO",
        price=no_price,
        size=no_size,
        ts=timestamp,
    )

    # Create and return MarketSnapshot
    return MarketSnapshot(
        key=key,
        best_yes=best_yes,
        best_no=best_no,
    )


# Registry of adapters by venue
_ADAPTERS: dict[str, VenueAdapter] = {
    "Kalshi": _kalshi_adapter,
    "Nadex": _nadex_adapter,
    "PredictIt": _predictit_adapter,
}


def to_snapshot(raw: dict[str, Any], source: str) -> MarketSnapshot:
    """Convert raw API payload to a canonical MarketSnapshot.

    Args:
        raw: Raw API payload as a dictionary
        source: Source venue - "Kalshi", "Nadex", or "PredictIt"

    Returns:
        MarketSnapshot: Normalized market snapshot

    Raises:
        ValueError: If source is not supported

    """
    if source not in _ADAPTERS:
        supported = ", ".join(_ADAPTERS.keys())
        error_msg = f"Unsupported source: {source}. Supported sources: {supported}"
        raise ValueError(error_msg)

    adapter = _ADAPTERS[source]
    return adapter(raw)
