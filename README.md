# Swedish cryptocurrency tax reporting script

## About

This is a tool to convert your cryptocurrency trade history to the K4 documents needed
for tax reporting to Skatteverket.

Using [cointracking.info](https://cointracking.info?ref=D611015) is currently the
only supported way to import trades. This site does not yet support doing tax
reports using average cost basis which is what is required in Sweden but
it is still very useful for the actual trade data import.

Besides adding support for average cost basis this script can also generate files
which are compatible with Skatteverket. There is either PDF output for printing and
sending by mail or SRU-output which can be imported on skatteverket.se.

## Supporting the development

Please consider supporting the development of this tool by either using
the referral link to [cointracking.info](https://cointracking.info?ref=D611015)
or by donating to one of the adresses below. Using the referral link
will give you a 10% discount if you decide to buy a Pro or Unlimited account.

* BTC: `3KTLVpWjRGuJNBmjsKo4HGDG1G5SCesej3`
* ETH: `0x05125B8E6598AbDDe21c7D01008a10F6107Ce004`

## How coins should be entered on [cointracking.info](https://cointracking.info?ref=D611015)

### Supported Trade Types

| Type | Description | Cost Basis |
|------|-------------|------------|
| **Trade** | Trades fiat↔crypto, crypto↔crypto | Market value at trade time |
| **Mining** | Mining income | Market value when received (declare as hobby income on T2) |
| **Gift/Tip** | Hard forks, gifts received | Zero (0 SEK) |
| **Airdrop** | Free tokens received | Zero (0 SEK) |
| **Spend** | Paying with crypto | Triggers capital gains tax |
| **Staking** | Staking rewards | Market value when received (taxable income) |
| **Interest Income** | Interest from lending crypto | Market value when received (taxable income) |
| **Reward / Bonus** | Platform rewards, referral bonuses | Market value when received (taxable income) |
| **Income** | Crypto received as payment (salary, freelance) | Market value when received (taxable income) |
| **Income (non taxable)** | Non-taxable income (e.g., Celsius loans) | Market value when received |

**Note:** For Mining, Staking, and Interest Income, the actual income should also be declared 
on a [T2 form "Inkomst av tjänst för inkomstgivande hobby"](https://www.skatteverket.se/privat/sjalvservice/blanketterbroschyrer/blanketter/info/2051.4.39f16f103821c58f680006232.html) 
if it exceeds hobby income thresholds.

A common mistake is to forget to report the conversion to/from Euro which
the bank does when transfering to an exchange such as Kraken/Bitstamp. There
should be a trade between SEK and EUR on cointracking to make sure that there
are EUR available when later exchanging it to crypto.

Withdrawals/Deposits are ignored for the tax report as these are assumed to be
transfers of funds between wallets owned by you.

Adding new rules for handling more situations shouldn't be that hard as long as
it is easy to define the cost basis for an income and what the price should be
when selling crypto. You can add feature requests and if it isn't too complicated
I'll try to add it to the script, or you can submit a pull request.

## Limitations

The sru format is currently limited in that it doesn't allow
decimals, this is a limitation with skatteverket.se. The
recommendation from Skatteverket is to round to whole numbers
even if that results in 0 BTC or similar being reported and then
report what roundings have been done under Övriga Upplysningar.

The script can now generate a rounding report which can be
pasted in Övriga Upplysningar. Skatteverket limits the size of
this field to 999 characters so it is best to combine this with
doing a simplified K4 report to reduce the number of lines which
has to be reported in the K4.

## Liability

I'm not taking any responsibility for that this tool will generate a
correct tax report. I am using the tool for my own tax reporting though
so making it correct is a priority to me. You will however have to
take responsibility yourself for the tax report you send to
Skatteverket, this means you should perform a sanity check of some sort
on the generated K4 documents to make sure it looks reasonable.

## Setup

### Windows

There is a packaged version for Windows under releases which can be used.
Change the example command lines below from `python report.py` to
`report.exe` instead if using it.

### macOS

There is a packaged version for macOS under releases which can be used.
Change the example command lines below from `python report.py` to
`./report` instead if using it.

### Streamlit Web UI (New!)

A web-based user interface is now available for easier usage:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web UI
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

**Features:**
- Upload trades directly from browser
- Data validation with helpful warnings
- Withdrawal/deposit matching
- Download SRU files and rounding report
- Holdings summary view
- Profit/Loss breakdown by coin
- T2 hobby income report (staking, mining, etc.)
- Calculation report showing cost basis changes per trade

### Other (or if you prefer setting up python yourself)

Python 3.10 or higher is required.

The following python packages are needed for pdf generation.

* pdfrw
* reportlab

Python virtual environment can be set up using:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Input data

### data/personal_details.json

This file should have the following format. Make sure to save the file in UTF-8 format. On Windows you can install Notepad++ to make this easier.

```
{
	"namn": "Full name",
	"personnummer": "YYYYMMDD-NNNN",
	"postnummer": "NNNNN",
	"postort": "City"
}
```

### data/trades.csv

To get the data for this file you first need to have your complete trade history
on [cointracking.info](https://cointracking.info?ref=D611015). Then go to the
Trade Prices-page and download a CSV report (comma separated version) from that
page and store it at`data/trades.csv`.

### data/stocks.json (optional)

If you have any stock trades which need to be reported in section A on the K4 then you can
enter them in `data/stocks.json`. See `data/stocks_template.json` for the format.

## Running

### Options

```
usage: report.py [-h] [--trades TRADES] [--out OUT] [--format {pdf,sru}]
                 [--decimal-sru]
                 [--exclude-groups [EXCLUDE_GROUPS [EXCLUDE_GROUPS ...]]]
                 [--coin-report] [--simplified-k4] [--rounding-report]
                 [--rounding-report-threshold ROUNDING_REPORT_THRESHOLD]
                 [--cointracking-usd] [--max-overdraft MAX_OVERDRAFT]
                 [--income-report] [--t2-sru] [--calculation-report]
                 [--validate] [--check-transfers] [--holdings]
                 year

Swedish cryptocurrency tax reporting script

positional arguments:
  year                  Tax year to create report for

optional arguments:
  -h, --help            show this help message and exit
  --trades TRADES       Read trades from csv file
  --out OUT             Output folder
  --format {pdf,sru}    The file format of the generated report
  --decimal-sru         Report decimal amounts in sru mode (not supported by
                        Skatteverket yet)
  --exclude-groups [EXCLUDE_GROUPS [EXCLUDE_GROUPS ...]]
                        Exclude cointracking group from report
  --coin-report         Generate report of remaining coins and their cost
                        basis at end of year
  --simplified-k4       Generate simplified K4 with only two line per coin
                        type (aggregated profit and loss).
  --rounding-report     Generate report of roundings done which can be pasted
                        in Ovriga Upplysningar, the file will be put in the
                        out folder.
  --rounding-report-threshold ROUNDING_REPORT_THRESHOLD
                        The number of percent difference required for an
                        amount to be included in the report.
  --cointracking-usd    Use this flag if you have configured cointracking
                        calculate prices in USD. Conversion from USD to SEK
                        will then be done by this script instead.
  --max-overdraft MAX_OVERDRAFT
                        The maximum overdraft to allow for each coin, at the
                        event of an overdraft the coin balance will be set to
                        zero.
  --income-report       Generate T2 income report CSV for taxable crypto
                        income (Mining, Staking, Interest, etc.)
  --t2-sru              Generate T2 SRU file for electronic submission to
                        Skatteverket (hobby income form)
  --t2-expenses N       Total expenses (kontanta utgifter) for T2 form in SEK
  --t2-schablon PCT     Schablonavdrag percentage (0.25 for born 1959+, 0.10 older)
  --calculation-report  Generate detailed calculation report showing cost
                        basis changes per trade (CSV format)
  --validate            Validate trade data before processing
  --check-transfers     Check for unmatched withdrawals/deposits
  --holdings            Show current holdings summary after processing
  --save-state          Save coin state at end of year for use in next year
  --load-state FILE     Load coin state from file (e.g., out/coin_state_2024.json)
  --update-rates        Update USD/SEK rates from Riksbanken before processing
```

### Example

#### Generate a simplified report for 2017 in sru format.

```
python report.py 2017 --simplified-k4
```

Generated sru files can be found in the ```out``` folder.

Generated sru files can be tested for errors at [https://www.skatteverket.se/filoverforing]

#### Generate a simplified report for 2017 in sru format with a rounding report with threshold of 1%.

```
python report.py 2017 --simplified-k4 --rounding-report --rounding-report-threshold=1
```

Generated sru files and the rounding report can be found in the ```out``` folder.

Generated sru files can be tested for errors at [https://www.skatteverket.se/filoverforing]

#### Generate report for 2017 in pdf format.

```
python report.py --format=pdf 2017
```

Generated pdf files can be found in the ```out``` folder.

#### Generate calculation report showing cost basis changes

The calculation report shows how each trade affects your cost basis, useful for
understanding and verifying the tax calculation.

```
python report.py 2024 --simplified-k4 --calculation-report
```

This generates:
- `out/calculation_report.csv` - All trades with cost basis changes
- `out/calculation_report_{COIN}.csv` - Per-coin breakdown

The report includes columns (in Swedish): Datum, Symbol, Typ, Händelse (Köp/Sälj),
Antal, Pris, Totalt antal, Totalt omkostnadsbelopp, Genomsnittligt omkostnadsbelopp,
Vinst, Förlust.

#### Generate T2 hobby income report

If you have crypto income from mining, staking, interest, etc., this needs to be
reported on a T2 form as hobby income.

```
# Generate CSV report only
python report.py 2024 --income-report

# Generate SRU file for upload to Skatteverket (appended to K4 blanketter.sru)
python report.py 2024 --simplified-k4 --t2-sru

# With expenses deduction
python report.py 2024 --simplified-k4 --t2-sru --t2-expenses 5000
```

The T2 SRU file is appended to `blanketter.sru` so you can upload both K4 and T2
in a single file to Skatteverket's filöverföring.

#### Validate trades and check for issues

```
python report.py 2024 --validate --check-transfers
```

This checks for common issues like missing cost basis, negative balances, and
unmatched withdrawal/deposit pairs.

#### Save and load coin state between years

To continue from the previous year's holdings without reprocessing all history:

```
# Generate 2023 report and save state
python report.py 2023 --simplified-k4 --save-state

# Generate 2024 report loading 2023 state
python report.py 2024 --simplified-k4 --load-state out/coin_state_2023.json
```

#### Update exchange rates

```
# Update rates and generate report
python report.py 2024 --update-rates --simplified-k4

# Update rates only (no report)
python report.py --update-rates
```

#### Merging the generated pdf files

Merging the pdf files can be done with Ghostscript. It might make printing a bit easier.

```
cd out
gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile=merged.pdf k4_no*.pdf
```
