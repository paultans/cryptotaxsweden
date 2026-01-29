"""Unit tests for taxdata.py module."""

import pytest
from datetime import datetime
import os

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from taxdata import read_usdsek_rates, usd_to_sek


class TestReadUsdSekRates:
    """Tests for read_usdsek_rates function."""

    @pytest.fixture
    def change_to_repo_root(self):
        """Change to repo root for file access."""
        original_cwd = os.getcwd()
        os.chdir(Path(__file__).parent.parent)
        yield
        os.chdir(original_cwd)

    def test_loads_rates_successfully(self, change_to_repo_root):
        """Should load rates from CSV file without error."""
        rates = read_usdsek_rates()
        assert len(rates) > 0

    def test_rates_are_sorted_by_date(self, change_to_repo_root):
        """Rates should be sorted chronologically (oldest first)."""
        rates = read_usdsek_rates()
        dates = [rate[0] for rate in rates]
        assert dates == sorted(dates)

    def test_rate_format_is_date_and_float(self, change_to_repo_root):
        """Each rate should be [datetime, float]."""
        rates = read_usdsek_rates()
        first_rate = rates[0]
        
        assert isinstance(first_rate[0], datetime)
        assert isinstance(first_rate[1], float)

    def test_rates_are_reasonable_values(self, change_to_repo_root):
        """Exchange rates should be in reasonable range (5-15 SEK per USD)."""
        rates = read_usdsek_rates()
        for rate in rates:
            assert 5.0 < rate[1] < 15.0, f"Rate {rate[1]} on {rate[0]} seems unreasonable"

    def test_contains_recent_data(self, change_to_repo_root):
        """Should contain data up to at least 2025."""
        rates = read_usdsek_rates()
        latest_date = rates[-1][0]
        assert latest_date.year >= 2025


class TestUsdToSek:
    """Tests for usd_to_sek function."""

    @pytest.fixture
    def sample_rates(self):
        """Create sample rates for testing."""
        return [
            [datetime(2024, 1, 1), 10.0],
            [datetime(2024, 1, 2), 10.5],
            [datetime(2024, 1, 3), 10.2],
            [datetime(2024, 1, 5), 10.8],  # Gap - no Jan 4
        ]

    def test_finds_rate_for_date_between_entries(self, sample_rates):
        """Should return previous rate when date falls between two entries."""
        # usd_to_sek returns prev_price when prev_date <= wanted_date < date
        # Query for Jan 1 at noon falls between Jan 1 and Jan 2
        rate = usd_to_sek(sample_rates, datetime(2024, 1, 1, 12, 0))
        assert rate == 10.0  # Returns Jan 1's rate

    def test_finds_rate_for_date_in_gap(self, sample_rates):
        """Should return previous available rate for dates in gaps."""
        # Jan 4 doesn't exist, should return Jan 3's rate
        rate = usd_to_sek(sample_rates, datetime(2024, 1, 4))
        assert rate == 10.2

    def test_raises_for_date_before_data(self, sample_rates):
        """Should raise exception for dates before available data."""
        with pytest.raises(Exception) as exc_info:
            usd_to_sek(sample_rates, datetime(2023, 12, 31))
        assert "Didn't find a USDSEK conversion rate" in str(exc_info.value)

    def test_raises_for_date_after_data(self, sample_rates):
        """Should raise exception for dates after available data."""
        with pytest.raises(Exception) as exc_info:
            usd_to_sek(sample_rates, datetime(2024, 1, 10))
        assert "Didn't find a USDSEK conversion rate" in str(exc_info.value)

    def test_with_real_data(self):
        """Integration test with real rate data."""
        # Change to repo root
        original_cwd = os.getcwd()
        os.chdir(Path(__file__).parent.parent)
        try:
            rates = read_usdsek_rates()
            
            # Test a known date - should return a reasonable rate
            rate = usd_to_sek(rates, datetime(2024, 6, 15))
            assert 9.0 < rate < 12.0, f"Rate {rate} seems unreasonable for 2024"
        finally:
            os.chdir(original_cwd)
