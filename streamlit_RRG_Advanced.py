import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit.runtime.scriptrunner import RerunData, RerunException
import streamlit.components.v1 as components

# Set page config to wide layout
st.set_page_config(layout="wide", page_title="Relative Rotation Graph (RRG) by JC")

class GitHubFetchError(Exception):
    pass

def fetch_portfolio_from_github(url):
    try:
        import requests
    except ImportError:
        raise GitHubFetchError("The 'requests' library is not installed. Please install it to fetch the portfolio from GitHub.")
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
        tickers = [line.strip() for line in response.text.split('\n') if line.strip()]
        if not tickers:
            raise GitHubFetchError("No tickers found in the GitHub file.")
        return tickers
    except requests.RequestException as e:
        raise GitHubFetchError(f"Failed to fetch portfolio from GitHub: {e}")

def get_preset_portfolio(portfolio_type):
    urls = {
        "Existing": "https://raw.githubusercontent.com/jasonckb/RRG_Jason/main/Existing%20Portfolio.txt",
        "Monitoring": "https://raw.githubusercontent.com/jasonckb/RRG_Jason/main/Monitoring%20Portfolio.txt",
        "US": "https://raw.githubusercontent.com/jasonckb/RRG_Jason/main/US%20Portfolio.txt"
    }
    try:
        return fetch_portfolio_from_github(urls[portfolio_type])
    except GitHubFetchError as e:
        st.error(str(e))
        st.error(f"Unable to load {portfolio_type} portfolio. Please check your internet connection or try again later.")
        return None

# ... [rest of the existing functions remain unchanged] ...

# Main Streamlit app
st.title("Relative Rotation Graph (RRG) by JC")

# Initialize session state
if 'selected_universe' not in st.session_state:
    st.session_state.selected_universe = "WORLD"
if 'data_refreshed' not in st.session_state:
    st.session_state.data_refreshed = False

# Sidebar
st.sidebar.header("Chart Settings")

# Add Refresh button at the top of the sidebar
if st.sidebar.button("Refresh Data"):
    refresh_data()
    st.rerun()

timeframe = st.sidebar.selectbox(
    "Select Timeframe",
    options=["Weekly", "Daily"],
    key="timeframe_selector"
)

tail_length = st.sidebar.slider(
    "Tail Length",
    min_value=1,
    max_value=52,
    value=5,
    step=1,
    help="Number of data points to show in the chart"
)

st.sidebar.header("Universe Selection")

universe_options = ["WORLD", "US", "US Sectors", "HK", "HK Sub-indexes", "Existing Portfolio", "Monitoring Portfolio", "US Portfolio", "FX"]
universe_names = {
    "WORLD": "World", 
    "US": "US", 
    "US Sectors": "US Sectors", 
    "HK": "Hong Kong", 
    "HK Sub-indexes": "HK Sub-indexes", 
    "Existing Portfolio": "Existing Portfolio",
    "Monitoring Portfolio": "Monitoring Portfolio",
    "US Portfolio": "US Portfolio",
    "FX": "Foreign Exchange"
}

selected_universe = st.sidebar.selectbox(
    "Select Universe",
    options=universe_options,
    format_func=lambda x: universe_names[x],
    key="universe_selector",
    index=universe_options.index(st.session_state.selected_universe)
)

# Update the selected universe in session state
st.session_state.selected_universe = selected_universe

sector = None
custom_tickers = None
custom_benchmark = None

if selected_universe == "US Sectors":
    # ... [US Sectors code remains unchanged] ...
elif selected_universe == "HK Sub-indexes":
    # ... [HK Sub-indexes code remains unchanged] ...
elif selected_universe in ["Existing Portfolio", "Monitoring Portfolio", "US Portfolio"]:
    st.sidebar.subheader(f"{selected_universe}")
    
    if 'reset_tickers' not in st.session_state:
        st.session_state.reset_tickers = False

    if f'{selected_universe.lower()}_tickers' not in st.session_state or st.session_state.reset_tickers:
        st.session_state[f'{selected_universe.lower()}_tickers'] = get_preset_portfolio(selected_universe.split()[0])

    col1, col2, col3 = st.sidebar.columns(3)
    
    custom_tickers = []
    for i in range(15):
        if i % 3 == 0:
            ticker = col1.text_input(f"Stock {i+1}", key=f"{selected_universe.lower()}_stock_{i+1}", value=st.session_state[f'{selected_universe.lower()}_tickers'][i] if i < len(st.session_state[f'{selected_universe.lower()}_tickers']) else "")
        elif i % 3 == 1:
            ticker = col2.text_input(f"Stock {i+1}", key=f"{selected_universe.lower()}_stock_{i+1}", value=st.session_state[f'{selected_universe.lower()}_tickers'][i] if i < len(st.session_state[f'{selected_universe.lower()}_tickers']) else "")
        else:
            ticker = col3.text_input(f"Stock {i+1}", key=f"{selected_universe.lower()}_stock_{i+1}", value=st.session_state[f'{selected_universe.lower()}_tickers'][i] if i < len(st.session_state[f'{selected_universe.lower()}_tickers']) else "")
        
        if ticker:
            if ticker.isalpha():
                processed_ticker = ticker.upper()
            elif ticker.isdigit():
                processed_ticker = f"{ticker.zfill(4)}.HK"
            else:
                processed_ticker = ticker
            custom_tickers.append(processed_ticker)
    
    st.session_state[f'{selected_universe.lower()}_tickers'] = custom_tickers

    custom_benchmark = st.sidebar.selectbox(
        "Select Benchmark",
        options=["ACWI", "^GSPC", "^HSI"],
        key=f"{selected_universe.lower()}_benchmark_selector"
    )

    # Add Reset button
    if st.sidebar.button(f"Reset to Preset {selected_universe}"):
        st.session_state[f'{selected_universe.lower()}_tickers'] = get_preset_portfolio(selected_universe.split()[0])
        st.rerun()

    # Reset the flag after use
    if st.session_state.reset_tickers:
        st.session_state.reset_tickers = False

# Main content area
if selected_universe:
    data, benchmark, sectors, sector_names = get_data(selected_universe, sector, timeframe, custom_tickers, custom_benchmark)
    if data is not None and not data.empty:
        fig = create_rrg_chart(data, benchmark, sectors, sector_names, selected_universe, timeframe, tail_length)
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("Latest Data")
        st.dataframe(data.tail())
        
        if st.session_state.data_refreshed:
            st.success("Data refreshed successfully!")
            st.session_state.data_refreshed = False
    else:
        st.error("No data available for the selected universe and sector. Please try a different selection.")
else:
    st.write("Please select a universe from the sidebar.")

if st.checkbox("Show raw data"):
    st.write("Raw data:")
    st.write(data)
    st.write("Sectors:")
    st.write(sectors)
    st.write("Benchmark:")
    st.write(benchmark)