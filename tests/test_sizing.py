"""Tests for the Kelly sizing module."""

import sys
from decimal import Decimal
from pathlib import Path

# Add the src directory to the path before importing arbscan
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from arbscan.sizing import kelly


class TestKellySizing:
    """Tests for the Kelly criterion sizing function."""

    def test_zero_edge_returns_zero(self):
        """When edge is 0, Kelly fraction should be 0."""
        edge = Decimal("0")
        odds = Decimal("1.5")
        result = kelly(edge, odds)
        assert result == Decimal("0")

    def test_positive_edge_small_odds(self):
        """With positive edge and small odds, fraction should be less than 1."""
        edge = Decimal("0.05")  # 5% edge
        odds = Decimal("1.95")  # typical betting odds
        result = kelly(edge, odds)
        assert result > Decimal("0")
        assert result < Decimal("1")
        # Using simplified Kelly: f = (edge * odds) / (odds - 1)
        # f = (0.05 * 1.95) / (1.95 - 1) = 0.0975 / 0.95 ≈ 0.1026
        expected = Decimal("0.1026")
        assert abs(result - expected) < Decimal("0.01")

    def test_large_edge_capped_at_one(self):
        """With large edge, fraction should be capped at 1."""
        edge = Decimal("0.6")  # 60% edge (unrealistically high)
        odds = Decimal("2.0")
        # Formula: (0.6 * 2.0) / (2.0 - 1) = 1.2, which should be capped at 1
        result = kelly(edge, odds)
        assert result == Decimal("1")

    def test_negative_edge_returns_zero(self):
        """When edge is negative, Kelly fraction should be 0."""
        edge = Decimal("-0.05")  # negative 5% edge
        odds = Decimal("1.95")
        result = kelly(edge, odds)
        assert result == Decimal("0")

    def test_precise_calculation(self):
        """Test with known values for precise calculation check."""
        # Using simplified Kelly: f = (edge * odds) / (odds - 1)
        # f = (0.03 * 1.9) / (1.9 - 1) = 0.057 / 0.9 = 0.063333
        edge = Decimal("0.03")
        odds = Decimal("1.9")
        result = kelly(edge, odds)
        expected = Decimal("0.063333")
        assert abs(result - expected) < Decimal("0.001")

    def test_extreme_odds(self):
        """Test with extreme odds values."""
        # Very high odds
        edge = Decimal("0.01")
        odds = Decimal("100.0")
        result = kelly(edge, odds)
        assert result > Decimal("0")
        assert result < Decimal("1")

        # Odds close to 1.0, which can cause division by near-zero
        edge = Decimal("0.01")
        odds = Decimal("1.01")
        # This should give a very high fraction that gets capped at 1
        result = kelly(edge, odds)
        assert result == Decimal("1")
