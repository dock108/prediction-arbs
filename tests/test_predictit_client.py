"""Tests for PredictIt data client."""

from unittest import mock

import pytest
import requests
import responses

from arbscan.predictit_client import PredictItClient

# Test constants
MOCK_MARKET_ID = 12345
MOCK_MARKET_NAME = "Which party will win the 2024 US election?"
MOCK_RETRY_AFTER = 2  # Seconds
RETRY_STATUS_CODE = 429  # Too Many Requests
EXPECTED_CONTRACTS = 2  # Number of contracts in a binary market
EXPECTED_REQUESTS = 2  # Number of expected requests in retry tests


@pytest.fixture
def predictit_client():
    """Fixture to create an instance of PredictItClient."""
    return PredictItClient()


@pytest.fixture
def mock_api_response():
    """Fixture to provide sample API response for testing."""
    return {
        "markets": [
            {
                "id": MOCK_MARKET_ID,
                "name": MOCK_MARKET_NAME,
                "contracts": [
                    {
                        "id": 1234,
                        "name": "Yes",
                        "bestBuyYesCost": 0.45,
                        "bestSellYesCost": 0.44,
                        "bestBuyNoCost": 0.56,
                        "bestSellNoCost": 0.55,
                    },
                    {
                        "id": 1235,
                        "name": "No",
                        "bestBuyYesCost": 0.55,
                        "bestSellYesCost": 0.54,
                        "bestBuyNoCost": 0.46,
                        "bestSellNoCost": 0.45,
                    },
                ],
            },
            {
                "id": 67890,
                "name": "Multi-choice market",
                "contracts": [
                    {"id": 6789, "name": "Option A", "bestBuyYesCost": 0.25},
                    {"id": 6790, "name": "Option B", "bestBuyYesCost": 0.35},
                    {"id": 6791, "name": "Option C", "bestBuyYesCost": 0.40},
                ],
            },
            {
                "id": 98765,
                "name": "Empty market",
                "contracts": [],
            },
        ],
    }


def test_init():
    """Test initialization of PredictItClient."""
    client = PredictItClient()
    assert isinstance(client, PredictItClient)
    assert client.session is not None


@responses.activate
def test_list_markets(predictit_client, mock_api_response):
    """Test listing markets with binary contracts."""
    # Set up mock response
    responses.add(
        responses.GET,
        PredictItClient.BASE_URL,
        json=mock_api_response,
        status=200,
    )

    # Call method
    markets = predictit_client.list_markets()

    # Verify results - should only include the binary market
    assert len(markets) == 1
    assert markets[0][0] == MOCK_MARKET_ID
    assert markets[0][1] == MOCK_MARKET_NAME


@responses.activate
def test_get_market_success(predictit_client, mock_api_response):
    """Test getting market data for a binary market."""
    # Set up mock response
    responses.add(
        responses.GET,
        PredictItClient.BASE_URL,
        json=mock_api_response,
        status=200,
    )

    # Call method
    market = predictit_client.get_market(MOCK_MARKET_ID)

    # Verify results
    assert market["id"] == MOCK_MARKET_ID
    assert market["name"] == MOCK_MARKET_NAME
    assert len(market["contracts"]) == EXPECTED_CONTRACTS
    assert market["contracts"][0]["name"] == "Yes"
    assert market["contracts"][1]["name"] == "No"


@responses.activate
def test_get_market_not_found(predictit_client, mock_api_response):
    """Test getting market data for non-existent market ID."""
    # Set up mock response
    responses.add(
        responses.GET,
        PredictItClient.BASE_URL,
        json=mock_api_response,
        status=200,
    )

    # Call method with invalid ID
    with pytest.raises(ValueError, match="not found") as excinfo:
        predictit_client.get_market(99999)

    # Verify error message
    assert "not found" in str(excinfo.value)


@responses.activate
def test_get_non_binary_market(predictit_client, mock_api_response):
    """Test getting market data for a non-binary market."""
    # Set up mock response
    responses.add(
        responses.GET,
        PredictItClient.BASE_URL,
        json=mock_api_response,
        status=200,
    )

    # Call method with non-binary market ID
    with pytest.raises(
        ValueError,
        match="does not contain binary contracts",
    ) as excinfo:
        predictit_client.get_market(67890)

    # Verify error message
    assert "does not contain binary contracts" in str(excinfo.value)


@responses.activate
def test_retry_on_rate_limit(predictit_client, mock_api_response):
    """Test retry logic for rate limiting."""
    # Set up first response with rate limit error
    responses.add(
        responses.GET,
        PredictItClient.BASE_URL,
        status=RETRY_STATUS_CODE,
        headers={"Retry-After": str(MOCK_RETRY_AFTER)},
    )

    # Set up second response (after retry)
    responses.add(
        responses.GET,
        PredictItClient.BASE_URL,
        json=mock_api_response,
        status=200,
    )

    # Mock the sleep function to avoid waiting in tests
    with mock.patch("time.sleep") as mock_sleep:
        # Call method
        markets = predictit_client.list_markets()

        # Verify sleep was called with correct duration
        mock_sleep.assert_called_once_with(MOCK_RETRY_AFTER)

        # Verify we got the expected results after retry
        assert len(markets) == 1
        assert markets[0][0] == MOCK_MARKET_ID
        assert markets[0][1] == MOCK_MARKET_NAME

        # Verify there were two requests
        assert len(responses.calls) == EXPECTED_REQUESTS


@responses.activate
def test_retry_with_max_delay_cap(predictit_client, mock_api_response):
    """Test retry logic with delay capped to maximum value."""
    large_retry = 10  # Larger than MAX_RETRY_DELAY

    # Set up first response with rate limit error and large retry value
    responses.add(
        responses.GET,
        PredictItClient.BASE_URL,
        status=RETRY_STATUS_CODE,
        headers={"Retry-After": str(large_retry)},
    )

    # Set up second response (after retry)
    responses.add(
        responses.GET,
        PredictItClient.BASE_URL,
        json=mock_api_response,
        status=200,
    )

    # Mock the sleep function to avoid waiting in tests
    with mock.patch("time.sleep") as mock_sleep:
        # Call method
        markets = predictit_client.list_markets()

        # Verify sleep was called with capped duration
        mock_sleep.assert_called_once_with(PredictItClient.MAX_RETRY_DELAY)

        # Verify we got the expected results after retry
        assert len(markets) == 1
        assert markets[0][0] == MOCK_MARKET_ID

        # Verify there were two requests
        assert len(responses.calls) == EXPECTED_REQUESTS


@responses.activate
def test_non_retryable_error(predictit_client):
    """Test that non-retryable errors are raised properly."""
    # Set up response with non-retryable error
    responses.add(
        responses.GET,
        PredictItClient.BASE_URL,
        status=404,  # Not Found is not in retry codes
    )

    # Expect the error to be propagated
    with pytest.raises(requests.exceptions.HTTPError):
        predictit_client.list_markets()
