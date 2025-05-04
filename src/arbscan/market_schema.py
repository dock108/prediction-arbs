"""Canonical data model for market data across different prediction markets."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, TypeVar, cast

YesNo = Literal["YES", "NO"]
T = TypeVar("T")  # Generic type for our dataclasses

# Error messages
ERR_MISSING_TZ = "Datetime must be timezone-aware"
ERR_PRICE_RANGE = "Price must be between 0 and 1"
ERR_WRONG_SIDE_YES = "best_yes quote must have YES side"
ERR_WRONG_SIDE_NO = "best_no quote must have NO side"


@dataclass(frozen=True)
class EventKey:
    """Unique identifier for a prediction market event across exchanges."""

    exchange: str  # "Kalshi" | "Nadex" | "PredictIt"
    symbol: str  # Venue-native contract code / ID
    question: str  # Human-readable question text
    expiry: datetime  # UTC settle/expiry time
    strike: float | None = None  # None for pure binary, else numeric strike
    settlement: Literal["price", "boolean"] = "boolean"  # price-based vs yes/no

    def __post_init__(self) -> None:
        """Validate the EventKey data."""
        # Ensure expiry is timezone-aware and in UTC
        if self.expiry.tzinfo is None:
            raise ValueError(ERR_MISSING_TZ)


@dataclass(frozen=True)
class Quote:
    """Quote data for a single side (YES/NO) of a prediction market."""

    side: YesNo  # "YES" or "NO"
    price: Decimal  # Stored as probability (0-1) in Decimal
    size: int  # Best-bid/ask size in contracts/shares
    ts: datetime  # UTC timestamp of quote snapshot

    def __post_init__(self) -> None:
        """Validate the Quote data."""
        # Ensure price is in valid range
        if not (Decimal("0") <= self.price <= Decimal("1")):
            err_msg = f"{ERR_PRICE_RANGE}, got {self.price}"
            raise ValueError(err_msg)

        # Ensure timestamp is timezone-aware and in UTC
        if self.ts.tzinfo is None:
            raise ValueError(ERR_MISSING_TZ)


@dataclass(frozen=True)
class MarketSnapshot:
    """Complete market snapshot with best quotes for both YES and NO sides."""

    key: EventKey
    best_yes: Quote  # best available YES price/size
    best_no: Quote  # best available NO price/size

    def __post_init__(self) -> None:
        """Validate the MarketSnapshot data."""
        # Ensure sides are correct
        if self.best_yes.side != "YES":
            err_msg = f"{ERR_WRONG_SIDE_YES}, found {self.best_yes.side}"
            raise ValueError(err_msg)
        if self.best_no.side != "NO":
            err_msg = f"{ERR_WRONG_SIDE_NO}, found {self.best_no.side}"
            raise ValueError(err_msg)


# Serialization helpers
class DecimalJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal objects."""

    def default(self, obj: object) -> object:
        """Convert Decimal and datetime objects to strings."""
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def to_json(obj: object) -> str:
    """Convert a dataclass object to a JSON string."""
    return json.dumps(asdict(obj), cls=DecimalJSONEncoder)


def _object_hook(d: dict[str, object]) -> dict[str, object]:
    """Convert string values back to Decimal and datetime objects."""
    result: dict[str, object] = {}
    for k, v in d.items():
        if isinstance(v, str):
            # Try to convert to Decimal if the string represents a number
            if k == "price":
                try:
                    result[k] = Decimal(v)
                    continue
                except (ValueError, TypeError):
                    pass
            # Try to convert to datetime if the string is ISO format
            if k in ("expiry", "ts"):
                try:
                    result[k] = datetime.fromisoformat(v)
                    continue
                except (ValueError, TypeError):
                    pass
        # Handle nested dictionaries
        if isinstance(v, dict):
            result[k] = _object_hook(v)
        else:
            result[k] = v
    return result


def from_json(json_str: str, cls: type[T]) -> T:
    """Convert a JSON string back to a dataclass object."""
    data = json.loads(json_str, object_hook=_object_hook)

    # Special handling for MarketSnapshot
    if cls is MarketSnapshot:
        # Convert nested dicts back to appropriate objects
        event_key = EventKey(**cast("dict[str, object]", data["key"]))
        best_yes = Quote(**cast("dict[str, object]", data["best_yes"]))
        best_no = Quote(**cast("dict[str, object]", data["best_no"]))
        return cast(
            "T",
            MarketSnapshot(key=event_key, best_yes=best_yes, best_no=best_no),
        )

    # For other classes
    return cls(**cast("dict[str, object]", data))
