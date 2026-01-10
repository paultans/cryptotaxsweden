Exchange rates from:
- 2020-01-02 to present: https://api.riksbank.se/swea/v1/Observations/SEKUSDPMI
- Before 2020: https://www.investing.com/currencies/usd-sek-historical-data

To update rates, run:
  curl -s "https://api.riksbank.se/swea/v1/Observations/SEKUSDPMI/YYYY-MM-DD/YYYY-MM-DD" > /tmp/new_rates.json
  # Then process and merge with existing CSV
