"""Utility for matching event symbols across prediction market venues.

Provides functionality to convert between venue-specific symbols and
canonical event tags defined in the event registry YAML.
"""

import os
from pathlib import Path
from typing import Any

import yaml

# Find the repo root directory (where event_registry.yaml should be)
REPO_ROOT = Path(__file__).parent.parent.parent
REGISTRY_PATH = REPO_ROOT / "event_registry.yaml"

# Load registry once at import time
try:
    with REGISTRY_PATH.open() as f:
        _REGISTRY: list[dict[str, Any]] = yaml.safe_load(f)
except (FileNotFoundError, yaml.YAMLError):
    # Fallback to environment variable if file not found or invalid
    registry_path_env = os.environ.get("EVENT_REGISTRY_PATH")
    if registry_path_env:
        try:
            registry_path = Path(registry_path_env)
            with registry_path.open() as f:
                _REGISTRY = yaml.safe_load(f)
        except (FileNotFoundError, yaml.YAMLError):
            _REGISTRY = []
    else:
        _REGISTRY = []

# Build reverse lookup maps for each venue (exchange_symbol -> tag)
_VENUE_TO_TAG_MAPS = {
    venue: {
        entry[venue]: entry["tag"]
        for entry in _REGISTRY
        if entry.get(venue) is not None
    }
    for venue in ["kalshi", "nadex", "predictit"]
}


def tag_from(exchange: str, symbol: str) -> str | None:
    """Get canonical tag from venue-specific symbol.

    Args:
        exchange: The exchange name (kalshi, nadex, predictit)
        symbol: The exchange-specific symbol or ID

    Returns:
        Canonical tag if found, None otherwise

    """
    # Handle market ID for PredictIt (convert to string if int)
    if exchange == "predictit" and isinstance(symbol, int):
        symbol = str(symbol)

    # Look up in the appropriate reverse map
    venue_map = _VENUE_TO_TAG_MAPS.get(exchange, {})
    return venue_map.get(symbol)


def venues_for(tag: str) -> dict[str, str]:
    """Get all venue-specific symbols for a canonical tag.

    Args:
        tag: The canonical event tag

    Returns:
        Dictionary mapping exchange names to their specific symbols
        (only includes exchanges that have this event)

    """
    for entry in _REGISTRY:
        if entry["tag"] == tag:
            # Filter out venues where the symbol is None
            return {
                venue: symbol
                for venue, symbol in entry.items()
                if venue not in ["tag", "description"] and symbol is not None
            }

    # Tag not found
    return {}
