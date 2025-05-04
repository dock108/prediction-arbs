"""Tests for event registry matcher utility."""

from unittest import mock

import pytest

from src.arbscan.matcher import tag_from, venues_for

# Test constants based on registry entries
TEST_TAG = "BTC-31MAY70K"
KALSHI_SYMBOL = "BTC-70K-31MAY25"
NADEX_SYMBOL = "BTC-70000-31MAY25"
UNKNOWN_SYMBOL = "UNKNOWN-SYMBOL"
PREDICTIT_ID = 8973  # FOMC-JUN25BP market ID
PREDICTIT_TAG = "FOMC-JUN25BP"
EXPECTED_VENUE_COUNT = 2  # Expected number of venues in test mappings


# Mock registry entries for testing
MOCK_REGISTRY = [
    {
        "tag": "BTC-31MAY70K",
        "description": "Will Bitcoin close ≥ $70,000 on 31 May 2025?",
        "kalshi": "BTC-70K-31MAY25",
        "nadex": "BTC-70000-31MAY25",
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


@pytest.fixture(autouse=True)
def mock_registry():
    """Fixture to mock the registry for deterministic testing."""
    with mock.patch("src.arbscan.matcher._REGISTRY", MOCK_REGISTRY):
        # Rebuild the venue maps with our mock data
        venue_maps = {
            venue: {
                entry[venue]: entry["tag"]
                for entry in MOCK_REGISTRY
                if entry.get(venue) is not None
            }
            for venue in ["kalshi", "nadex", "predictit"]
        }
        with mock.patch("src.arbscan.matcher._VENUE_TO_TAG_MAPS", venue_maps):
            yield


def test_tag_from_kalshi():
    """Test getting a tag from a Kalshi symbol."""
    assert tag_from("kalshi", KALSHI_SYMBOL) == TEST_TAG


def test_tag_from_nadex():
    """Test getting a tag from a Nadex symbol."""
    assert tag_from("nadex", NADEX_SYMBOL) == TEST_TAG


def test_tag_from_predictit():
    """Test getting a tag from a PredictIt ID."""
    # Test with both string and integer ID
    assert tag_from("predictit", str(PREDICTIT_ID)) == PREDICTIT_TAG
    assert tag_from("predictit", PREDICTIT_ID) == PREDICTIT_TAG


def test_tag_from_unknown_symbol():
    """Test that unknown symbols return None."""
    assert tag_from("kalshi", UNKNOWN_SYMBOL) is None


def test_tag_from_unknown_exchange():
    """Test that unknown exchange returns None."""
    assert tag_from("unknown_exchange", KALSHI_SYMBOL) is None


def test_venues_for_valid_tag():
    """Test getting venue symbols for a valid tag."""
    venues = venues_for(TEST_TAG)
    assert len(venues) == EXPECTED_VENUE_COUNT
    assert venues["kalshi"] == KALSHI_SYMBOL
    assert venues["nadex"] == NADEX_SYMBOL
    assert "predictit" not in venues


def test_venues_for_predictit_tag():
    """Test getting venue symbols for a tag with PredictIt mapping."""
    venues = venues_for(PREDICTIT_TAG)
    assert len(venues) == EXPECTED_VENUE_COUNT
    assert venues["kalshi"] == "FED-25BP-JUN25"
    assert venues["predictit"] == "8973"
    assert "nadex" not in venues


def test_venues_for_unknown_tag():
    """Test that unknown tag returns empty dict."""
    assert venues_for("UNKNOWN-TAG") == {}
