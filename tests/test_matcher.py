"""Tests for the matcher."""

from unittest import mock

import pytest

from arbscan.matcher import tag_from, venues_for

# Constants for test data
KALSHI_TAG = "BTC-31MAY70K"
KALSHI_ID = "BTC-70K-31MAY25"

NADEX_TAG = "SPX-31MAY5500"
NADEX_ID = "SPX-5500-31MAY25"

PREDICTIT_TAG = "FOMC-JUN25BP"
PREDICTIT_ID = "8973"  # String ID to match what we get from venues_for

EXPECTED_VENUE_COUNT = 2  # Number of venues per event

# Mock registry for testing
MOCK_REGISTRY = [
    {
        "tag": "BTC-31MAY70K",
        "description": "Will Bitcoin close ≥ $70,000 on 31 May 2025?",
        "kalshi": "BTC-70K-31MAY25",
        "nadex": "BTC-70000-31MAY25",
        "predictit": None,
    },
    {
        "tag": "SPX-31MAY5500",
        "description": "Will S&P 500 close above 5,500 on 31 May 2025?",
        "kalshi": "SPX-5500-31MAY25",
        "nadex": "SPX-5500-31MAY25",
        "predictit": None,
    },
    {
        "tag": "FOMC-JUN25BP",
        "description": "Will the FOMC cut rates by 25 basis points in June 2025?",
        "kalshi": "FED-25BP-JUN25",
        "nadex": None,
        "predictit": "8973",
    },
]

# Build venue maps from mock registry
MOCK_VENUE_MAPS = {
    venue: {
        entry[venue]: entry["tag"]
        for entry in MOCK_REGISTRY
        if entry.get(venue) is not None
    }
    for venue in ["kalshi", "nadex", "predictit"]
}


@pytest.fixture(autouse=True)
def mock_registry():
    """Mock the registry and venue maps for testing."""
    with (
        mock.patch("arbscan.matcher._REGISTRY", MOCK_REGISTRY),
        mock.patch(
            "arbscan.matcher._VENUE_TO_TAG_MAPS",
            MOCK_VENUE_MAPS,
        ),
    ):
        yield


def test_tag_from_kalshi():
    """Test getting a tag from a Kalshi ID."""
    assert tag_from("kalshi", KALSHI_ID) == KALSHI_TAG
    assert tag_from("KALSHI", KALSHI_ID) is None  # Case sensitive


def test_tag_from_nadex():
    """Test getting a tag from a Nadex ID."""
    assert tag_from("nadex", NADEX_ID) == NADEX_TAG
    assert tag_from("NADEX", NADEX_ID) is None  # Case sensitive


def test_tag_from_predictit():
    """Test getting a tag from a PredictIt ID."""
    # Test with both string and integer ID
    assert tag_from("predictit", PREDICTIT_ID) == PREDICTIT_TAG
    assert tag_from("predictit", int(PREDICTIT_ID)) == PREDICTIT_TAG
    assert tag_from("PREDICTIT", PREDICTIT_ID) is None  # Case sensitive


def test_tag_from_unknown_venue():
    """Test getting a tag from an unknown venue."""
    assert tag_from("unknown", "123") is None


def test_tag_from_unknown_symbol():
    """Test getting a tag for an unknown symbol."""
    assert tag_from("kalshi", "UNKNOWN-SYMBOL") is None
    assert tag_from("nadex", "UNKNOWN-SYMBOL") is None
    assert tag_from("predictit", "99999") is None


def test_venues_for_kalshi_tag():
    """Test getting venue symbols for a tag with Kalshi mapping."""
    venues = venues_for(KALSHI_TAG)
    assert len(venues) == EXPECTED_VENUE_COUNT  # Kalshi and Nadex
    assert venues["kalshi"] == KALSHI_ID
    assert "nadex" in venues


def test_venues_for_nadex_tag():
    """Test getting venue symbols for a tag with Nadex mapping."""
    venues = venues_for(NADEX_TAG)
    assert len(venues) == EXPECTED_VENUE_COUNT
    assert venues["nadex"] == NADEX_ID
    assert "kalshi" in venues


def test_venues_for_predictit_tag():
    """Test getting venue symbols for a tag with PredictIt mapping."""
    venues = venues_for(PREDICTIT_TAG)
    assert len(venues) == EXPECTED_VENUE_COUNT
    assert venues["kalshi"] == "FED-25BP-JUN25"
    assert venues["predictit"] == PREDICTIT_ID
