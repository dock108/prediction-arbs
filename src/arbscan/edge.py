"""Edge calculator for cross-venue arbitrage opportunities.

Calculates fee-adjusted edge between two market snapshots from different venues.
"""

from decimal import Decimal
from pathlib import Path

import yaml

from src.arbscan.market_schema import MarketSnapshot, YesNo

# Constants
ONE = Decimal("1")
DEFAULT_FEE = {"entry_fee": Decimal("0"), "exit_fee_pct": Decimal("0")}

# Load fee structure from YAML
FEES_PATH = Path(__file__).parent / "fees.yaml"
try:
    with FEES_PATH.open() as f:
        _FEE_DATA = yaml.safe_load(f)
except (FileNotFoundError, yaml.YAMLError):
    # Fallback to empty fee structure
    _FEE_DATA = {}


def _get_fee_config(exchange: str) -> dict[str, Decimal]:
    """Get fee configuration for a specific exchange.

    Args:
        exchange: Exchange name (case-insensitive)

    Returns:
        Dictionary with entry_fee and exit_fee_pct values

    """
    # Normalize exchange name
    normalized_exchange = exchange.capitalize()

    # Get fee data or default
    fee_data = _FEE_DATA.get(normalized_exchange, DEFAULT_FEE)

    # Convert to Decimal
    return {
        "entry_fee": Decimal(str(fee_data.get("entry_fee", 0))),
        "exit_fee_pct": Decimal(str(fee_data.get("exit_fee_pct", 0))),
    }


def adjusted_price(exchange: str, side: YesNo, price: Decimal) -> Decimal:
    """Calculate fee-adjusted price for a specific exchange and side.

    Args:
        exchange: The exchange name (Kalshi, Nadex, PredictIt)
        side: The position side ("YES" or "NO")
        price: The raw probability price (0-1)

    Returns:
        Fee-adjusted price accounting for entry and estimated exit fees

    """
    fee_config = _get_fee_config(exchange)
    entry_fee = fee_config["entry_fee"]
    exit_fee_pct = fee_config["exit_fee_pct"]

    # For YES positions:
    # - Entry cost: price + entry_fee
    # - Exit fee on profit: (1 - entry_cost) * exit_fee_pct
    if side == "YES":
        entry_cost = price + entry_fee
        # Cap at 1.0 to avoid invalid probabilities
        if entry_cost > ONE:
            return ONE

        profit_fee = (ONE - entry_cost) * exit_fee_pct
        return entry_cost + profit_fee

    # For NO positions:
    # - Entry cost: (1 - price) + entry_fee
    # - Exit fee on profit: price * exit_fee_pct
    entry_cost = (ONE - price) + entry_fee
    # Cap at 1.0 to avoid invalid probabilities
    if entry_cost > ONE:
        return ONE

    profit_fee = price * exit_fee_pct
    return entry_cost + profit_fee


def calc_edge(
    snapshot_a: MarketSnapshot,
    snapshot_b: MarketSnapshot,
    tag_map: dict[str, str] | None = None,
) -> Decimal:
    """Calculate the edge between two market snapshots after fees.

    Args:
        snapshot_a: First market snapshot
        snapshot_b: Second market snapshot
        tag_map: Optional dictionary mapping exchange+symbol to tag

    Returns:
        Fee-adjusted edge as a decimal (negative if no edge)

    Raises:
        ValueError: If the two snapshots don't have matching tags

    """

    # Helper to get tag for a snapshot
    def get_tag(snapshot: MarketSnapshot) -> str | None:
        # If we have a tag_map, look up by exchange and symbol
        if tag_map is not None:
            key = f"{snapshot.key.exchange}:{snapshot.key.symbol}"
            return tag_map.get(key)

        # Fallback to checking for a tag attribute
        return getattr(snapshot.key, "tag", None)

    # Get tags for both snapshots
    tag_a = get_tag(snapshot_a)
    tag_b = get_tag(snapshot_b)

    # Ensure we're comparing the same event
    if tag_a is None or tag_b is None:
        error_msg = "Snapshots must include event tags to calculate edge"
        raise ValueError(error_msg)

    if tag_a != tag_b:
        error_msg = f"Snapshots must have matching tags, got {tag_a} and {tag_b}"
        raise ValueError(error_msg)

    # Calculate fee-adjusted prices
    yes_price_a = adjusted_price(
        snapshot_a.key.exchange,
        "YES",
        snapshot_a.best_yes.price,
    )
    no_price_a = adjusted_price(snapshot_a.key.exchange, "NO", snapshot_a.best_no.price)

    yes_price_b = adjusted_price(
        snapshot_b.key.exchange,
        "YES",
        snapshot_b.best_yes.price,
    )
    no_price_b = adjusted_price(snapshot_b.key.exchange, "NO", snapshot_b.best_no.price)

    # Calculate potential edges (YES on one venue vs NO on the other)
    edge_a_yes_b_no = (ONE - yes_price_a) - no_price_b
    edge_b_yes_a_no = (ONE - yes_price_b) - no_price_a

    # Return the best edge (or negative if no edge exists)
    return max(edge_a_yes_b_no, edge_b_yes_a_no, Decimal("0"))
