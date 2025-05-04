"""Tests for Nadex data client."""

from datetime import datetime
from unittest import mock

import pytest
import requests
import responses

from arbscan.nadex_client import NadexClient, NadexContract

# Constants for testing
MOCK_INSTRUMENT_ID = "SPX-40000-31DEC23"
RETRY_STATUS_CODES = [429, 503]  # Test both retry status codes
# Number of valid contracts in mock CSV
# (including the row with invalid float)
EXPECTED_VALID_CONTRACTS = 4
EXPECTED_REQUESTS = 2  # Number of expected requests in retry tests
MOCK_YES_PRICE = 25
MOCK_NO_PRICE = 75
MOCK_STRIKE_VALUE = 40000.0


@pytest.fixture
def nadex_client():
    """Fixture to create an instance of NadexClient."""
    return NadexClient()


@pytest.fixture
def mock_csv_content():
    """Fixture to provide sample CSV content for testing."""
    return (
        "instrument_id,underlying,strike,expiry,other_field\n"
        f"{MOCK_INSTRUMENT_ID},SPX,40000,2023-12-31T23:59:59Z,extra\n"
        "BTC-70K-31MAY24,BTC,70000,2024-05-31T23:59:59Z,extra\n"
        "DEMS-PRES-2024,,0,2024-11-05T23:59:59Z,extra\n"
        "INVALID-ROW,BTC,not_a_number,2024-01-01T00:00:00Z,extra\n"
        "INVALID-DATE,SPX,50000,not_a_date,extra\n"
    )


@pytest.fixture
def mock_contract_data():
    """Fixture to provide sample contract data for testing."""
    return {
        "instrument_id": MOCK_INSTRUMENT_ID,
        "underlying": "SPX",
        "strike": 40000,
        "yes_price": 25,
        "no_price": 75,
        "yes_volume": 500,
        "no_volume": 750,
        "timestamp": "2023-12-15T12:34:56Z",
    }


def test_init():
    """Test initialization of NadexClient."""
    client = NadexClient()
    assert isinstance(client, NadexClient)
    assert client.session is not None


@responses.activate
def test_list_contracts(nadex_client, mock_csv_content):
    """Test listing contracts from CSV endpoint."""
    # Set up mock response
    responses.add(
        responses.GET,
        NadexClient.CONTRACTS_CSV_URL,
        body=mock_csv_content,
        status=200,
        content_type="text/csv",
    )

    # Call method
    contracts = nadex_client.list_contracts()

    # Verify results
    assert len(contracts) == EXPECTED_VALID_CONTRACTS
    assert isinstance(contracts[0], NadexContract)

    # Check first contract details
    assert contracts[0].instrument_id == MOCK_INSTRUMENT_ID
    assert contracts[0].underlying == "SPX"
    assert contracts[0].strike == MOCK_STRIKE_VALUE
    assert contracts[0].expiry == datetime.fromisoformat("2023-12-31T23:59:59Z")

    # Check contract with no strike
    assert contracts[2].instrument_id == "DEMS-PRES-2024"
    assert contracts[2].strike == 0.0  # Converted to float

    # Check contract with invalid strike (now None instead of throwing an error)
    assert contracts[3].instrument_id == "INVALID-ROW"
    assert contracts[3].strike is None


@responses.activate
def test_get_contract(nadex_client, mock_contract_data):
    """Test getting contract data from JSON endpoint."""
    # Set up mock response
    responses.add(
        responses.GET,
        f"{NadexClient.CONTRACT_DETAIL_URL}/{MOCK_INSTRUMENT_ID}",
        json=mock_contract_data,
        status=200,
    )

    # Call method
    contract_data = nadex_client.get_contract(MOCK_INSTRUMENT_ID)

    # Verify results
    assert contract_data == mock_contract_data
    assert contract_data["instrument_id"] == MOCK_INSTRUMENT_ID
    assert contract_data["yes_price"] == MOCK_YES_PRICE
    assert contract_data["no_price"] == MOCK_NO_PRICE


@pytest.mark.parametrize("status_code", RETRY_STATUS_CODES)
@responses.activate
def test_retry_list_contracts(nadex_client, mock_csv_content, status_code):
    """Test retry logic for list_contracts on rate limiting or service unavailable."""
    # Set up first response with error
    responses.add(
        responses.GET,
        NadexClient.CONTRACTS_CSV_URL,
        status=status_code,
    )

    # Set up second response (after retry)
    responses.add(
        responses.GET,
        NadexClient.CONTRACTS_CSV_URL,
        body=mock_csv_content,
        status=200,
        content_type="text/csv",
    )

    # Mock the sleep function to avoid waiting in tests
    with mock.patch("time.sleep") as mock_sleep:
        contracts = nadex_client.list_contracts()

        # Verify sleep was called with correct duration
        mock_sleep.assert_called_once_with(NadexClient.RETRY_DELAY)

        # Verify we got the expected results after retry
        assert len(contracts) == EXPECTED_VALID_CONTRACTS
        assert contracts[0].instrument_id == MOCK_INSTRUMENT_ID

        # Verify there were two requests
        assert len(responses.calls) == EXPECTED_REQUESTS


@pytest.mark.parametrize("status_code", RETRY_STATUS_CODES)
@responses.activate
def test_retry_get_contract(nadex_client, mock_contract_data, status_code):
    """Test retry logic for get_contract on rate limiting or service unavailable."""
    url = f"{NadexClient.CONTRACT_DETAIL_URL}/{MOCK_INSTRUMENT_ID}"

    # Set up first response with error
    responses.add(
        responses.GET,
        url,
        status=status_code,
    )

    # Set up second response (after retry)
    responses.add(
        responses.GET,
        url,
        json=mock_contract_data,
        status=200,
    )

    # Mock the sleep function to avoid waiting in tests
    with mock.patch("time.sleep") as mock_sleep:
        contract_data = nadex_client.get_contract(MOCK_INSTRUMENT_ID)

        # Verify sleep was called with correct duration
        mock_sleep.assert_called_once_with(NadexClient.RETRY_DELAY)

        # Verify we got the expected results after retry
        assert contract_data == mock_contract_data

        # Verify there were two requests
        assert len(responses.calls) == EXPECTED_REQUESTS


@responses.activate
def test_non_retryable_error(nadex_client):
    """Test that non-retryable errors are raised properly."""
    # Set up response with non-retryable error
    responses.add(
        responses.GET,
        NadexClient.CONTRACTS_CSV_URL,
        status=404,  # Not Found is not in retry codes
    )

    # Expect the error to be propagated
    with pytest.raises(requests.exceptions.HTTPError):
        nadex_client.list_contracts()
