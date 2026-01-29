"""Data structures and I/O functions for tax data processing.

This module provides classes for handling personal details, trades,
and tax events, as well as functions for reading exchange rates.
"""

from datetime import datetime
from typing import List, Optional, Any
import dateutil.parser
import csv
import json


class PersonalDetails:
    """Personal information required for tax forms."""
    
    def __init__(self, namn: str, personnummer: str, postnummer: str, postort: str) -> None:
        self.namn = namn
        self.personnummer = personnummer
        self.postnummer = postnummer
        self.postort = postort

    @staticmethod
    def read_from(filename: str) -> 'PersonalDetails':
        """Read personal details from a JSON file."""
        with open(filename, encoding="utf-8-sig") as f:
            d = json.load(f)
            return PersonalDetails(d["namn"], d["personnummer"], d["postnummer"], d["postort"])


class Fees:
    """Fee configuration for tax calculations."""
    
    def __init__(self, fees: dict) -> None:
        self.fees = fees

    @staticmethod
    def read_from(filename: str) -> 'Fees':
        """Read fee configuration from a JSON file."""
        with open(filename, encoding="utf-8-sig") as f:
            d = json.load(f)
            return Fees(d["fees"])


class Trade:
    """Represents a single cryptocurrency trade."""
    
    def __init__(
        self, 
        lineno: int, 
        date: datetime, 
        type: str, 
        group: Optional[str],
        buy_coin: Optional[str], 
        buy_amount: Optional[float], 
        buy_value: Optional[float],
        sell_coin: Optional[str], 
        sell_amount: Optional[float], 
        sell_value: Optional[float]
    ) -> None:
        self.lineno = lineno
        self.date = date
        self.type = type
        self.group = group
        self.buy_coin = buy_coin
        self.buy_amount = buy_amount
        self.buy_value = buy_value
        self.sell_coin = sell_coin
        self.sell_amount = sell_amount
        self.sell_value = sell_value


def read_usdsek_rates() -> List[List[Any]]:
    """Read USD/SEK exchange rates from CSV file.
    
    Returns:
        List of [datetime, float] pairs sorted by date.
    """
    rates: List[List[Any]] = []
    with open('data/rates/usdsek.csv', encoding='utf-8-sig') as f:
        is_first = True
        for row in csv.reader(f, delimiter=',', quotechar='"'):
            if is_first:
                is_first = False
                continue
            date = dateutil.parser.parse(row[0])
            close = float(row[1])
            rates.append([date, close])
    rates.sort(key=lambda rate: rate[0])
    return rates


def usd_to_sek(rates: List[List[Any]], wanted_date: datetime) -> float:
    """Convert USD to SEK using historical exchange rates.
    
    Args:
        rates: List of [datetime, rate] pairs, sorted by date.
        wanted_date: The date to look up the rate for.
    
    Returns:
        The exchange rate (SEK per USD) for the given date.
    
    Raises:
        Exception: If no rate is found for the given date.
    """
    prev_date: Optional[datetime] = None
    prev_price: Optional[float] = None
    for rate in rates:
        date = rate[0]
        price = rate[1]
        if prev_date and prev_date <= wanted_date and wanted_date < date:
            return prev_price  # type: ignore
        prev_date = date
        prev_price = price
    raise Exception("Didn't find a USDSEK conversion rate for date %s" % wanted_date)


class Trades:
    """Collection of trades read from a CSV file."""
    
    def __init__(self, trades: List[Trade]) -> None:
        self.trades = trades

    @staticmethod
    def read_from(filename: str, value_in_usd: bool) -> 'Trades':
        """Read trades from a CoinTracking CSV export.
        
        Args:
            filename: Path to the CSV file.
            value_in_usd: If True, convert USD values to SEK.
        """
        with open(filename, encoding='utf-8-sig') as f:
            lines = [line for line in csv.reader(f, delimiter=',', quotechar='"')]

        # Normalize headers: replace non-breaking spaces with regular spaces
        lines[0] = [col.replace('\xa0', ' ') for col in lines[0]]

        if value_in_usd:
            usdsek = read_usdsek_rates()

        def indices(col_name: str) -> List[int]:
            return [index for index, col in enumerate(lines[0]) if col == col_name]

        price_field_name = 'Value in USD' if value_in_usd else 'Value in SEK'

        date_index = indices('Date')[0]
        type_index = indices('Type')[0]
        group_index = indices('Group')[0]
        buy_coin_index = indices('Cur.')[0]
        buy_amount_index = indices('Buy')[0]
        buy_value_index = indices(price_field_name)[0]
        sell_coin_index = indices('Cur.')[1]
        sell_amount_index = indices('Sell')[0]
        sell_value_index = indices(price_field_name)[1]

        trades: List[Trade] = []
        lineno = 2
        for line in lines[1:]:
            trade = Trade(
                lineno,
                datetime.strptime(line[date_index], "%d.%m.%Y %H:%M"),
                line[type_index],
                None if line[group_index] == '-' else line[group_index],
                None if line[buy_coin_index] == '-' else line[buy_coin_index],
                None if line[buy_amount_index] == '-' else float(line[buy_amount_index]),
                None if line[buy_value_index] == '-' else float(line[buy_value_index]),
                None if line[sell_coin_index] == '-' else line[sell_coin_index],
                None if line[sell_amount_index] == '-' else float(line[sell_amount_index]),
                None if line[sell_value_index] == '-' else float(line[sell_value_index])
            )
            if value_in_usd:
                usdsek_rate = usd_to_sek(usdsek, trade.date)
                if trade.buy_value:
                    trade.buy_value *= usdsek_rate
                if trade.sell_value:
                    trade.sell_value *= usdsek_rate
            trades.append(trade)
            lineno += 1

        trades.reverse()
        trades.sort(key=lambda x: x.date)

        return Trades(trades)


class TaxEvent:
    """Represents a taxable event (sale of assets)."""
    
    def __init__(self, amount: float, name: str, income: float, cost: float) -> None:
        self.amount = amount
        self.name = name
        self.income = income
        self.cost = cost

    @staticmethod
    def headers() -> List[str]:
        """Return column headers for CSV output."""
        return ['Amount', 'Name', 'Income', 'Cost']

    def fields(self) -> List[Any]:
        """Return field values for CSV output."""
        return [self.amount, self.name, self.income, self.cost]

    def k4_fields(self) -> List[Any]:
        """Return field values for K4 form output."""
        return [self.amount, self.name, self.income, self.cost,
                self.profit() if self.profit() > 0 else None,
                -self.profit() if self.profit() < 0 else None]

    def profit(self) -> float:
        """Calculate profit (income minus cost)."""
        return self.income - self.cost

    @staticmethod
    def read_stock_tax_events_from(filename: str) -> List['TaxEvent']:
        """Read stock tax events from a JSON file."""
        with open(filename, encoding="utf-8-sig") as f:
            d = json.load(f)
            events: List[TaxEvent] = []
            for event in d["trades"]:
                events.append(TaxEvent(event["amount"], event["name"], event["income"], event["costbase"]))
            return events


class TradeEvent:
    """Records a single trade with cost basis changes for calculation report.

    This class tracks how each trade affects the cost basis, enabling
    detailed calculation reports that show the tax calculation logic.
    """

    def __init__(
        self,
        date: datetime,
        name: str,
        amount: float,
        price: float,
        total_amount_before: float,
        total_amount_after: float,
        cost_basis_before: float,
        cost_basis_after: float,
        tax_event: Optional[TaxEvent],
        trade_type: str
    ) -> None:
        self.date = date
        self.name = name
        self.amount = amount  # Positive for buy, negative for sell
        self.price = price
        self.total_amount_before = total_amount_before
        self.total_amount_after = total_amount_after
        self.cost_basis_before = cost_basis_before
        self.cost_basis_after = cost_basis_after
        self.tax_event = tax_event  # Only set for sell events
        self.trade_type = trade_type
