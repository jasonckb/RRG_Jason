custom_tickers = []
    for i in range(15):
        if i % 3 == 0:
            ticker = col1.text_input(f"Stock {i+1}", key=f"{portfolio_key}_stock_{i+1}", value=st.session_state[f'{portfolio_key}_tickers'][i] if i < len(st.session_state[f'{portfolio_key}_tickers']) else "")
        elif i % 3 == 1:
            ticker = col2.text_input(f"Stock {i+1}", key=f"{portfolio_key}_stock_{i+1}", value=st.session_state[f'{portfolio_key}_tickers'][i] if i < len(st.session_state[f'{portfolio_key}_tickers']) else "")
        else:
            ticker = col3.text_input(f"Stock {i+1}", key=f"{portfolio_key}_stock_{i+1}", value=st.session_state[f'{portfolio_key}_tickers'][i] if i < len(st.session_state[f'{portfolio_key}_tickers']) else "")
        
        if ticker:
            if ticker.isalpha():
                processed_ticker = ticker.upper()
            elif ticker.isdigit():
                processed_ticker = f"{ticker.zfill(4)}.HK"
            else:
                processed_ticker = ticker
            custom_tickers.append(processed_ticker)
    
    st.session_state[f'{portfolio_key}_tickers'] = custom_tickers

    custom_benchmark = st.sidebar.selectbox(
        "Select Benchmark",
        options=["ACWI", "^GSPC", "^HSI"],
        key=f"{portfolio_key}_benchmark_selector"
    )

    # Add Reset button
    if st.sidebar.button(f"Reset to Preset {selected_universe}"):
        st.session_state[f'{portfolio_key}_tickers'] = get_preset_portfolio(selected_universe.split()[0])
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
