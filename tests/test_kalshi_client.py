"""Tests for the Kalshi REST client."""

import os
from unittest import mock

import pytest
import responses

from src.arbscan.kalshi_client import KalshiClient

# Constants for testing
EXPECTED_MARKETS_COUNT = 2
MOCK_TICKER_1 = "BTC-31MAY70K"
MOCK_TICKER_2 = "DEMS-2024-PRES"


@pytest.fixture
def mock_env_api_key():
    """Fixture to mock environment variable with API key."""
    with mock.patch.dict(os.environ, {"KALSHI_API_KEY": "test_api_key_from_env"}):
        yield


@pytest.fixture
def kalshi_client():
    """Fixture to create an instance of KalshiClient."""
    return KalshiClient()


@pytest.fixture
def kalshi_client_with_key():
    """Fixture to create an instance of KalshiClient with explicit API key."""
    return KalshiClient(api_key="test_api_key")


def test_init_without_key():
    """Test initialization without API key."""
    client = KalshiClient()
    assert client.api_key is None


def test_init_with_key():
    """Test initialization with explicit API key."""
    client = KalshiClient(api_key="test_api_key")
    assert client.api_key == "test_api_key"


def test_init_with_env_key(mock_env_api_key: None):
    """Test initialization using API key from environment variable."""
    # The fixture sets the environment variable, we don't need to use it directly
    # but we need to include it as a parameter to activate it
    _ = mock_env_api_key  # Acknowledge the fixture to satisfy linter
    client = KalshiClient()
    assert client.api_key == "test_api_key_from_env"


# We want to test private methods directly in these tests
# ruff: noqa: SLF001
def test_get_headers_no_auth():
    """Test header generation without API key."""
    client = KalshiClient()
    headers = client._get_headers()
    assert "Authorization" not in headers
    assert headers["Accept"] == "application/json"


# ruff: noqa: SLF001
def test_get_headers_with_auth():
    """Test header generation with API key."""
    client = KalshiClient(api_key="test_api_key")
    headers = client._get_headers()
    assert headers["Authorization"] == "Bearer test_api_key"
    assert headers["Accept"] == "application/json"


@responses.activate
def test_list_markets(kalshi_client: KalshiClient):
    """Test listing markets."""
    # Mock response data
    mock_markets = {
        "markets": [
            {"ticker": MOCK_TICKER_1, "name": "Bitcoin above $70K on May 31"},
            {
                "ticker": MOCK_TICKER_2,
                "name": "Democrats win 2024 presidential election",
            },
        ],
    }

    # Set up mock response
    responses.add(
        responses.GET,
        f"{KalshiClient.BASE_URL}/markets",
        json=mock_markets,
        status=200,
    )

    # Call method
    result = kalshi_client.list_markets()

    # Verify results
    assert len(result) == EXPECTED_MARKETS_COUNT
    assert MOCK_TICKER_1 in result
    assert MOCK_TICKER_2 in result


@responses.activate
def test_get_market(kalshi_client: KalshiClient):
    """Test getting specific market data."""
    ticker = MOCK_TICKER_1

    # Mock response data
    mock_market_data = {
        "market": {
            "ticker": ticker,
            "name": "Bitcoin above $70K on May 31",
            "yes_bids": [{"price": 65, "size": 100}],
            "no_bids": [{"price": 35, "size": 50}],
        },
        "event": {"close_time": "2024-05-31T23:59:59Z"},
    }

    # Set up mock response
    responses.add(
        responses.GET,
        f"{KalshiClient.BASE_URL}/markets/{ticker}",
        json=mock_market_data,
        status=200,
    )

    # Call method
    result = kalshi_client.get_market(ticker)

    # Verify result is returned directly
    assert result == mock_market_data


@responses.activate
def test_auth_header_sent(kalshi_client_with_key: KalshiClient):
    """Test that auth header is sent when API key is provided."""
    # Set up mock response
    responses.add(
        responses.GET,
        f"{KalshiClient.BASE_URL}/markets",
        json={"markets": []},
        status=200,
    )

    # Call method
    kalshi_client_with_key.list_markets()

    # Get the last request and verify headers
    request = responses.calls[0].request
    assert "Authorization" in request.headers
    assert request.headers["Authorization"] == "Bearer test_api_key"


@responses.activate
def test_rate_limit_retry():
    """Test rate limit retry logic."""
    client = KalshiClient()
    ticker = MOCK_TICKER_1

    # Mock response data
    mock_market_data = {
        "market": {"ticker": ticker},
        "event": {"close_time": "2024-05-31T23:59:59Z"},
    }

    # Set up first response with rate limit
    responses.add(
        responses.GET,
        f"{KalshiClient.BASE_URL}/markets/{ticker}",
        status=KalshiClient.RATE_LIMIT_STATUS,
        headers={"Retry-After": "1"},
    )

    # Set up second response (after retry)
    responses.add(
        responses.GET,
        f"{KalshiClient.BASE_URL}/markets/{ticker}",
        json=mock_market_data,
        status=200,
    )

    # Mock the sleep function to avoid waiting in tests
    with mock.patch("time.sleep") as mock_sleep:
        result = client.get_market(ticker)

        # Verify sleep was called with correct duration
        mock_sleep.assert_called_once_with(1)

        # Verify we got the expected result after retry
        assert result == mock_market_data

        # Verify there were two requests
        assert len(responses.calls) == EXPECTED_MARKETS_COUNT


@responses.activate
def test_rate_limit_retry_max_delay():
    """Test rate limit retry with delay capped at maximum."""
    client = KalshiClient()

    # Set up first response with excessive rate limit
    responses.add(
        responses.GET,
        f"{KalshiClient.BASE_URL}/markets",
        status=KalshiClient.RATE_LIMIT_STATUS,
        headers={"Retry-After": "10"},  # More than MAX_RETRY_DELAY
    )

    # Set up second response (after retry)
    responses.add(
        responses.GET,
        f"{KalshiClient.BASE_URL}/markets",
        json={"markets": []},
        status=200,
    )

    # Mock the sleep function to avoid waiting in tests
    with mock.patch("time.sleep") as mock_sleep:
        client.list_markets()

        # Verify sleep was called with MAX_RETRY_DELAY (not the full 10s)
        mock_sleep.assert_called_once_with(KalshiClient.MAX_RETRY_DELAY)

        # Verify there were two requests
        assert len(responses.calls) == EXPECTED_MARKETS_COUNT
