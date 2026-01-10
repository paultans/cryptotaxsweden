"""Coin state persistence for multi-year cost basis tracking.

This module allows saving and loading coin state (amounts and cost basis)
between tax years, so you don't need to reprocess the entire trade history.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional


class CoinState:
    """Represents the state of all coins at a point in time."""
    
    def __init__(self):
        self.coins: Dict[str, Dict[str, float]] = {}
        self.as_of_date: Optional[str] = None
        self.year: Optional[int] = None
    
    def add_coin(self, symbol: str, amount: float, cost_basis: float) -> None:
        """Add or update a coin's state."""
        self.coins[symbol] = {
            'amount': amount,
            'cost_basis': cost_basis,
        }
    
    def get_coin(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get a coin's state."""
        return self.coins.get(symbol)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'version': 1,
            'as_of_date': self.as_of_date,
            'year': self.year,
            'generated_at': datetime.now().isoformat(),
            'coins': self.coins,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CoinState':
        """Create from dictionary."""
        state = cls()
        state.as_of_date = data.get('as_of_date')
        state.year = data.get('year')
        state.coins = data.get('coins', {})
        return state
    
    def save(self, filepath: str) -> None:
        """Save state to JSON file."""
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Saved coin state to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'CoinState':
        """Load state from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Loaded coin state from {filepath}")
        return cls.from_dict(data)
    
    def summary(self) -> str:
        """Get a summary of the coin state."""
        lines = []
        lines.append(f"Coin State (as of {self.as_of_date or 'unknown'}, year {self.year or 'unknown'}):")
        lines.append("-" * 60)
        
        total_value = 0.0
        for symbol, data in sorted(self.coins.items()):
            amount = data['amount']
            cost_basis = data['cost_basis']
            if amount > 1e-9:
                total_cost = amount * cost_basis
                total_value += total_cost
                lines.append(f"  {symbol:8} {amount:>14.6f} units @ {cost_basis:>12.2f} SEK = {total_cost:>12.0f} SEK")
        
        lines.append("-" * 60)
        lines.append(f"  Total cost basis: {total_value:,.0f} SEK")
        
        return "\n".join(lines)


def create_state_from_coins(coins_dict: Dict[str, Any], year: int) -> CoinState:
    """Create a CoinState from the coins dictionary returned by compute_tax.
    
    Args:
        coins_dict: Dictionary of coin symbol -> Coin object
        year: The tax year this state is for
    
    Returns:
        CoinState object with the current state of all coins
    """
    state = CoinState()
    state.year = year
    state.as_of_date = f"{year}-12-31"
    
    for symbol, coin in coins_dict.items():
        if coin.amount > 1e-9:  # Only save non-zero balances
            state.add_coin(symbol, coin.amount, coin.cost_basis)
    
    return state


def apply_state_to_coins(state: CoinState, coins_dict: Dict[str, Any], coin_class: Any, max_overdraft: float) -> None:
    """Apply a saved state to the coins dictionary.
    
    Args:
        state: CoinState to apply
        coins_dict: Dictionary to populate with coins
        coin_class: The Coin class to use for creating new coins
        max_overdraft: Max overdraft value for coins
    """
    for symbol, data in state.coins.items():
        coin = coin_class(symbol, max_overdraft)
        coin.amount = data['amount']
        coin.cost_basis = data['cost_basis']
        coins_dict[symbol] = coin
    
    print(f"Applied state from {state.as_of_date}: {len(state.coins)} coins loaded")
