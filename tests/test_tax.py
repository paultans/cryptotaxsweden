"""Unit tests for tax.py module."""

import pytest
from datetime import datetime

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tax import Coin, is_fiat, aggregate_per_coin, convert_to_integer_amounts
from taxdata import TaxEvent


class TestIsFiat:
    """Tests for is_fiat function."""

    def test_sek_is_fiat(self):
        assert is_fiat("SEK") is True

    def test_eur_is_fiat(self):
        assert is_fiat("EUR") is True

    def test_usd_is_fiat(self):
        assert is_fiat("USD") is True

    def test_btc_is_not_fiat(self):
        assert is_fiat("BTC") is False

    def test_eth_is_not_fiat(self):
        assert is_fiat("ETH") is False


class TestCoin:
    """Tests for Coin class buy/sell mechanics."""

    def test_initial_state(self):
        """New coin should have zero amount and cost basis."""
        coin = Coin("BTC", max_overdraft=0)
        assert coin.symbol == "BTC"
        assert coin.amount == 0.0
        assert coin.cost_basis == 0.0

    def test_buy_increases_amount(self):
        """Buying should increase the coin amount."""
        coin = Coin("BTC", max_overdraft=0)
        coin.buy(amount=1.0, price=10000.0)
        assert coin.amount == 1.0

    def test_buy_sets_cost_basis(self):
        """First buy should set cost basis to price/amount."""
        coin = Coin("BTC", max_overdraft=0)
        coin.buy(amount=1.0, price=10000.0)
        assert coin.cost_basis == 10000.0

    def test_multiple_buys_average_cost_basis(self):
        """Multiple buys should calculate weighted average cost basis."""
        coin = Coin("BTC", max_overdraft=0)
        coin.buy(amount=1.0, price=10000.0)  # 1 BTC @ 10000 SEK/BTC
        coin.buy(amount=1.0, price=20000.0)  # 1 BTC @ 20000 SEK/BTC
        # Total: 2 BTC, average cost = (10000 + 20000) / 2 = 15000
        assert coin.amount == 2.0
        assert coin.cost_basis == 15000.0

    def test_sell_decreases_amount(self):
        """Selling should decrease the coin amount."""
        coin = Coin("BTC", max_overdraft=0)
        coin.buy(amount=2.0, price=20000.0)
        coin.sell(amount=1.0, price=15000.0)
        assert coin.amount == 1.0

    def test_sell_returns_tax_event(self):
        """Selling should return a TaxEvent with correct values."""
        coin = Coin("BTC", max_overdraft=0)
        coin.buy(amount=1.0, price=10000.0)  # Buy 1 BTC for 10000 SEK
        tax_event = coin.sell(amount=1.0, price=15000.0)  # Sell 1 BTC for 15000 SEK
        
        assert tax_event.amount == 1.0
        assert tax_event.name == "BTC"
        assert tax_event.income == 15000.0
        assert tax_event.cost == 10000.0
        assert tax_event.profit() == 5000.0

    def test_sell_more_than_owned_raises_exception(self):
        """Selling more than owned should raise exception."""
        coin = Coin("BTC", max_overdraft=0)
        coin.buy(amount=1.0, price=10000.0)
        with pytest.raises(Exception) as exc_info:
            coin.sell(amount=2.0, price=20000.0)
        assert "Not enough coins" in str(exc_info.value)

    def test_sell_with_overdraft_allowed(self):
        """Selling with overdraft allowed should not raise exception."""
        coin = Coin("BTC", max_overdraft=1.0)
        coin.buy(amount=1.0, price=10000.0)
        # Should not raise - overdraft of 0.5 is within max_overdraft of 1.0
        tax_event = coin.sell(amount=1.5, price=15000.0)
        assert tax_event.amount == 1.5
        assert coin.amount == 0.0  # Amount is set to 0 when going negative


class TestTaxEvent:
    """Tests for TaxEvent class."""

    def test_profit_calculation_positive(self):
        """Profit should be income minus cost."""
        event = TaxEvent(amount=1.0, name="BTC", income=15000.0, cost=10000.0)
        assert event.profit() == 5000.0

    def test_profit_calculation_negative(self):
        """Loss should be negative profit."""
        event = TaxEvent(amount=1.0, name="BTC", income=8000.0, cost=10000.0)
        assert event.profit() == -2000.0

    def test_fields(self):
        """fields() should return list of values."""
        event = TaxEvent(amount=1.0, name="BTC", income=15000.0, cost=10000.0)
        assert event.fields() == [1.0, "BTC", 15000.0, 10000.0]

    def test_k4_fields_with_profit(self):
        """k4_fields() should include profit in 5th position when positive."""
        event = TaxEvent(amount=1.0, name="BTC", income=15000.0, cost=10000.0)
        fields = event.k4_fields()
        assert fields[4] == 5000.0  # Profit
        assert fields[5] is None  # No loss

    def test_k4_fields_with_loss(self):
        """k4_fields() should include loss in 6th position when negative."""
        event = TaxEvent(amount=1.0, name="BTC", income=8000.0, cost=10000.0)
        fields = event.k4_fields()
        assert fields[4] is None  # No profit
        assert fields[5] == 2000.0  # Loss (absolute value)


class TestAggregatePerCoin:
    """Tests for aggregate_per_coin function."""

    def test_empty_list(self):
        """Empty list should return empty list."""
        result = aggregate_per_coin([])
        assert result == []

    def test_single_profit_event(self):
        """Single profit event should be aggregated."""
        events = [TaxEvent(amount=1.0, name="BTC", income=15000.0, cost=10000.0)]
        result = aggregate_per_coin(events)
        assert len(result) == 1
        assert result[0].name == "BTC"
        assert result[0].profit() == 5000.0

    def test_aggregate_multiple_profits(self):
        """Multiple profit events should be summed."""
        events = [
            TaxEvent(amount=1.0, name="BTC", income=15000.0, cost=10000.0),  # +5000
            TaxEvent(amount=2.0, name="BTC", income=30000.0, cost=20000.0),  # +10000
        ]
        result = aggregate_per_coin(events)
        assert len(result) == 1
        assert result[0].amount == 3.0
        assert result[0].income == 45000.0
        assert result[0].cost == 30000.0
        assert result[0].profit() == 15000.0

    def test_separate_profits_and_losses(self):
        """Profits and losses should be reported separately."""
        events = [
            TaxEvent(amount=1.0, name="BTC", income=15000.0, cost=10000.0),  # +5000
            TaxEvent(amount=1.0, name="BTC", income=8000.0, cost=10000.0),   # -2000
        ]
        result = aggregate_per_coin(events)
        assert len(result) == 2
        # First should be profit
        profit_event = [e for e in result if e.profit() > 0][0]
        loss_event = [e for e in result if e.profit() < 0][0]
        assert profit_event.profit() == 5000.0
        assert loss_event.profit() == -2000.0


class TestConvertToIntegerAmounts:
    """Tests for convert_to_integer_amounts function."""

    def test_rounds_amounts(self):
        """Amounts should be rounded to integers."""
        events = [
            TaxEvent(amount=1.5, name="BTC", income=15000.0, cost=10000.0),
            TaxEvent(amount=2.4, name="ETH", income=8000.0, cost=5000.0),
        ]
        result = convert_to_integer_amounts(events)
        assert result[0].amount == 2
        assert result[1].amount == 2

    def test_does_not_modify_income_cost(self):
        """Income and cost should not be rounded."""
        events = [
            TaxEvent(amount=1.5, name="BTC", income=15000.5, cost=10000.3),
        ]
        result = convert_to_integer_amounts(events)
        assert result[0].income == 15000.5
        assert result[0].cost == 10000.3
