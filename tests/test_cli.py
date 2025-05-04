"""Tests for the CLI runner."""

from decimal import Decimal
from unittest import mock

import pytest
from click.testing import CliRunner

from src.arbscan.main import check_for_arbitrage, cli, format_alert_message


@pytest.fixture
def mock_registry():
    """Mock registry with test entries."""
    return [
        {
            "tag": "TEST-TAG",
            "description": "Test market",
            "kalshi": "TEST-KALSHI",
            "nadex": "TEST-NADEX",
            "predictit": None,
        },
    ]


@pytest.fixture
def mock_venues():
    """Mock venue mapping for test tag."""
    return {"kalshi": "TEST-KALSHI", "nadex": "TEST-NADEX"}


@pytest.fixture
def mock_market_data_kalshi():
    """Mock Kalshi market data for testing."""
    return {
        "ticker": "TEST-KALSHI",
        "yes_ask": {"price": 45, "size": 100},  # cents (0-100)
        "no_ask": {"price": 55, "size": 100},
    }


@pytest.fixture
def mock_market_data_nadex():
    """Mock Nadex market data for testing."""
    return {
        "instrument_id": "TEST-NADEX",
        "yes_price": 40,  # cents (0-100)
        "no_price": 60,
    }


@pytest.fixture
def mock_yes_no_snapshot():
    """Mock MarketSnapshot for testing."""
    return mock.MagicMock(
        best_yes=mock.MagicMock(price=Decimal("0.45")),
        best_no=mock.MagicMock(price=Decimal("0.55")),
        key=mock.MagicMock(exchange="TestExchange", symbol="TEST-SYM"),
    )


@pytest.fixture
def arbitrage_mocks(  # noqa: PLR0913
    mock_calc_edge,
    mock_to_snapshot,
    mock_fetch_market_data,
    mock_venues_for,
    mock_load_registry,
    mock_get_alert_sink,
    mock_registry,
    mock_venues,
    mock_yes_no_snapshot,
):
    """Group fixtures for arbitrage testing."""
    # Setup common mocks
    mock_load_registry.return_value = mock_registry
    mock_venues_for.return_value = mock_venues
    mock_fetch_market_data.return_value = {}
    mock_to_snapshot.return_value = mock_yes_no_snapshot

    # Return dict for customization in tests
    return {
        "calc_edge": mock_calc_edge,
        "alert_sink": mock_get_alert_sink.return_value,
    }


def test_format_alert_message():
    """Test formatting alert messages."""
    # Without bankroll
    message = format_alert_message(
        "TEST-TAG",
        Decimal("0.07"),
        "Kalshi",
        "Nadex",
        "YES",
        Decimal("0.45"),
        "NO",
        Decimal("0.48"),
        None,
    )
    assert "EDGE 7.000" in message
    assert "TEST-TAG" in message
    assert "YES@Kalshi 0.45" in message
    assert "NO@Nadex 0.48" in message
    assert "Kelly stake" not in message

    # With bankroll
    message = format_alert_message(
        "TEST-TAG",
        Decimal("0.07"),
        "Kalshi",
        "Nadex",
        "YES",
        Decimal("0.45"),
        "NO",
        Decimal("0.48"),
        1000,
    )
    assert "EDGE 7.000" in message
    assert "Kelly stake: $" in message


@mock.patch("src.arbscan.main.save_snapshot")
@mock.patch("src.arbscan.main.save_edge")
@mock.patch("src.arbscan.main.get_alert_sink")
@mock.patch("src.arbscan.main.load_registry")
@mock.patch("src.arbscan.main.venues_for")
@mock.patch("src.arbscan.main.fetch_market_data")
@mock.patch("src.arbscan.main.to_snapshot")
@mock.patch("src.arbscan.main.calc_edge")
def test_check_for_arbitrage_with_edge(  # noqa: PLR0913
    mock_calc_edge,
    mock_to_snapshot,
    mock_fetch_market_data,
    mock_venues_for,
    mock_load_registry,
    mock_get_alert_sink,
    mock_save_edge,
    mock_save_snapshot,
    mock_registry,
    mock_venues,
    mock_yes_no_snapshot,
):
    """Test check_for_arbitrage function when edge exceeds threshold."""
    # Setup mocks
    mock_load_registry.return_value = mock_registry
    mock_venues_for.return_value = mock_venues
    mock_fetch_market_data.return_value = {}
    mock_to_snapshot.return_value = mock_yes_no_snapshot
    mock_calc_edge.return_value = Decimal("0.07")  # Above default threshold
    mock_alert_sink = mock.MagicMock()
    mock_get_alert_sink.return_value = mock_alert_sink

    # Call the function
    check_for_arbitrage(0.05, once=True)

    # Assertions
    assert mock_alert_sink.send.call_count == 1
    assert "EDGE" in mock_alert_sink.send.call_args[0][0]
    # Verify database functions were called
    assert mock_save_snapshot.call_count >= 1
    assert mock_save_edge.call_count >= 1


@mock.patch("src.arbscan.main.save_snapshot")
@mock.patch("src.arbscan.main.save_edge")
@mock.patch("src.arbscan.main.get_alert_sink")
@mock.patch("src.arbscan.main.load_registry")
@mock.patch("src.arbscan.main.venues_for")
@mock.patch("src.arbscan.main.fetch_market_data")
@mock.patch("src.arbscan.main.to_snapshot")
@mock.patch("src.arbscan.main.calc_edge")
def test_check_for_arbitrage_no_edge(  # noqa: PLR0913
    mock_calc_edge,
    mock_to_snapshot,
    mock_fetch_market_data,
    mock_venues_for,
    mock_load_registry,
    mock_get_alert_sink,
    mock_save_edge,
    mock_save_snapshot,
    mock_registry,
    mock_venues,
    mock_yes_no_snapshot,
):
    """Test check_for_arbitrage function when edge is below threshold."""
    # Setup mocks
    mock_load_registry.return_value = mock_registry
    mock_venues_for.return_value = mock_venues
    mock_fetch_market_data.return_value = {}
    mock_to_snapshot.return_value = mock_yes_no_snapshot
    mock_calc_edge.return_value = Decimal("0.03")  # Below default threshold
    mock_alert_sink = mock.MagicMock()
    mock_get_alert_sink.return_value = mock_alert_sink

    # Call the function
    check_for_arbitrage(0.05, once=True)

    # Assertions
    mock_alert_sink.send.assert_not_called()
    # Verify database functions were called
    # (snapshots and edges are stored regardless of threshold)
    assert mock_save_snapshot.call_count >= 1
    assert mock_save_edge.call_count >= 1


def test_cli_once_flag():
    """Test CLI with --once flag runs and exits."""
    runner = CliRunner()

    with mock.patch("src.arbscan.main.check_for_arbitrage") as mock_check:
        result = runner.invoke(cli, ["--threshold", "0.05", "--once"])

        assert result.exit_code == 0
        mock_check.assert_called_once_with(0.05, None, once=True)


@mock.patch("src.arbscan.main.check_for_arbitrage")
@mock.patch("src.arbscan.main.time.sleep")
def test_cli_loop_then_exception(mock_sleep, mock_check):
    """Test CLI loop with exception handling."""
    runner = CliRunner()

    # Make sleep raise exception after first call to simulate error
    mock_sleep.side_effect = [None, Exception("Test error")]

    result = runner.invoke(cli, ["--threshold", "0.06", "--interval", "30"])

    assert result.exit_code == 1
    assert mock_check.call_count >= 1
    mock_check.assert_called_with(0.06, None, once=False)
    mock_sleep.assert_called_with(30)
