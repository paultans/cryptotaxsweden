"""USD/SEK exchange rate updater using Riksbanken API.

This module fetches historical USD/SEK exchange rates from the Swedish
central bank (Riksbanken) and updates the rates CSV file.
"""

import csv
import json
import os
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


RIKSBANK_API_URL = "https://api.riksbank.se/swea/v1/Observations/SEKUSDPMI/{start}/{end}"
RATES_FILE = "data/rates/usdsek.csv"


def fetch_rates_from_riksbank(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Fetch USD/SEK rates from Riksbanken API using curl.
    
    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
    
    Returns:
        List of {date, value} dictionaries.
    """
    url = RIKSBANK_API_URL.format(start=start_date, end=end_date)
    
    # Use curl since Python's urllib may have SSL issues on older versions
    result = subprocess.run(
        ["curl", "-s", url],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if result.returncode != 0:
        raise Exception(f"Failed to fetch rates: {result.stderr}")
    
    data = json.loads(result.stdout)
    return data


def get_latest_date_in_file(filepath: str = RATES_FILE) -> Optional[datetime]:
    """Get the most recent date in the rates CSV file."""
    if not os.path.exists(filepath):
        return None
    
    latest_date = None
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            if row:
                try:
                    # Format: "Jan 09, 2026"
                    date = datetime.strptime(row[0], '%b %d, %Y')
                    if latest_date is None or date > latest_date:
                        latest_date = date
                except ValueError:
                    continue
    
    return latest_date


def update_rates(days_back: int = 30) -> int:
    """Update the rates file with latest data from Riksbanken.
    
    Args:
        days_back: How many days back to fetch (for overlap/gap filling).
    
    Returns:
        Number of new rates added.
    """
    # Determine date range
    latest_date = get_latest_date_in_file()
    
    if latest_date:
        start_date = (latest_date - timedelta(days=days_back)).strftime('%Y-%m-%d')
    else:
        start_date = "2010-01-01"
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"Fetching rates from {start_date} to {end_date}...")
    
    # Fetch new data
    new_data = fetch_rates_from_riksbank(start_date, end_date)
    print(f"Retrieved {len(new_data)} records from Riksbanken")
    
    # Convert to CSV format
    new_rows = []
    for entry in new_data:
        date_obj = datetime.strptime(entry['date'], '%Y-%m-%d')
        formatted_date = date_obj.strftime('%b %d, %Y')
        rate = entry['value']
        new_rows.append([
            formatted_date,
            f"{rate:.4f}",
            f"{rate:.4f}",
            f"{rate:.4f}",
            f"{rate:.4f}",
            "0.00%"
        ])
    
    # Read existing data
    existing_rows = []
    header = ["Date", "Price", "Open", "High", "Low", "Change %"]
    
    if os.path.exists(RATES_FILE):
        with open(RATES_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                if row:
                    existing_rows.append(row)
    
    # Merge: new data takes precedence
    new_dates = {row[0] for row in new_rows}
    filtered_existing = [row for row in existing_rows if row[0] not in new_dates]
    
    all_rows = new_rows + filtered_existing
    
    # Sort by date descending (newest first)
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, '%b %d, %Y')
        except:
            return datetime.min
    
    all_rows.sort(key=lambda x: parse_date(x[0]), reverse=True)
    
    # Write updated file
    with open(RATES_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(all_rows)
    
    new_count = len(new_rows)
    print(f"Updated {RATES_FILE} with {new_count} new/updated rates")
    print(f"Total rates: {len(all_rows)}")
    print(f"Date range: {all_rows[-1][0]} to {all_rows[0][0]}")
    
    return new_count


if __name__ == "__main__":
    update_rates()
