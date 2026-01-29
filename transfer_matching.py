"""Withdrawal/Deposit matching for detecting missing trades.

This module analyzes withdrawal and deposit transactions to identify
unmatched transfers that might indicate missing trades.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


class UnmatchedTransfer:
    """Represents an unmatched withdrawal or deposit."""
    
    def __init__(self, transfer_type: str, coin: str, amount: float, 
                 date: datetime, lineno: int):
        self.transfer_type = transfer_type  # 'withdrawal' or 'deposit'
        self.coin = coin
        self.amount = amount
        self.date = date
        self.lineno = lineno
    
    def __str__(self):
        return (f"[{self.transfer_type.upper()}] Line {self.lineno}: "
                f"{self.amount} {self.coin} on {self.date.strftime('%Y-%m-%d')}")


def find_unmatched_transfers(
    trades: Any,
    time_window_days: int = 7,
    amount_tolerance: float = 0.001
) -> Tuple[List[UnmatchedTransfer], Dict[str, Any]]:
    """Find withdrawals and deposits that don't have matching counterparts.
    
    When crypto is transferred between exchanges/wallets, there should be
    a withdrawal from one and a deposit to another within a reasonable
    time window.
    
    Args:
        trades: Trades object containing all trades
        time_window_days: Maximum days between matching withdrawal/deposit
        amount_tolerance: Tolerance for amount matching (proportion)
    
    Returns:
        Tuple of (unmatched_transfers, statistics)
    """
    # Collect withdrawals and deposits
    withdrawals: Dict[str, List[Dict]] = defaultdict(list)
    deposits: Dict[str, List[Dict]] = defaultdict(list)
    
    for trade in trades.trades:
        if trade.type == 'Withdrawal':
            if trade.sell_coin:
                withdrawals[trade.sell_coin].append({
                    'amount': trade.sell_amount or 0,
                    'date': trade.date,
                    'lineno': trade.lineno,
                    'matched': False,
                })
        elif trade.type == 'Deposit':
            if trade.buy_coin:
                deposits[trade.buy_coin].append({
                    'amount': trade.buy_amount or 0,
                    'date': trade.date,
                    'lineno': trade.lineno,
                    'matched': False,
                })
    
    # Try to match withdrawals to deposits
    matched_count = 0
    time_window = timedelta(days=time_window_days)
    
    all_coins = set(withdrawals.keys()) | set(deposits.keys())
    
    for coin in all_coins:
        coin_withdrawals = withdrawals.get(coin, [])
        coin_deposits = deposits.get(coin, [])
        
        for w in coin_withdrawals:
            if w['matched']:
                continue
            
            for d in coin_deposits:
                if d['matched']:
                    continue
                
                # Check time window
                time_diff = abs((d['date'] - w['date']).total_seconds())
                if time_diff > time_window.total_seconds():
                    continue
                
                # Check amount (within tolerance)
                amount_diff = abs(d['amount'] - w['amount'])
                if w['amount'] > 0:
                    if amount_diff / w['amount'] <= amount_tolerance:
                        w['matched'] = True
                        d['matched'] = True
                        matched_count += 1
                        break
    
    # Collect unmatched transfers
    unmatched: List[UnmatchedTransfer] = []
    
    for coin, items in withdrawals.items():
        for item in items:
            if not item['matched']:
                unmatched.append(UnmatchedTransfer(
                    'withdrawal', coin, item['amount'], item['date'], item['lineno']
                ))
    
    for coin, items in deposits.items():
        for item in items:
            if not item['matched']:
                unmatched.append(UnmatchedTransfer(
                    'deposit', coin, item['amount'], item['date'], item['lineno']
                ))
    
    # Sort by date
    unmatched.sort(key=lambda x: x.date)
    
    # Statistics
    total_withdrawals = sum(len(w) for w in withdrawals.values())
    total_deposits = sum(len(d) for d in deposits.values())
    
    stats = {
        'total_withdrawals': total_withdrawals,
        'total_deposits': total_deposits,
        'matched_pairs': matched_count,
        'unmatched_withdrawals': sum(1 for u in unmatched if u.transfer_type == 'withdrawal'),
        'unmatched_deposits': sum(1 for u in unmatched if u.transfer_type == 'deposit'),
    }
    
    return unmatched, stats


def print_transfer_report(unmatched: List[UnmatchedTransfer], stats: Dict[str, Any]) -> None:
    """Print a formatted transfer matching report."""
    print("\nTransfer Matching Report")
    print("=" * 60)
    print(f"  Total withdrawals: {stats['total_withdrawals']}")
    print(f"  Total deposits: {stats['total_deposits']}")
    print(f"  Matched pairs: {stats['matched_pairs']}")
    print(f"  Unmatched withdrawals: {stats['unmatched_withdrawals']}")
    print(f"  Unmatched deposits: {stats['unmatched_deposits']}")
    
    if unmatched:
        print("\nUnmatched Transfers (may indicate missing trades):")
        print("-" * 60)
        
        # Group by coin
        by_coin: Dict[str, List[UnmatchedTransfer]] = defaultdict(list)
        for u in unmatched:
            by_coin[u.coin].append(u)
        
        for coin in sorted(by_coin.keys()):
            print(f"\n  {coin}:")
            for u in by_coin[coin]:
                icon = "↑" if u.transfer_type == 'withdrawal' else "↓"
                print(f"    {icon} {u.date.strftime('%Y-%m-%d')}: {u.amount:.6f} (line {u.lineno})")
    else:
        print("\n✓ All transfers matched!")
    
    print()
