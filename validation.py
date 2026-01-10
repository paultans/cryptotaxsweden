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


def _check_balance_issues(trades: Any) -> List[ValidationWarning]:
    """Check for trades that might cause negative balances."""
    warnings = []
    
    # Track running balances
    balances: Dict[str, float] = defaultdict(float)
    
    sorted_trades = sorted(trades.trades, key=lambda t: t.date)
    
    for trade in sorted_trades:
        # Add buys
        if trade.buy_coin and trade.buy_coin not in ['SEK', 'EUR', 'USD']:
            balances[trade.buy_coin] += trade.buy_amount or 0
        
        # Subtract sells
        if trade.sell_coin and trade.sell_coin not in ['SEK', 'EUR', 'USD']:
            balances[trade.sell_coin] -= trade.sell_amount or 0
            
            # Check for negative balance
            if balances[trade.sell_coin] < -0.0001:
                warnings.append(ValidationWarning(
                    'error',
                    f"Negative balance: {trade.sell_coin} goes to {balances[trade.sell_coin]:.6f} after selling {trade.sell_amount}",
                    trade.lineno
                ))
    
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
