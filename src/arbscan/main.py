"""Command-line entry point for the arbitrage scanner."""

import os
import signal
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import click
import yaml

from arbscan.alerts import AlertSink, SlackSink, StdoutSink
from arbscan.db import init_db, save_edge, save_snapshot
from arbscan.edge import calc_edge
from arbscan.kalshi_client import KalshiClient
from arbscan.matcher import venues_for
from arbscan.nadex_client import NadexClient
from arbscan.normalizer import to_snapshot
from arbscan.predictit_client import PredictItClient
from arbscan.sizing import kelly

# Find the repo root directory (where event_registry.yaml should be)
REPO_ROOT = Path(__file__).parent.parent.parent
REGISTRY_PATH = REPO_ROOT / "event_registry.yaml"
MIN_VENUES_FOR_ARBITRAGE = 2

# Map of exchange names to client classes
CLIENTS = {
    "kalshi": KalshiClient,
    "nadex": NadexClient,
    "predictit": PredictItClient,
}

# Map of exchange names to normalizer source names
NORMALIZER_SOURCES = {
    "kalshi": "Kalshi",
    "nadex": "Nadex",
    "predictit": "PredictIt",
}


def load_registry() -> list[dict[str, Any]]:
    """Load the event registry from YAML.

    Returns:
        List of event entries from the registry

    """
    try:
        with REGISTRY_PATH.open() as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        # Try environment variable if file not found
        registry_path_env = os.environ.get("EVENT_REGISTRY_PATH")
        if registry_path_env:
            try:
                with Path(registry_path_env).open() as f:
                    return yaml.safe_load(f)
            except (FileNotFoundError, yaml.YAMLError):
                pass
        # If all attempts fail, show error and exit
        click.echo(f"Error loading event registry: {e}", err=True)
        return []


def get_client(exchange: str) -> KalshiClient | NadexClient | PredictItClient:
    """Get a client instance for the specified exchange.

    Args:
        exchange: Exchange name (kalshi, nadex, predictit)

    Returns:
        Client instance for the exchange

    """
    client_class = CLIENTS.get(exchange.lower())
    if client_class is None:
        error_msg = f"Unsupported exchange: {exchange}"
        raise ValueError(error_msg)
    return client_class()


def fetch_market_data(exchange: str, symbol: str) -> dict:
    """Fetch market data for the specified exchange and symbol.

    Args:
        exchange: Exchange name
        symbol: Market symbol

    Returns:
        Raw market data

    """
    client = get_client(exchange)

    # Call the appropriate method based on the exchange
    if exchange.lower() == "kalshi":
        return client.get_market(symbol)
    if exchange.lower() == "nadex":
        return client.get_contract(symbol)
    if exchange.lower() == "predictit":
        # PredictIt expects an integer market ID
        return client.get_market(int(symbol))

    error_msg = f"Unsupported exchange: {exchange}"
    raise ValueError(error_msg)


def format_alert_message(  # noqa: PLR0913
    tag: str,
    edge: Decimal,
    venue_a: str,
    venue_b: str,
    side_a: str,
    price_a: Decimal,
    side_b: str,
    price_b: Decimal,
    bankroll: float | None = None,
) -> str:
    """Format alert message for an arbitrage opportunity.

    Args:
        tag: Event tag
        edge: Calculated edge
        venue_a: First venue
        venue_b: Second venue
        side_a: Side (YES/NO) for first venue
        price_a: Price for first venue
        side_b: Side (YES/NO) for second venue
        price_b: Price for second venue
        bankroll: Optional bankroll amount for Kelly sizing

    Returns:
        Formatted alert message

    """
    # Format edge as percentage with 2 decimal places
    edge_pct = edge * 100

    # Create the basic alert message
    message = (
        f"EDGE {edge_pct:.3f} | {tag} {side_a}@{venue_a} {price_a:.2f} "
        f"vs {side_b}@{venue_b} {price_b:.2f}"
    )

    # Add Kelly stake if bankroll is provided
    if bankroll is not None:
        # Calculate Kelly fraction (using 2.0 as a conservative odds estimate)
        k = kelly(edge, Decimal("2.0"))
        stake = float(k) * bankroll
        message += f" | Kelly stake: ${stake:.0f}"

    return message


def get_alert_sink() -> AlertSink:
    """Get the appropriate alert sink based on environment.

    Returns:
        Alert sink (SlackSink if webhook URL is set, StdoutSink otherwise)

    """
    try:
        return SlackSink()
    except RuntimeError:
        return StdoutSink()


def check_venue_pair(  # noqa: PLR0913
    venue_a: str,
    venue_b: str,
    symbols_a: str,
    symbols_b: str,
    tag: str,
    threshold_decimal: Decimal,
    alert_sink: AlertSink,
    bankroll: float | None = None,
) -> None:
    """Check a single pair of venues for arbitrage opportunities.

    Args:
        venue_a: First venue name
        venue_b: Second venue name
        symbols_a: Symbol for first venue
        symbols_b: Symbol for second venue
        tag: Event tag
        threshold_decimal: Minimum edge threshold
        alert_sink: Alert sink for notifications
        bankroll: Optional bankroll amount for Kelly sizing

    """
    try:
        # Fetch market data for both venues
        data_a = fetch_market_data(venue_a, symbols_a)
        data_b = fetch_market_data(venue_b, symbols_b)

        # Convert to canonical snapshots
        snapshot_a = to_snapshot(data_a, NORMALIZER_SOURCES[venue_a])
        snapshot_b = to_snapshot(data_b, NORMALIZER_SOURCES[venue_b])

        # Save snapshots to database
        save_snapshot(
            tag=tag,
            exchange=venue_a,
            yes_price=snapshot_a.best_yes.price,
            no_price=snapshot_a.best_no.price,
        )

        save_snapshot(
            tag=tag,
            exchange=venue_b,
            yes_price=snapshot_b.best_yes.price,
            no_price=snapshot_b.best_no.price,
        )

        # Calculate edge
        edge = calc_edge(snapshot_a, snapshot_b)

        # Determine which combination gives the higher edge
        yes_a_no_b = (
            Decimal("1") - snapshot_a.best_yes.price
        ) - snapshot_b.best_no.price
        yes_b_no_a = (
            Decimal("1") - snapshot_b.best_yes.price
        ) - snapshot_a.best_no.price

        # Save edge to database regardless of threshold
        if yes_a_no_b >= yes_b_no_a:
            # YES on venue_a, NO on venue_b is better
            save_edge(
                tag=tag,
                yes_exchange=venue_a,
                no_exchange=venue_b,
                edge=edge,
            )
        else:
            # YES on venue_b, NO on venue_a is better
            save_edge(
                tag=tag,
                yes_exchange=venue_b,
                no_exchange=venue_a,
                edge=edge,
            )

        # If edge exceeds threshold, send alert
        if edge >= threshold_decimal:
            if yes_a_no_b >= yes_b_no_a:
                message = format_alert_message(
                    tag,
                    edge,
                    venue_a.capitalize(),
                    venue_b.capitalize(),
                    "YES",
                    snapshot_a.best_yes.price,
                    "NO",
                    snapshot_b.best_no.price,
                    bankroll,
                )
            else:
                message = format_alert_message(
                    tag,
                    edge,
                    venue_b.capitalize(),
                    venue_a.capitalize(),
                    "YES",
                    snapshot_b.best_yes.price,
                    "NO",
                    snapshot_a.best_no.price,
                    bankroll,
                )

            alert_sink.send(message)

    except ValueError as e:
        click.echo(
            f"Value error checking {venue_a} vs {venue_b} for {tag}: {e}",
            err=True,
        )
    except KeyError as e:
        click.echo(
            f"Key error checking {venue_a} vs {venue_b} for {tag}: {e}",
            err=True,
        )
    except ConnectionError as e:
        click.echo(
            f"Connection error checking {venue_a} vs {venue_b} for {tag}: {e}",
            err=True,
        )
    except Exception as e:  # noqa: BLE001
        # We need to catch all exceptions to ensure the scanner keeps running
        click.echo(f"Error checking {venue_a} vs {venue_b} for {tag}: {e}", err=True)


def check_for_arbitrage(
    threshold: float,
    bankroll: float | None = None,
    *,
    once: bool = False,
) -> None:
    """Check for arbitrage opportunities across venues.

    Args:
        threshold: Minimum edge to trigger an alert
        bankroll: Optional bankroll amount for Kelly sizing
        once: Run only once (for testing)

    """
    alert_sink = get_alert_sink()
    threshold_decimal = Decimal(str(threshold))

    # Load registry
    registry = load_registry()
    if not registry:
        click.echo("No events found in registry.", err=True)
        return

    for entry in registry:
        tag = entry.get("tag")
        if not tag:
            continue

        # Get venues for this tag
        venues = venues_for(tag)
        if len(venues) < MIN_VENUES_FOR_ARBITRAGE:
            # Need at least 2 venues for cross-venue arbitrage
            continue

        # Check each pair of venues
        venue_names = list(venues.keys())
        for i in range(len(venue_names)):
            for j in range(i + 1, len(venue_names)):
                venue_a = venue_names[i]
                venue_b = venue_names[j]

                check_venue_pair(
                    venue_a,
                    venue_b,
                    venues[venue_a],
                    venues[venue_b],
                    tag,
                    threshold_decimal,
                    alert_sink,
                    bankroll,
                )

    if once:
        return


@click.command()
@click.option(
    "--threshold",
    type=float,
    default=0.05,
    help="Minimum positive edge before alert (default: 0.05)",
)
@click.option(
    "--interval",
    type=int,
    default=60,
    help="Polling interval in seconds (default: 60)",
)
@click.option(
    "--bankroll",
    type=float,
    help="Optional bankroll amount for Kelly sizing",
)
@click.option(
    "--once",
    is_flag=True,
    hidden=True,
    help="Run once and exit (for testing)",
)
def cli(
    threshold: float,
    interval: int,
    bankroll: float | None = None,
    once: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """Scan for arbitrage opportunities across prediction market venues.

    Continuously monitors venues for profitable edges, sending alerts when opportunities
    are found. Press Ctrl+C to exit.
    """
    click.echo(f"Starting arbscan with threshold={threshold}, interval={interval}s")

    # Initialize database
    init_db()
    click.echo("Database initialized at data/arb.db")

    # Set up signal handler for graceful exit
    def signal_handler(_sig: int, _frame: object) -> None:
        click.echo("\nExiting arbscan...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Run once or enter polling loop
        if once:
            check_for_arbitrage(threshold, bankroll, once=True)
            return

        while True:
            check_for_arbitrage(threshold, bankroll, once=False)
            time.sleep(interval)

    except KeyboardInterrupt:
        click.echo("\nExiting arbscan...", err=True)
        sys.exit(0)
    except ValueError as e:
        click.echo(f"Value error: {e}", err=True)
        sys.exit(1)
    except KeyError as e:
        click.echo(f"Key error: {e}", err=True)
        sys.exit(1)
    except ConnectionError as e:
        click.echo(f"Connection error: {e}", err=True)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        # Need to catch all exceptions to exit gracefully
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
