import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit.runtime.scriptrunner import RerunData, RerunException
import streamlit.components.v1 as components

# Set page config to wide layout
st.set_page_config(layout="wide", page_title="Asset Rotation Analysis by JC Algos")

class GitHubFetchError(Exception):
    pass

def fetch_portfolio_from_github(portfolio_type="HK"):
    try:
        import requests
    except ImportError:
        raise GitHubFetchError("The 'requests' library is not installed. Please install it to fetch the portfolio from GitHub.")
    
    if portfolio_type == "HK":
        url = "https://raw.githubusercontent.com/JC-Algos/Ultimate-Stock-Analyst/main/Customised%20Portfolio_HK.txt"
    else:  # US
        url = "https://raw.githubusercontent.com/JC-Algos/Ultimate-Stock-Analyst/main/Customised%20Portfolio_US.txt"
    
    st.info(f"Attempting to fetch portfolio from: {url}")
    
    try:
        response = requests.get(url)
        st.info(f"Response status code: {response.status_code}")
        
        response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
        
        content = response.text
        st.info(f"Received content: {content[:100]}...") # Show first 100 chars
        
        tickers = [line.strip() for line in content.split('\n') if line.strip()]
        st.info(f"Parsed tickers: {tickers}")
        
        if not tickers:
            raise GitHubFetchError(f"No tickers found in the GitHub file for {portfolio_type} portfolio.")
        return tickers
    except requests.RequestException as e:
        raise GitHubFetchError(f"Failed to fetch {portfolio_type} portfolio from GitHub: {e}")

def get_preset_portfolio(portfolio_type="HK"):
    try:
        return fetch_portfolio_from_github(portfolio_type)
    except GitHubFetchError as e:
        st.error(str(e))
        st.error(f"Failed to fetch {portfolio_type} portfolio from GitHub: {e}")
        # Let's suggest setting up a fallback default portfolio
        if portfolio_type == "HK":
            return ["0005.HK", "0700.HK", "3988.HK", "0388.HK", "1398.HK"]
        else:
            return ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]


def refresh_data():
    try:
        # Clear all cached data
        st.cache_data.clear()
        
        # Re-fetch data for the current universe
        universe = st.session_state.get('selected_universe', 'WORLD')
        sector = st.session_state.get('sector', None)
        timeframe = st.session_state.get('timeframe', 'Weekly')
        custom_tickers = st.session_state.get('custom_tickers', None)
        custom_benchmark = st.session_state.get('custom_benchmark', None)
        
        # Call get_data with current parameters to refresh the data
        get_data(universe, sector, timeframe, custom_tickers, custom_benchmark)
        
        st.session_state.data_refreshed = True
        st.success("Data refreshed successfully!")
    except Exception as e:
        st.error(f"An error occurred while refreshing data: {str(e)}")
        st.session_state.data_refreshed = False


@st.cache_data
def ma(data, period):
    return data.rolling(window=period).mean()

@st.cache_data
def calculate_rrg_values(data, benchmark):
    sbr = data / benchmark
    rs1 = ma(sbr, 10)
    rs2 = ma(sbr, 26)
    rs = 100 * ((rs1 - rs2) / rs2 + 1)
    rm1 = ma(rs, 1)
    rm2 = ma(rs, 4)
    rm = 100 * ((rm1 - rm2) / rm2 + 1)
    return rs, rm

@st.cache_data
def get_data(universe, sector, timeframe, custom_tickers=None, custom_benchmark=None):
    end_date = datetime.now()
    if timeframe == "Weekly":
        start_date = end_date - timedelta(weeks=100)
    else:  # Daily
        start_date = end_date - timedelta(days=500)

    sector_universes = {
        "US": {
            "XLK": ["AAPL", "MSFT", "NVDA", "AVGO", "ADBE", "MU", "CRM", "ASML", "SNPS", "IBM", "INTC", "TXN", "NOW", "QCOM", "AMD", "AMAT", "NOW", "PANW", "CDNS", "TSMC"],
            "XLY": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX", "BKNG", "MAR", "F", "GM", "ORLY", "DHI", "CMG", "TJX", "YUM", "LEN", "ULTA", "CCL", "EXPE"],
            "XLV": ["UNH", "JNJ", "LLY", "PFE", "ABT", "TMO", "MRK", "ABBV", "DHR", "BMY", "AMGN", "CVS", "ISRG", "MDT", "GILD", "VRTX", "CI", "ZTS", "RGEN", "BSX", "HCA"],
            "XLF": ["BRK.B", "JPM", "BAC", "WFC", "GS", "MS", "SPGI", "BLK", "C", "AXP", "CB", "MMC", "PGR", "PNC", "TFC", "V", "MA", "PYPL", "AON", "CME", "ICE", "COF"],
            "XLC": ["META", "GOOGL", "GOOG", "NFLX", "CMCSA", "DIS", "VZ", "T", "TMUS", "ATVI", "EA", "TTWO", "MTCH", "CHTR", "DISH", "FOXA", "TTWO", "FOX", "NWS", "WBD"],
            "XLI": ["UNP", "HON", "UPS", "BA", "CAT", "GE", "MMM", "RTX", "LMT", "FDX", "DE", "ETN", "EMR", "NSC", "CSX", "ADP", "GD", "NOC", "FDX", "JCI", "CARR", "ITW"],
            "XLE": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "KMI", "WMB", "HES", "HAL", "DVN", "BKR", "CTRA", "EQT", "APA", "MRO", "TRGP", "FANG"],
            "XLB": ["LIN", "APD", "SHW", "FCX", "ECL", "NEM", "DOW", "DD", "CTVA", "PPG", "NUE", "VMC", "ALB", "FMC", "CE", "MLM", "IFF", "STLD", "CF", "FMC"],
            "XLP": ["PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "EL", "CL", "GIS", "KMB", "SYY", "KHC", "STZ", "HSY", "TGT", "ADM", "MNST", "DG", "DLTR", "WBA", "SJM"],
            "XLU": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "PCG", "WEC", "ES", "ED", "DTE", "AEE", "ETR", "CEG", "PCG", "EIX", "FFE", "CMS", "CNP", "PPL"],
            "XLRE": ["PLD", "AMT", "CCI", "EQIX", "PSA", "O", "WELL", "SPG", "SBAC", "AVB", "EQR", "DLR", "VTR", "ARE", "CBRE", "WY", "EXR", "MAA", "IRM", "ESS", "HST"]
        },
        "HK": {
            "^HSNU": ["0002.HK", "0003.HK", "0006.HK", "0836.HK", "1038.HK", "2688.HK",],
            "^HSNF": ["0005.HK", "0011.HK", "0388.HK", "0939.HK", "1398.HK", "2318.HK", "2388.HK", "2628.HK","3968.HK","3988.HK","1299.HK"],
            "^HSNP": ["0012.HK", "0016.HK", "0017.HK", "0101.HK", "0823.HK", "0688.HK", "1109.HK", "1997.HK", "1209.HK", "0960.HK","1113.HK"],
            "^HSNC": ["0700.HK", "0857.HK", "0883.HK", "0941.HK", "0001.HK","0175.HK","0241.HK","0267.HK","0285.HK","0027.HK",
                      "0288.HK","0291.HK","0316.HK","0332.HK", "0386.HK", "0669.HK", "0762.HK", "0968.HK", "0981.HK", "0386.HK"]
        }
    }

    if universe == "WORLD":
        benchmark = "ACWI"
        sectors = ["^GSPC", "^NDX", "^RUT", "^HSI", "3032.HK", "^STOXX50E", "^BSESN", "^KS11", 
                   "^TWII", "000300.SS", "^N225", "HYG", "AGG", "EEM", "GDX", "XLE", "XME", "AAXJ","IBB","DBA"]
        sector_names = {
            "^GSPC": "標普500", "^NDX": "納指100", "^RUT": "羅素2000", "^HSI": "恆指",
            "3032.HK": "恒生科技", "^STOXX50E": "歐洲", "^BSESN": "印度", "^KS11": "韓國",
            "^TWII": "台灣", "000300.SS": "滬深300", "^N225": "日本", "HYG": "高收益債券",
            "AGG": "投資級別債券", "EEM": "新興市場", "GDX": "金礦", "XLE": "能源",
            "XME": "礦業", "AAXJ": "亞太日本除外", "IBB": "生物科技","DBA":"農業"
        }
    elif universe == "US":
        benchmark = "^GSPC"
        sectors = list(sector_universes["US"].keys())
        sector_names = {
            "XLK": "科技", "XLY": "非必須消費", "XLV": "健康護理",
            "XLF": "金融", "XLC": "通訊", "XLI": "工業", "XLE": "能源",
            "XLB": "物料", "XLP": "必須消費", "XLU": "公用", "XLRE": "房地產"
        }
    elif universe == "US Sectors":
        if sector:
            benchmark = sector
            sectors = sector_universes["US"][sector]
            sector_names = {s: "" for s in sectors}
        else:
            st.error("Please select a US sector.")
            return None, None, None, None
    elif universe == "HK":
        benchmark = "^HSI"
        sectors = list(sector_universes["HK"].keys())
        sector_names = {"^HSNU": "公用", "^HSNF": "金融", "^HSNP": "地產", "^HSNC": "工商"}
    elif universe == "HK Sub-indexes":
        if sector:
            benchmark = sector
            sectors = sector_universes["HK"][sector]
            sector_names = {s: "" for s in sectors}
        else:
            st.error("Please select a HK sub-index.")
            return None, None, None, None
    elif universe == "Customised Portfolio_HK" or universe == "Customised Portfolio_US":
        if custom_benchmark and custom_tickers and len(custom_tickers) > 0:
            benchmark = custom_benchmark
            sectors = [ticker for ticker in custom_tickers if ticker]
            sector_names = {s: "" for s in sectors}
            st.info(f"Using custom benchmark: {benchmark} and tickers: {sectors}")
        else:
            portfolio_type = "HK" if universe == "Customised Portfolio_HK" else "US"
            st.error(f"Please provide at least one stock ticker and select a benchmark for your custom {portfolio_type} portfolio.")
            return None, None, None, None
    elif universe == "FX":
        benchmark = "HKDUSD=X"
        sectors = ["GBPUSD=X", "EURUSD=X", "AUDUSD=X", "NZDUSD=X", "CADUSD=X", "CHFUSD=X", "JPYUSD=X", "CNYUSD=X",  "EURGBP=X", "AUDNZD=X", "AUDCAD=X", "NZDCAD=X", "DX-Y.NYB"]
        sector_names = {
            "GBPUSD=X": "GBP", "EURUSD=X": "EUR", "AUDUSD=X": "AUD", "NZDUSD=X": "NZD",
            "CADUSD=X": "CAD",  "JPYUSD=X": "JPY", "EURGBP=X": "EURGBP", "AUDNZD=X": "AUDNZD",
            "AUDCAD=X": "AUDCAD", "NZDCAD=X": "NZDCAD", "DX-Y.NYB":"DXY", "CHFUSD=X":"CHF","CNYUSD=X":"CNY" 
        }
    else:
        st.error("Invalid universe selection.")
        return None, None, None, None

    try:
        tickers_to_download = [benchmark] + sectors
        st.info(f"Attempting to download data for: {', '.join(tickers_to_download)}")
        
        data = yf.download(tickers_to_download, start=start_date, end=end_date)['Close']
        
        # Check the actual date range of the downloaded data
        actual_start_date = data.index.min()
        actual_end_date = data.index.max()
        
        st.info(f"Data available from {actual_start_date.date()} to {actual_end_date.date()}")
        
        if actual_end_date.date() < end_date.date() - timedelta(days=1):
            st.warning(f"The most recent data available is from {actual_end_date.date()}. "
                       f"This may be due to market holidays or delays in data updates.")
        
        missing_tickers = set(tickers_to_download) - set(data.columns)
        if missing_tickers:
            st.warning(f"The following tickers could not be downloaded: {', '.join(missing_tickers)}")
            
            if universe == "WORLD":
                if "^TWII" in missing_tickers:
                    st.info("Attempting to download alternative for ^TWII: TAIEX")
                    twii_data = yf.download("TAIEX", start=start_date, end=end_date)['Close']
                    if not twii_data.empty:
                        data["^TWII"] = twii_data
                        missing_tickers.remove("^TWII")
                        st.success("Successfully downloaded TAIEX as a proxy for ^TWII")
                
                if "3032.HK" in missing_tickers:
                    st.info("Attempting to download alternative for 3032.HK: ^HSTECH")
                    hstech_data = yf.download("^HSTECH", start=start_date, end=end_date)['Close']
                    if not hstech_data.empty:
                        data["3032.HK"] = hstech_data
                        missing_tickers.remove("3032.HK")
                        st.success("Successfully downloaded ^HSTECH as a proxy for 3032.HK")
            
            for missing_ticker in missing_tickers:
                data[missing_ticker] = pd.Series(index=data.index, dtype='float64')

        if data.empty:
            st.error(f"No data available for the selected universe and sector.")
            return None, benchmark, sectors, sector_names
        
        data = data.dropna(axis=1, how='all')
        
        if benchmark not in data.columns:
            st.error(f"No data available for the benchmark {benchmark}. Please choose a different benchmark.")
            return None, benchmark, sectors, sector_names
        
        valid_sectors = [s for s in sectors if s in data.columns]
        if len(valid_sectors) == 0:
            st.error("No valid sector data available. Please check your input and try again.")
            return None, benchmark, sectors, sector_names
        
        sectors = valid_sectors
        sector_names = {s: sector_names[s] for s in valid_sectors if s in sector_names}
        
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None, benchmark, sectors, sector_names

    st.success(f"Successfully downloaded data for {len(data.columns)} tickers.")
    return data, benchmark, sectors, sector_names

def create_rrg_chart(data, benchmark, sectors, sector_names, universe, timeframe, tail_length):
    if timeframe == "Weekly":
        data_resampled = data.resample('W-FRI').last()
    else:  # Daily
        data_resampled = data

    rrg_data = pd.DataFrame()
    for sector in sectors:
        rs_ratio, rs_momentum = calculate_rrg_values(data_resampled[sector], data_resampled[benchmark])
        rrg_data[f"{sector}_RS-Ratio"] = rs_ratio
        rrg_data[f"{sector}_RS-Momentum"] = rs_momentum

    # Consider last 10 data points for boundary calculation
    boundary_data = rrg_data.iloc[-10:]
    
    padding = 0.1
    min_x = boundary_data[[f"{sector}_RS-Ratio" for sector in sectors]].min().min()
    max_x = boundary_data[[f"{sector}_RS-Ratio" for sector in sectors]].max().max()
    min_y = boundary_data[[f"{sector}_RS-Momentum" for sector in sectors]].min().min()
    max_y = boundary_data[[f"{sector}_RS-Momentum" for sector in sectors]].max().max()

    range_x = max_x - min_x
    range_y = max_y - min_y
    min_x = max(min_x - range_x * padding, 70)
    max_x = min(max_x + range_x * padding, 130)
    min_y = max(min_y - range_y * padding, 70)
    max_y = min(max_y + range_y * padding, 130)

    fig = go.Figure()

    quadrant_colors = {"Lagging": "pink", "Weakening": "lightyellow", "Improving": "lightblue", "Leading": "lightgreen"}
    curve_colors = {"Lagging": "red", "Weakening": "orange", "Improving": "darkblue", "Leading": "darkgreen"}

    def get_quadrant(x, y):
        if x < 100 and y < 100: return "Lagging"
        elif x >= 100 and y < 100: return "Weakening"
        elif x < 100 and y >= 100: return "Improving"
        else: return "Leading"

    for sector in sectors:
        x_values = rrg_data[f"{sector}_RS-Ratio"].iloc[-tail_length:].dropna()
        y_values = rrg_data[f"{sector}_RS-Momentum"].iloc[-tail_length:].dropna()
        if len(x_values) > 0 and len(y_values) > 0:
            current_quadrant = get_quadrant(x_values.iloc[-1], y_values.iloc[-1])
            color = curve_colors[current_quadrant]
            
            if universe == "FX":
                legend_label = f"{sector} ({sector_names.get(sector, '')})"
                chart_label = sector_names.get(sector, sector)
            elif universe == "US Sectors" or universe == "HK Sub-indexes" or universe == "Customised Portfolio_HK" or universe == "Customised Portfolio_US":
                legend_label = sector
                chart_label = sector.replace('.HK', '')
            else:
                legend_label = f"{sector} ({sector_names.get(sector, '')})"
                chart_label = f"{sector_names.get(sector, sector)}"
            
            fig.add_trace(go.Scatter(
                x=x_values, y=y_values, mode='lines+markers', name=legend_label,
                line=dict(color=color, width=2), marker=dict(size=6, symbol='circle'),
                legendgroup=sector, showlegend=True
            ))
            
            # Determine text position based on momentum comparison
            if len(y_values) > 1:
                current_momentum = y_values.iloc[-1]
                last_momentum = y_values.iloc[-2]
                text_position = "top center" if current_momentum > last_momentum else "bottom center"
            else:
                text_position = "top center"
            
            # Add only the latest point as a larger marker with text
            fig.add_trace(go.Scatter(
                x=[x_values.iloc[-1]], y=[y_values.iloc[-1]], mode='markers+text',
                name=f"{sector} (latest)", marker=dict(color=color, size=12, symbol='circle'),
                text=[chart_label], textposition=text_position, legendgroup=sector, showlegend=False,
                textfont=dict(color='black', size=12, family='Arial Black')
            ))

    fig.update_layout(
        title=f"Asset Rotation Analysis for {universe} ({timeframe})",
        xaxis_title="RS-Ratio",
        yaxis_title="RS-Momentum",
        width=1200,
        height=800,
        xaxis=dict(range=[min_x, max_x], title_font=dict(size=14)),
        yaxis=dict(range=[min_y, max_y], title_font=dict(size=14)),
        plot_bgcolor='white',
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.02, title=f"Legend<br>Benchmark: {benchmark}"),
        shapes=[
            dict(type="rect", xref="x", yref="y", x0=min_x, y0=100, x1=100, y1=max_y, fillcolor="lightblue", opacity=0.35, line_width=0),
            dict(type="rect", xref="x", yref="y", x0=100, y0=100, x1=max_x, y1=max_y, fillcolor="lightgreen", opacity=0.35, line_width=0),
            dict(type="rect", xref="x", yref="y", x0=min_x, y0=min_y, x1=100, y1=100, fillcolor="pink", opacity=0.35, line_width=0),
            dict(type="rect", xref="x", yref="y", x0=100, y0=min_y, x1=max_x, y1=100, fillcolor="lightyellow", opacity=0.35, line_width=0),
            dict(type="line", xref="x", yref="y", x0=100, y0=min_y, x1=100, y1=max_y, line=dict(color="black", width=1)),
            dict(type="line", xref="x", yref="y", x0=min_x, y0=100, x1=max_x, y1=100, line=dict(color="black", width=1)),
        ]
    )

    label_font = dict(size=32, color='black', family='Arial Black')
    fig.add_annotation(x=min_x, y=min_y, text="落後", showarrow=False, font=label_font, xanchor="left", yanchor="bottom")
    fig.add_annotation(x=max_x, y=min_y, text="轉弱", showarrow=False, font=label_font, xanchor="right", yanchor="bottom")
    fig.add_annotation(x=min_x, y=max_y, text="改善", showarrow=False, font=label_font, xanchor="left", yanchor="top")
    fig.add_annotation(x=max_x, y=max_y, text="領先", showarrow=False, font=label_font, xanchor="right", yanchor="top")

    return fig



# Main Streamlit app
st.title("Asset Rotation Analysis by JC Algos")

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

universe_options = ["WORLD", "US", "US Sectors", "HK", "HK Sub-indexes", "Customised Portfolio_HK", "Customised Portfolio_US", "FX"]
universe_names = {
    "WORLD": "World", 
    "US": "US", 
    "US Sectors": "US Sectors", 
    "HK": "Hong Kong", 
    "HK Sub-indexes": "HK Sub-indexes", 
    "Customised Portfolio_HK": "Customised Portfolio - Hong Kong",
    "Customised Portfolio_US": "Customised Portfolio - US",
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

# Initialize variables for different universes
sector = None
custom_tickers = None
custom_benchmark = None

# Debugging display for session state
st.sidebar.write("Debug - Session State Keys:", list(st.session_state.keys()))

if selected_universe == "US Sectors":
    us_sectors = ["XLK", "XLY", "XLV", "XLF", "XLC", "XLI", "XLE", "XLB", "XLP", "XLU", "XLRE"]
    us_sector_names = {
        "XLK": "Technology", "XLY": "Consumer Discretionary", "XLV": "Health Care",
        "XLF": "Financials", "XLC": "Communications", "XLI": "Industrials", "XLE": "Energy",
        "XLB": "Materials", "XLP": "Consumer Staples", "XLU": "Utilities", "XLRE": "Real Estate"
    }
    st.sidebar.subheader("US Sectors")
    selected_us_sector = st.sidebar.selectbox(
        "Select US Sector",
        options=us_sectors,
        format_func=lambda x: us_sector_names[x],
        key="us_sector_selector"
    )
    if selected_us_sector:
        sector = selected_us_sector
elif selected_universe == "HK Sub-indexes":
    hk_sectors = ["^HSNU", "^HSNF", "^HSNP", "^HSNC"]
    hk_sector_names = {"^HSNU": "Utilities", "^HSNF": "Financials", "^HSNP": "Properties", "^HSNC": "Commerce & Industry"}
    st.sidebar.subheader("Hang Seng Sub-indexes")
    selected_hk_sector = st.sidebar.selectbox(
        "Select HK Sub-index",
        options=hk_sectors,
        format_func=lambda x: hk_sector_names[x],
        key="hk_sector_selector"
    )
    if selected_hk_sector:
        sector = selected_hk_sector
elif selected_universe == "Customised Portfolio_HK" or selected_universe == "Customised Portfolio_US":
    st.sidebar.subheader(f"{selected_universe}")
    
    if 'reset_tickers' not in st.session_state:
        st.session_state.reset_tickers = False
    
    portfolio_key = selected_universe.lower().replace(" ", "_")
    if f'{portfolio_key}_tickers' not in st.session_state or st.session_state.reset_tickers:
        portfolio_type = "HK" if selected_universe == "Customised Portfolio_HK" else "US"
        st.session_state[f'{portfolio_key}_tickers'] = get_preset_portfolio(portfolio_type)
    
    # Determine the number of tickers to display
    num_tickers = len(st.session_state[f'{portfolio_key}_tickers'])
    num_tickers = max(num_tickers, 30)  # Ensure at least 30 input fields
    
    # Calculate the number of columns needed
    num_columns = (num_tickers + 2) // 3  # Round up to the nearest multiple of 3
    # Create columns
    columns = st.sidebar.columns(3)
    
    custom_tickers = []
    for i in range(num_columns * 3):  # This ensures we always have a multiple of 3 input fields
        col_index = i % 3
        if i < num_tickers:
            ticker = columns[col_index].text_input(
                f"Stock {i+1}", 
                key=f"{portfolio_key}_stock_{i+1}", 
                value=st.session_state[f'{portfolio_key}_tickers'][i] if i < len(st.session_state[f'{portfolio_key}_tickers']) else ""
            )
        else:
            ticker = columns[col_index].text_input(
                f"Stock {i+1}", 
                key=f"{portfolio_key}_stock_{i+1}", 
                value=""
            )
        
        if ticker:
            if selected_universe == "Customised Portfolio_HK" and ticker.isdigit():
                processed_ticker = f"{ticker.zfill(4)}.HK"
            elif ticker.isalpha():
                processed_ticker = ticker.upper()
            else:
                processed_ticker = ticker
            custom_tickers.append(processed_ticker)
    
    st.session_state[f'{portfolio_key}_tickers'] = custom_tickers
    
    benchmark_options = ["^GSPC", "^HSI", "ACWI"]
    default_benchmark = "^HSI" if selected_universe == "Customised Portfolio_HK" else "^GSPC"
    
    custom_benchmark = st.sidebar.selectbox(
        "Select Benchmark",
        options=benchmark_options,
        index=benchmark_options.index(default_benchmark) if default_benchmark in benchmark_options else 0,
        key=f"{portfolio_key}_benchmark_selector"
    )
    
    # Update the Reset button
    if st.sidebar.button(f"Reset to Preset {selected_universe}"):
        portfolio_type = "HK" if selected_universe == "Customised Portfolio_HK" else "US"
        st.session_state[f'{portfolio_key}_tickers'] = get_preset_portfolio(portfolio_type)
        st.rerun()
    
    # Reset the flag after use
    if st.session_state.reset_tickers:
        st.session_state.reset_tickers = False

# Main content area
if selected_universe:
    # Debug information
    st.write("Debug info:")
    st.write(f"Selected universe: {selected_universe}")
    st.write(f"Sector: {sector}")
    st.write(f"Custom tickers: {custom_tickers}")
    st.write(f"Custom benchmark: {custom_benchmark}")
    
    # Manually add some default tickers if none are found
    if (selected_universe == "Customised Portfolio_HK" or selected_universe == "Customised Portfolio_US") and (not custom_tickers or len(custom_tickers) == 0):
        portfolio_type = "HK" if selected_universe == "Customised Portfolio_HK" else "US"
        if portfolio_type == "HK":
            custom_tickers = ["0005.HK", "0700.HK", "3988.HK", "0388.HK", "1398.HK"]
            custom_benchmark = "^HSI"
        else:
            custom_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
            custom_benchmark = "^GSPC"
        st.info(f"Using default tickers for {portfolio_type}: {custom_tickers}")
    
    # Get data
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
