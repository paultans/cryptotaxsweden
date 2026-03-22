import argparse
import datetime
import os
import shutil
import sys
from enum import Enum

from taxdata import PersonalDetails, Trades, TaxEvent
import tax


class Format(Enum):
    pdf = 'pdf'
    sru = 'sru'

    def __str__(self):
        return self.value

parser = argparse.ArgumentParser(description='Swedish cryptocurrency tax reporting script')
parser.add_argument('year', type=int, nargs='?', default=None,
                    help='Tax year to create report for')
parser.add_argument('--trades', help='Read trades from csv file', default='data/trades.csv')
parser.add_argument('--out', help='Output folder', default='out')
parser.add_argument('--format', type=Format, choices=list(Format), default=Format.sru,
                    help='The file format of the generated report')
parser.add_argument('--decimal-sru', help='Report decimal amounts in sru mode (not supported by Skatteverket yet)', action='store_true')
parser.add_argument('--exclude-groups', nargs='*', help='Exclude cointracking group from report')
parser.add_argument('--coin-report', help='Generate report of remaining coins and their cost basis at end of year', action='store_true')
parser.add_argument('--simplified-k4', help='Generate simplified K4 with only two line per coin type (aggregated profit and loss).', action='store_true')
parser.add_argument('--rounding-report', help='Generate report of roundings done which can be pasted in Ovriga Upplysningar, the file will be put in the out folder.', action='store_true')
parser.add_argument('--rounding-report-threshold', help='The number of percent difference required for an amount to be included in the report.', default='1')
parser.add_argument('--cointracking-usd', help='Use this flag if you have configured cointracking calculate prices in USD. Conversion from USD to SEK will then be done by this script instead.', action='store_true')
parser.add_argument('--max-overdraft', type=float, help='The maximum overdraft to allow for each coin, at the event of an overdraft the coin balance will be set to zero.', default=1e-9)
parser.add_argument('--income-report', help='Generate T2 income report CSV for taxable crypto income (Mining, Staking, Interest, etc.)', action='store_true')
parser.add_argument('--t2-sru', help='Generate T2 SRU file for electronic submission to Skatteverket', action='store_true')
parser.add_argument('--t2-expenses', type=int, default=0, help='Total expenses (kontanta utgifter) for T2 form in SEK')
parser.add_argument('--t2-schablon', type=float, default=0.25, help='Schablonavdrag percentage for egenavgifter (0.25 for born 1959+, 0.10 for older)')

# New features
parser.add_argument('--validate', help='Validate trade data before processing', action='store_true')
parser.add_argument('--check-transfers', help='Check for unmatched withdrawals/deposits', action='store_true')
parser.add_argument('--update-rates', help='Update USD/SEK rates from Riksbanken before processing', action='store_true')
parser.add_argument('--save-state', help='Save coin state at end of year for use in next year', action='store_true')
parser.add_argument('--load-state', help='Load coin state from file (e.g., out/coin_state_2024.json)', type=str)
parser.add_argument('--holdings', help='Show current holdings summary after processing', action='store_true')
parser.add_argument('--calculation-report', help='Generate detailed calculation report showing cost basis changes per trade', action='store_true')
parser.add_argument('--archive', help='Copy all output files to an archive folder named by tax year (e.g., out/2025/)', action='store_true')

opts = parser.parse_args()

# Handle update-rates as standalone command
if opts.update_rates:
    from rates_updater import update_rates
    update_rates()
    if opts.year is None:
        print("Rates updated. Specify a year to generate a report.")
        sys.exit(0)

# Year is required for report generation
if opts.year is None:
    parser.error("year is required for report generation")

if not os.path.isdir(opts.out):
    os.makedirs(opts.out)

# Load trades
trades = Trades.read_from(opts.trades, opts.cointracking_usd)

# Validation
if opts.validate:
    from validation import validate_trades, print_validation_report
    warnings = validate_trades(trades, opts.year)
    print_validation_report(warnings)
    errors = [w for w in warnings if w.level == 'error']
    if errors:
        print("Fix errors before proceeding.")
        sys.exit(1)

# Check transfers
if opts.check_transfers:
    from transfer_matching import find_unmatched_transfers, print_transfer_report
    unmatched, stats = find_unmatched_transfers(trades)
    print_transfer_report(unmatched, stats)

# Load personal details
personal_details = PersonalDetails.read_from("data/personal_details.json")
stock_tax_events = TaxEvent.read_stock_tax_events_from("data/stocks.json") if os.path.exists("data/stocks.json") else None

# Compute tax
from_date = datetime.datetime(year=opts.year, month=1, day=1, hour=0, minute=0)
to_date = datetime.datetime(year=opts.year, month=12, day=31, hour=23, minute=59)

tax_events, trade_events = tax.compute_tax(trades,
                             from_date,
                             to_date,
                             opts.max_overdraft,
                             exclude_groups=opts.exclude_groups if opts.exclude_groups else [],
                             coin_report_filename=os.path.join(opts.out, "coin_report.csv") if opts.coin_report else None,
                             load_state_file=opts.load_state,
                             save_state_file=os.path.join(opts.out, f"coin_state_{opts.year}.json") if opts.save_state else None,
                             show_holdings=opts.holdings,
                             track_trade_events=opts.calculation_report,
                             )

if tax_events is None:
    print(f"Aborting tax computation.")
    sys.exit(1)

# Generate calculation report if requested
if opts.calculation_report and trade_events:
    tax.generate_calculation_report(trade_events, opts.out)
    print(f"\nCalculation Report: {os.path.join(opts.out, 'calculation_report.csv')}")
    print(f"  Per-coin reports also generated in {opts.out}/")

if opts.simplified_k4:
    tax_events = tax.aggregate_per_coin(tax_events)

if opts.format == Format.sru and not opts.decimal_sru:
    if opts.rounding_report:
        threshold = float(opts.rounding_report_threshold) / 100.0
        tax.rounding_report(tax_events, threshold, os.path.join(opts.out, "rounding_report.txt"))
    tax_events = tax.convert_to_integer_amounts(tax_events)

tax_events = tax.convert_sek_to_integer_amounts(tax_events)

pages = tax.generate_k4_pages(opts.year, personal_details, tax_events, stock_tax_events=stock_tax_events)

if opts.format == Format.sru:
    tax.generate_k4_sru(pages, personal_details, opts.out)
elif opts.format == Format.pdf:
    tax.generate_k4_pdf(pages, opts.out)

tax.output_totals(tax_events, stock_tax_events=stock_tax_events)

# Generate income report for T2 form if requested
if opts.income_report:
    income_total = tax.generate_income_report(
        trades, from_date, to_date,
        os.path.join(opts.out, "income_report.csv")
    )
    print(f"\nT2 Income Report: {os.path.join(opts.out, 'income_report.csv')}")
    print(f"  Total taxable crypto income: {round(income_total)} SEK")

# Generate T2 SRU file if requested
if opts.t2_sru:
    t2_income, t2_result = tax.generate_t2_sru_report(
        trades, from_date, to_date, personal_details, opts.out,
        expenses=opts.t2_expenses,
        schablon_percent=opts.t2_schablon,
        append_to_k4=True
    )
    if t2_income > 0:
        print(f"\nT2 SRU generated (appended to blanketter.sru)")
        print(f"  Total hobby income: {t2_income:,} SEK")
        print(f"  Result (for INK1 p.1.6): {t2_result:,} SEK")
        print(f"  Note: Test with Skatteverket's test function before production use")
    else:
        print(f"\nNo taxable crypto income found - T2 SRU not generated")

# Archive output files to year folder if requested
if opts.archive:
    archive_dir = os.path.join(opts.out, str(opts.year))
    if os.path.exists(archive_dir):
        print(f"\nArchive folder {archive_dir} already exists. Overwrite? [y/N] ", end="")
        if input().strip().lower() != 'y':
            print("Archive skipped.")
            sys.exit(0)
        shutil.rmtree(archive_dir)
    os.makedirs(archive_dir)

    # Copy all files (not subdirectories) from out/ to out/YEAR/
    count = 0
    for filename in os.listdir(opts.out):
        filepath = os.path.join(opts.out, filename)
        if os.path.isfile(filepath):
            shutil.copy2(filepath, archive_dir)
            count += 1

    # Also copy the input trades.csv and personal_details.json for reproducibility
    for data_file in [opts.trades, "data/personal_details.json"]:
        if os.path.exists(data_file):
            shutil.copy2(data_file, archive_dir)
            count += 1

    print(f"\nArchived {count} files to {archive_dir}/")

