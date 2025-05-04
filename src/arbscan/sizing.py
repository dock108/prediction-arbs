"""Kelly criterion calculation utilities for optimal bet sizing based on edge."""

from decimal import Decimal, getcontext

getcontext().prec = 6  # sufficient for cents


def kelly(edge: Decimal, odds: Decimal) -> Decimal:
    """Return Kelly fraction (0-1) for a binary bet.

    Args:
        edge: probability_edge (true_prob - offered_prob)
        odds: Decimal payout ratio on winning leg (e.g. 1.08 for 8¢ win on $1 stake)

    Returns:
        The Kelly criterion fraction, clamped between 0 and 1.
        Negative values are clamped to 0.

    """
    # For negative edge, return 0 (don't bet)
    if edge <= Decimal("0"):
        return Decimal("0")

    # Kelly formula: f = (edge * odds) / (odds - 1)
    # This is the simplified formula for when we're directly given the edge
    f = (edge * odds) / (odds - Decimal("1"))

    # Clamp values > 1 to 1
    if f > Decimal("1"):
        return Decimal("1")

    return f
