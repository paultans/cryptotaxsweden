"""Streamlit web UI for Swedish Crypto Tax Reporter.

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import datetime
import os
import sys
import io
from typing import Optional

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from taxdata import PersonalDetails, Trades, TaxEvent
import tax
from validation import validate_trades, ValidationWarning
from transfer_matching import find_unmatched_transfers


st.set_page_config(
    page_title="Swedish Crypto Tax Reporter",
    page_icon="💰",
    layout="wide"
)

st.title("🇸🇪 Swedish Crypto Tax Reporter")
st.markdown("Generate K4 forms for Skatteverket from your CoinTracking data")

# Sidebar for settings
st.sidebar.header("⚙️ Settings")

# Year selection
current_year = datetime.datetime.now().year
year = st.sidebar.selectbox(
    "Tax Year",
    options=list(range(current_year, 2014, -1)),
    index=0
)

# File upload
st.sidebar.header("📁 Data Files")
trades_file = st.sidebar.file_uploader("Trades CSV (from CoinTracking)", type=['csv'])

# Options
st.sidebar.header("📋 Options")
use_usd = st.sidebar.checkbox("CoinTracking prices in USD", value=False)
simplified_k4 = st.sidebar.checkbox("Simplified K4 (aggregate per coin)", value=True)
generate_income_report = st.sidebar.checkbox("Generate T2 Income Report", value=True)
show_holdings = st.sidebar.checkbox("Show Holdings Summary", value=True)

# Advanced options
with st.sidebar.expander("Advanced Options"):
    max_overdraft = st.number_input("Max Overdraft", value=0.000001, format="%.6f")
    output_format = st.selectbox("Output Format", ["SRU", "PDF"])

# Main content area
if trades_file is None:
    st.info("👆 Upload your trades CSV file from CoinTracking to get started")
    
    st.markdown("""
    ### How to export from CoinTracking:
    1. Go to [CoinTracking.info](https://cointracking.info)
    2. Navigate to **Enter Coins** → **Trade Table**
    3. Click **Export** and choose **CSV**
    4. Upload the file here
    
    ### Supported Trade Types:
    - Trade, Mining, Gift/Tip, Spend, Airdrop
    - Staking, Interest Income, Reward/Bonus, Income
    """)
else:
    # Save uploaded file temporarily
    trades_path = "data/trades_upload.csv"
    with open(trades_path, "wb") as f:
        f.write(trades_file.getvalue())
    
    # Load trades
    try:
        trades = Trades.read_from(trades_path, use_usd)
        st.success(f"✅ Loaded {len(trades.trades)} trades")
    except Exception as e:
        st.error(f"❌ Error loading trades: {e}")
        st.stop()
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Validation", "🔄 Transfers", "📄 Generate Report", "📈 Holdings"])
    
    with tab1:
        st.header("Trade Data Validation")
        
        warnings = validate_trades(trades, year)
        
        if not warnings:
            st.success("✅ No validation issues found!")
        else:
            errors = [w for w in warnings if w.level == 'error']
            warns = [w for w in warnings if w.level == 'warning']
            infos = [w for w in warnings if w.level == 'info']
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Errors", len(errors), delta=None if len(errors) == 0 else "Fix required")
            col2.metric("Warnings", len(warns))
            col3.metric("Info", len(infos))
            
            if errors:
                st.error("### ❌ Errors (must fix)")
                for w in errors:
                    st.markdown(f"- Line {w.lineno}: {w.message}")
            
            if warns:
                st.warning("### ⚠️ Warnings")
                for w in warns:
                    st.markdown(f"- Line {w.lineno}: {w.message}")
            
            if infos:
                st.info("### ℹ️ Information")
                for w in infos:
                    st.markdown(f"- {w.message}")
    
    with tab2:
        st.header("Withdrawal/Deposit Matching")
        
        unmatched, stats = find_unmatched_transfers(trades)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Withdrawals", stats['total_withdrawals'])
        col2.metric("Total Deposits", stats['total_deposits'])
        col3.metric("Matched Pairs", stats['matched_pairs'])
        
        if unmatched:
            st.warning(f"Found {len(unmatched)} unmatched transfers")
            
            # Group by coin
            df_data = []
            for u in unmatched:
                df_data.append({
                    'Type': u.transfer_type.upper(),
                    'Coin': u.coin,
                    'Amount': u.amount,
                    'Date': u.date.strftime('%Y-%m-%d'),
                    'Line': u.lineno
                })
            
            st.dataframe(pd.DataFrame(df_data), use_container_width=True)
        else:
            st.success("✅ All transfers matched!")
    
    with tab3:
        st.header("Generate Report")
        
        # Check if we can proceed
        errors = [w for w in validate_trades(trades, year) if w.level == 'error']
        
        if errors:
            st.error(f"❌ Fix {len(errors)} validation errors before generating report")
        else:
            # Personal details
            st.subheader("Personal Details")
            
            col1, col2 = st.columns(2)
            name = col1.text_input("Name", value="")
            personnummer = col2.text_input("Personnummer", value="", placeholder="YYYYMMDD-XXXX")
            
            col3, col4 = st.columns(2)
            postnummer = col3.text_input("Postnummer", value="")
            postort = col4.text_input("Postort", value="")
            
            if st.button("🚀 Generate Report", type="primary"):
                if not all([name, personnummer, postnummer, postort]):
                    st.error("Please fill in all personal details")
                else:
                    with st.spinner("Generating report..."):
                        # Create personal details
                        personal = PersonalDetails(name, personnummer, postnummer, postort)
                        
                        # Compute tax
                        from_date = datetime.datetime(year=year, month=1, day=1)
                        to_date = datetime.datetime(year=year, month=12, day=31, hour=23, minute=59)
                        
                        tax_events = tax.compute_tax(
                            trades, from_date, to_date, max_overdraft,
                            exclude_groups=[]
                        )
                        
                        if tax_events is None:
                            st.error("Error computing tax events")
                        else:
                            if simplified_k4:
                                tax_events = tax.aggregate_per_coin(tax_events)
                            
                            # Convert to integers for SRU
                            if output_format == "SRU":
                                display_events = tax.convert_to_integer_amounts(tax_events.copy())
                            else:
                                display_events = tax_events
                            
                            display_events = tax.convert_sek_to_integer_amounts(display_events)
                            
                            # Generate pages
                            pages = tax.generate_k4_pages(year, personal, display_events)
                            
                            # Generate output files
                            output_dir = "out/streamlit"
                            os.makedirs(output_dir, exist_ok=True)
                            
                            if output_format == "SRU":
                                tax.generate_k4_sru(pages, personal, output_dir)
                                
                                # Read generated files
                                with open(f"{output_dir}/info.sru", "r") as f:
                                    info_sru = f.read()
                                with open(f"{output_dir}/blanketter.sru", "r") as f:
                                    blanketter_sru = f.read()
                                
                                st.success("✅ SRU files generated!")
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.download_button(
                                        "📥 Download info.sru",
                                        info_sru,
                                        file_name="info.sru",
                                        mime="text/plain"
                                    )
                                with col2:
                                    st.download_button(
                                        "📥 Download blanketter.sru",
                                        blanketter_sru,
                                        file_name="blanketter.sru",
                                        mime="text/plain"
                                    )
                            else:
                                tax.generate_k4_pdf(pages, output_dir)
                                st.success("✅ PDF files generated in out/streamlit/")
                            
                            # Show totals
                            st.subheader("Tax Summary")
                            crypto_events = [x for x in display_events if not tax.is_fiat(x.name)]
                            
                            profit = sum([x.profit() if x.profit() > 0 else 0 for x in crypto_events])
                            loss = sum([-x.profit() if x.profit() < 0 else 0 for x in crypto_events])
                            
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Total Profit", f"{profit:,.0f} SEK")
                            col2.metric("Total Loss", f"{loss:,.0f} SEK")
                            col3.metric("Estimated Tax", f"{round(0.3*(profit - 0.7*loss)):,.0f} SEK")
    
    with tab4:
        st.header("Holdings Summary")
        
        from_date = datetime.datetime(year=year, month=1, day=1)
        to_date = datetime.datetime(year=year, month=12, day=31, hour=23, minute=59)
        
        # We need to recompute to get coin balances
        # This is a simplified version - in production we'd cache this
        coins_data = []
        
        # Simulate compute to get holdings
        coins = {}
        for trade in trades.trades:
            if trade.date > to_date:
                break
            
            if trade.buy_coin and trade.buy_coin not in ['SEK', 'EUR', 'USD']:
                if trade.buy_coin not in coins:
                    coins[trade.buy_coin] = {'amount': 0.0, 'cost_basis': 0.0}
                old_amount = coins[trade.buy_coin]['amount']
                new_amount = old_amount + (trade.buy_amount or 0)
                if new_amount > 0:
                    old_cost = coins[trade.buy_coin]['cost_basis'] * old_amount
                    new_cost = (trade.buy_value or 0)
                    coins[trade.buy_coin]['cost_basis'] = (old_cost + new_cost) / new_amount
                    coins[trade.buy_coin]['amount'] = new_amount
            
            if trade.sell_coin and trade.sell_coin not in ['SEK', 'EUR', 'USD']:
                if trade.sell_coin in coins:
                    coins[trade.sell_coin]['amount'] -= (trade.sell_amount or 0)
                    if coins[trade.sell_coin]['amount'] < 0:
                        coins[trade.sell_coin]['amount'] = 0
        
        # Build display data
        for symbol, data in sorted(coins.items()):
            if data['amount'] > 0.0001:
                coins_data.append({
                    'Coin': symbol,
                    'Amount': data['amount'],
                    'Cost Basis (SEK/unit)': data['cost_basis'],
                    'Total Cost (SEK)': data['amount'] * data['cost_basis']
                })
        
        if coins_data:
            df = pd.DataFrame(coins_data)
            st.dataframe(df, use_container_width=True)
            
            total_cost = sum(d['Total Cost (SEK)'] for d in coins_data)
            st.metric("Total Portfolio Cost Basis", f"{total_cost:,.0f} SEK")
        else:
            st.info("No holdings found for this year")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Made with ❤️ for Swedish crypto tax reporting")
