"""Trade data validation for detecting data quality issues.

This module validates trade data before processing to catch common
issues like missing prices, duplicates, and gaps.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict


class ValidationWarning:
    """Represents a validation warning."""
    
    def __init__(self, level: str, message: str, lineno: Optional[int] = None):
        self.level = level  # 'error', 'warning', 'info'
        self.message = message
        self.lineno = lineno
    
    def __str__(self):
        prefix = f"Line {self.lineno}: " if self.lineno else ""
        return f"[{self.level.upper()}] {prefix}{self.message}"


def validate_trades(trades: Any, year: Optional[int] = None) -> List[ValidationWarning]:
    """Validate trade data and return list of warnings.
    
    Args:
        trades: Trades object containing all trades
        year: Optional year to filter validation to
    
    Returns:
        List of ValidationWarning objects
    """
    warnings: List[ValidationWarning] = []
    
    # Check for missing values
    warnings.extend(_check_missing_values(trades))
    
    # Check for duplicates
    warnings.extend(_check_duplicates(trades))
    
    # Check for date gaps
    warnings.extend(_check_date_gaps(trades, year))
    
    # Check for potential balance issues
    warnings.extend(_check_balance_issues(trades))
    
    return warnings


def _check_missing_values(trades: Any) -> List[ValidationWarning]:
    """Check for trades with missing critical values."""
    warnings = []
    
    for trade in trades.trades:
        # Check for missing prices on buy side
        if trade.buy_coin and trade.buy_coin not in ['SEK', 'EUR', 'USD']:
            if trade.buy_amount and not trade.buy_value:
                warnings.append(ValidationWarning(
                    'warning',
                    f"Missing buy value for {trade.buy_amount} {trade.buy_coin} on {trade.date.strftime('%Y-%m-%d')}",
                    trade.lineno
                ))
        
        # Check for missing prices on sell side
        if trade.sell_coin and trade.sell_coin not in ['SEK', 'EUR', 'USD']:
            if trade.sell_amount and not trade.sell_value:
                warnings.append(ValidationWarning(
                    'warning',
                    f"Missing sell value for {trade.sell_amount} {trade.sell_coin} on {trade.date.strftime('%Y-%m-%d')}",
                    trade.lineno
                ))
    
    return warnings


def _check_duplicates(trades: Any) -> List[ValidationWarning]:
    """Check for potential duplicate trades."""
    warnings = []
    
    # Group by (date, type, buy_coin, buy_amount, sell_coin, sell_amount)
    seen: Dict[Tuple, List[int]] = defaultdict(list)
    
    for trade in trades.trades:
        key = (
            trade.date.strftime('%Y-%m-%d %H:%M'),
            trade.type,
            trade.buy_coin,
            round(trade.buy_amount or 0, 8),
            trade.sell_coin,
            round(trade.sell_amount or 0, 8),
        )
        seen[key].append(trade.lineno)
    
    for key, linenos in seen.items():
        if len(linenos) > 1:
            warnings.append(ValidationWarning(
                'warning',
                f"Possible duplicate: {len(linenos)} identical trades on lines {linenos}",
                linenos[0]
            ))
    
    return warnings


def _check_date_gaps(trades: Any, year: Optional[int] = None) -> List[ValidationWarning]:
    """Check for large gaps in trading activity."""
    warnings = []
    
    dates = sorted([trade.date for trade in trades.trades])
    
    if not dates:
        return warnings
    
    # Filter to year if specified
    if year:
        dates = [d for d in dates if d.year == year]
    
    if len(dates) < 2:
        return warnings
    
    # Check for gaps > 90 days (might indicate missing data)
    for i in range(1, len(dates)):
        gap = (dates[i] - dates[i-1]).days
        if gap > 90:
            warnings.append(ValidationWarning(
                'info',
                f"Large gap in activity: {gap} days between {dates[i-1].strftime('%Y-%m-%d')} and {dates[i].strftime('%Y-%m-%d')}",
                None
            ))
    
    return warnings


def _check_balance_issues(trades: Any, sek_threshold: float = 2500.0) -> List[ValidationWarning]:
    """Check for trades that might cause negative balances.
    
    Uses monetary value (SEK) to determine significance of overdrafts.
    Only reports errors for overdrafts exceeding sek_threshold.
    
    Args:
        trades: Trades object containing all trades
        sek_threshold: Minimum SEK value to report as error (default: 2500)
    """
    warnings = []
    
    # Track running balances, prices, and first negative per coin
    balances: Dict[str, float] = defaultdict(float)
    prices: Dict[str, float] = {}  # Last known price per unit in SEK
    first_negative: Dict[str, Tuple[int, float, float]] = {}  # coin -> (lineno, balance, price)
    
    # Sort by date, with secondary sort to prioritize deposits/buys over withdrawals/sells
    # This handles same-timestamp trades correctly
    def sort_key(trade):
        # Lower number = processed first
        type_order = {
            'Deposit': 0,
            'Mining': 0,
            'Staking': 0,
            'Interest Income': 0,
            'Reward / Bonus': 0,
            'Income': 0,
            'Income (non taxable)': 0,
            'Airdrop': 0,
            'Gift/Tip': 0,
            'Trade': 1,  # Trades can be either buy or sell
            'Spend': 2,
            'Withdrawal': 2,
        }
        return (trade.date, type_order.get(trade.type, 1))
    
    sorted_trades = sorted(trades.trades, key=sort_key)
    
    for trade in sorted_trades:
        # Track buy prices
        if trade.buy_coin and trade.buy_coin not in ['SEK', 'EUR', 'USD']:
            balances[trade.buy_coin] += trade.buy_amount or 0
            if trade.buy_amount and trade.buy_value:
                prices[trade.buy_coin] = trade.buy_value / trade.buy_amount
        
        # Track sell prices and check for negative
        if trade.sell_coin and trade.sell_coin not in ['SEK', 'EUR', 'USD']:
            if trade.sell_amount and trade.sell_value:
                prices[trade.sell_coin] = trade.sell_value / trade.sell_amount
            
            balances[trade.sell_coin] -= trade.sell_amount or 0
            
            # Track first time coin goes significantly negative
            if balances[trade.sell_coin] < -1e-8:
                if trade.sell_coin not in first_negative:
                    price = prices.get(trade.sell_coin, 0)
                    first_negative[trade.sell_coin] = (trade.lineno, balances[trade.sell_coin], price)
    
    # Create warnings based on SEK value
    for coin, (lineno, balance, price) in first_negative.items():
        sek_value = abs(balance * price) if price else 0
        
        if sek_value >= sek_threshold:
            # Significant overdraft - this needs attention
            warnings.append(ValidationWarning(
                'error',
                f"Negative balance: {coin} at {balance:.6f} units (~{sek_value:,.0f} SEK)",
                lineno
            ))
        elif sek_value >= 100:
            # Minor but noticeable
            warnings.append(ValidationWarning(
                'warning',
                f"Minor overdraft: {coin} at {balance:.6f} units (~{sek_value:,.0f} SEK)",
                lineno
            ))
        # Ignore very small overdrafts (< 100 SEK)
    
    return warnings


def print_validation_report(warnings: List[ValidationWarning]) -> None:
    """Print a formatted validation report."""
    if not warnings:
        print("✓ No validation issues found")
        return
    
    errors = [w for w in warnings if w.level == 'error']
    warns = [w for w in warnings if w.level == 'warning']
    infos = [w for w in warnings if w.level == 'info']
    
    print(f"\nValidation Report: {len(errors)} errors, {len(warns)} warnings, {len(infos)} info")
    print("=" * 60)
    
    for w in errors:
        print(f"  ❌ {w}")
    for w in warns:
        print(f"  ⚠️  {w}")
    for w in infos:
        print(f"  ℹ️  {w}")
    
    print()
