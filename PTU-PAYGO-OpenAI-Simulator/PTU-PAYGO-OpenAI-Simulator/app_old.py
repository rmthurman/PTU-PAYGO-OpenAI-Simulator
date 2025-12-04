"""
Streamlit app: Tokens per Minute Analyzer

Upload a CSV with the following columns (case-insensitive match, spaces allowed):
- timestamp [UTC]
- input tokens
- output tokens
- total tokens

For each minute, the app computes the total tokens (summing rows within the same minute) and then computes per-date statistics:
- max tokens per minute
- min tokens per minute
- median tokens per minute
- average tokens per minute

Usage:
    pip install -r requirements.txt
    streamlit run app.py

"""

from typing import Tuple, Dict

import pandas as pd
import streamlit as st
import math


EXPECTED_COLS = [
    "timestamp [utc]",
    "input tokens",
    "output tokens",
    "total tokens",
]


def find_columns(df: pd.DataFrame) -> Dict[str, str]:
    """Return a mapping from canonical names to actual dataframe column names.

    Canonical keys: 'timestamp', 'input', 'output', 'total'
    """
    cols = {c.lower(): c for c in df.columns}
    mapping = {}

    # timestamp column: prefer exact match, else any column containing 'timestamp'
    ts_candidates = [c for c_low, c in cols.items() if 'timestamp' in c_low]
    if ts_candidates:
        mapping['timestamp'] = ts_candidates[0]

    # token columns
    inp = [c for c_low, c in cols.items() if 'input' in c_low and 'token' in c_low]
    out = [c for c_low, c in cols.items() if 'output' in c_low and 'token' in c_low]
    tot = [c for c_low, c in cols.items() if 'total' in c_low and 'token' in c_low]

    if inp:
        mapping['input'] = inp[0]
    if out:
        mapping['output'] = out[0]
    if tot:
        mapping['total'] = tot[0]

    # Fallbacks: if total is missing but input+output exist, we'll compute total later
    return mapping


def prepare_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """Detect columns, parse timestamps, compute minute buckets and total tokens per row.

    Returns DataFrame with at least columns: 'minute' (datetime64[ns,UTC]) and 'total_tokens' (int)
    Also returns an error message (empty if ok).
    """
    mapping = find_columns(df)
    missing = []
    if 'timestamp' not in mapping:
        missing.append('timestamp')
    if 'total' not in mapping and not ('input' in mapping and 'output' in mapping):
        # we need either total tokens, or both input and output
        missing.append('total or (input and output)')

    if missing:
        return pd.DataFrame(), f"Missing required columns: {', '.join(missing)}"

    # parse timestamp
    try:
        ts_col = mapping['timestamp']
        # The dataset uses timestamps like: 8/18/2025, 12:06:23.290 AM
        # Normalize single-digit month/day to two digits (e.g. 8/1 -> 08/01) so a fixed strftime
        # format can be applied reliably.
        import re

        def _normalize(ts_value):
            if pd.isna(ts_value):
                return ts_value
            s = str(ts_value).strip()
            m = re.match(r"^(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4}),\s*(?P<rest>.*)$", s)
            if m:
                mm = m.group('m').zfill(2)
                dd = m.group('d').zfill(2)
                yyyy = m.group('y')
                rest = m.group('rest')
                return f"{mm}/{dd}/{yyyy}, {rest}"
            return s

        df[ts_col] = df[ts_col].apply(_normalize)

        fmt = "%m/%d/%Y, %I:%M:%S.%f %p"
        # Parse using the fixed format (hours in 12-hour clock with AM/PM and fractional seconds)
        df[ts_col] = pd.to_datetime(df[ts_col], format=fmt, utc=True, errors='raise')
    except Exception as e:
        hint = " Expected example: '8/18/2025, 12:06:23.290 AM'."
        return pd.DataFrame(), f"Failed to parse timestamps in column '{ts_col}' with assumed format '{fmt}': {e}. {hint}"

    # compute/normalize token columns
    # Always create canonical numeric columns if the source columns exist
    if 'input' in mapping:
        inp_col = mapping['input']
        try:
            df['input_tokens'] = pd.to_numeric(df[inp_col], errors='coerce').fillna(0).astype(int)
        except Exception as e:
            return pd.DataFrame(), f"Failed to coerce input tokens column '{inp_col}' to numeric: {e}"
    if 'output' in mapping:
        out_col = mapping['output']
        try:
            df['output_tokens'] = pd.to_numeric(df[out_col], errors='coerce').fillna(0).astype(int)
        except Exception as e:
            return pd.DataFrame(), f"Failed to coerce output tokens column '{out_col}' to numeric: {e}"

    # compute total tokens if missing or normalize existing total
    if 'total' not in mapping:
        # if input/output exist, total = input + output
        if 'input' in mapping and 'output' in mapping:
            try:
                df['total_tokens'] = df['input_tokens'] + df['output_tokens']
            except Exception as e:
                return pd.DataFrame(), f"Failed to compute total tokens from input/output columns: {e}"
        else:
            # should not reach here because of earlier missing check, but guard anyway
            return pd.DataFrame(), "Missing token columns to compute total tokens"
    else:
        tot_col = mapping['total']
        try:
            df['total_tokens'] = pd.to_numeric(df[tot_col], errors='coerce').fillna(0).astype(int)
        except Exception as e:
            return pd.DataFrame(), f"Failed to coerce total tokens column '{tot_col}' to numeric: {e}"
        # if input/output also exist, ensure they are present (already handled above)

    # minute timestamp (floor to minute)
    df['minute'] = df[mapping['timestamp']].dt.floor('min')

    # Keep needed columns. Preserve input/output if available so we can aggregate them separately.
    out_cols = ['minute', 'total_tokens']
    if 'input' in mapping:
        out_cols.insert(1, 'input_tokens')
    if 'output' in mapping and 'output_tokens' not in out_cols:
        # ensure output follows input in order
        out_cols.insert(2 if 'input' in mapping else 1, 'output_tokens')

    out_df = df[out_cols].copy()
    return out_df, ''


def compute_minute_aggregation(minutes_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate tokens per minute and attach date column.

    This now aggregates input, output and total tokens per minute when available and keeps
    separate columns for each. It also sets `tokens_per_minute` (the total) for backward compatibility.
    """
    # decide which token columns are available
    agg_cols = []
    if 'input_tokens' in minutes_df.columns:
        agg_cols.append('input_tokens')
    if 'output_tokens' in minutes_df.columns:
        agg_cols.append('output_tokens')
    # total_tokens should always be present at this point
    agg_cols.append('total_tokens')

    # Sum token counts for each minute
    minute_series = minutes_df.groupby('minute', as_index=False)[agg_cols].sum()

    # maintain a canonical 'tokens_per_minute' column for existing stats calculations
    if 'total_tokens' in minute_series.columns:
        minute_series['tokens_per_minute'] = minute_series['total_tokens']
    else:
        # fallback: sum input+output if total isn't available
        minute_series['tokens_per_minute'] = minute_series.get('input_tokens', 0) + minute_series.get('output_tokens', 0)

    minute_series['date'] = minute_series['minute'].dt.date
    return minute_series


def compute_stats_per_date(minute_series: pd.DataFrame) -> pd.DataFrame:
    """Compute max, min, median, avg tokens per minute for each date."""
    stats = minute_series.groupby('date', as_index=False)['tokens_per_minute'].agg([
        ('max_tokens_per_minute', 'max'),
        ('min_tokens_per_minute', 'min'),
        ('median_tokens_per_minute', 'median'),
        ('avg_tokens_per_minute', 'mean'),
    ])
    # The aggregation produces a MultiIndex for columns in older pandas, normalize to flat columns
    stats = stats.reset_index(drop=True)
    # Ensure avg is rounded to reasonable precision
    stats['avg_tokens_per_minute'] = stats['avg_tokens_per_minute'].round(2)
    # Convert median to int if it's integral
    stats['median_tokens_per_minute'] = stats['median_tokens_per_minute'].apply(lambda x: int(x) if pd.notna(x) and float(x).is_integer() else x)
    # Ensure numeric types
    numeric_cols = ['max_tokens_per_minute', 'min_tokens_per_minute']
    for c in numeric_cols:
        stats[c] = pd.to_numeric(stats[c], errors='coerce').fillna(0).astype(int)
    return stats


def main():
    st.set_page_config(page_title="Tokens per Minute Analyzer", layout="wide")
    st.title("Tokens per Minute Analyzer")

    st.markdown("""
    Upload a CSV with columns: `timestamp [UTC]`, `input tokens`, `output tokens`, `total tokens`.
    The app will aggregate tokens into minute buckets (UTC), compute tokens-per-minute, and then
    calculate per-date statistics (max, min, median, average tokens per minute).
    """)

    # PTU pricing selector (rich UI inspired by the AOAI sizing tool)
    st.subheader("PTU Pricing & Selection")
    default_ptu_prices = {
        'Monthly Reservation': 260.0,
        'Yearly Reservation': 221.0,
        'Hourly - Global ($1/Hour)': 730.0,
        'Hourly - Data Zone ($1.1/Hour)': 803.0,
        'Hourly - Regional ($2/Hour)': 1461.0,
        'Monthly Commitment (Deprecated)': 312.0,
    }

    # Two deployment preference selectors similar to the referenced UI
    left, right = st.columns(2)
    with left:
        deployment = st.selectbox("Select PTU Regional Deployment Type Preference", options=["Global", "Regional"], index=0)
        st.caption(f"Deployment preference: {deployment}. Your selection affects minimum PTU deployment size and pricing used in comparisons.")
    with right:
        paygo_deployment = st.selectbox("Select PayGO Regional Deployment Type Preference", options=["Global", "Regional"], index=0)
        st.caption(f"PayGO deployment preference: {paygo_deployment}. This selection determines the PayGO pricing used in comparisons.")

    # Pricing option (selectbox) — no experimental rerun required
    st.write("Choose a pricing scheme:")
    pricing_option = st.selectbox('Pricing option', options=list(default_ptu_prices.keys()), index=1)
    # Show card-like info (non-interactive) for reference
    opts = list(default_ptu_prices.items())
    def _chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
    for row in _chunks(opts, 3):
        cols = st.columns(len(row))
        for c, (name, price) in zip(cols, row):
            with c:
                st.markdown(f"**{name}**\n\n${price:.0f} USD/Month")

    # Prefill base price from selected option, allow manual override
    base_price_default = default_ptu_prices.get(pricing_option, 221.0)
    base_ptu_monthly = st.number_input("Base PTU Monthly Price (USD)", value=float(base_price_default), min_value=0.0, format="%.2f")

    # Discount and final price
    discount_pct = st.number_input("PTU Discount Percentage (%)", value=0.0, min_value=0.0, max_value=100.0, step=0.1, help="Enter e.g. 14.5 for 14.5% discount")
    final_ptu_price = round(base_ptu_monthly * (1 - discount_pct / 100.0), 2)
    # Show both base and final price side-by-side
    p1, p2 = st.columns(2)
    p1.metric("Base PTU Monthly Price (USD)", f"${base_ptu_monthly:.2f}")
    p2.metric("Final PTU Monthly Price (USD)", f"${final_ptu_price:.2f}")

    # Expose the final PTU price as a variable (could be used later for cost calculations)
    # (Stored in local variable `final_ptu_price`)

    # --- Model selection (Single Month Forecast style) ---
    st.subheader("Model Selection (Single Month Forecast)")
    import json
    import os

    @st.cache_data
    def load_local_json(path: str):
        try:
            if not os.path.exists(path):
                return None
            with open(path, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return None

    info_json = load_local_json('info.json')

    def _extract_model_groups(obj):
        groups = {'OpenAI': set(), 'Gemini': set(), 'Anthropic': set()}

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                if all(isinstance(x, str) for x in o) and len(o) > 5:
                    # heuristics: classify strings that contain provider names
                    for s in o:
                        if 'GPT' in s or s.lower().startswith('o') or 'o1' in s:
                            groups['OpenAI'].add(s)
                        elif 'Gemini' in s:
                            groups['Gemini'].add(s)
                        elif 'Claude' in s or 'Anthropic' in s:
                            groups['Anthropic'].add(s)
            # ignore other types

        walk(obj)
        # filter out empty groups
        return {k: sorted(v) for k, v in groups.items() if v}

    model_groups = _extract_model_groups(info_json) if info_json else {}

    if model_groups:
        provider = st.selectbox('Model provider', options=list(model_groups.keys()))
        models = model_groups.get(provider, [])
        if models:
            # default to 'GPT 4.1' when available
            try:
                default_idx = models.index('GPT 4.1')
            except ValueError:
                default_idx = 0
            selected_model = st.selectbox('Select model', options=models, index=default_idx)
        else:
            selected_model = st.text_input('Select model (no models found in snapshot)', value='')
    else:
        st.warning('No local model snapshot found (info.json). You can still enter model manually.')
        provider = st.selectbox('Model provider', options=['OpenAI', 'Gemini', 'Anthropic'])
        selected_model = st.text_input('Model name')

    # Try to heuristically extract model pricing from the info.json raw text
    def _extract_input_output_prices(path: str, model_list: list):
        prices = {}
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                txt = fh.read()
        except Exception:
            return prices

        import re
        for m in model_list:
            prices[m] = {'input': None, 'output': None}
            esc = re.escape(m)
            # look for input/prompt pricing near the model name
            pat_input = re.compile(rf"{esc}.{{0,200}}?(?:prompt|input|input tokens)[^$0-9\n\r]*\$\s*([0-9]+\.?[0-9]*)", re.IGNORECASE)
            pat_output = re.compile(rf"{esc}.{{0,200}}?(?:output|completion|generation|output tokens)[^$0-9\n\r]*\$\s*([0-9]+\.?[0-9]*)", re.IGNORECASE)
            m_in = pat_input.search(txt)
            m_out = pat_output.search(txt)
            # fallback: generic price near the model name
            pat_generic = re.compile(rf"{esc}.{{0,200}}?\$\s*([0-9]+\.?[0-9]*)", re.IGNORECASE)
            if m_in:
                try:
                    prices[m]['input'] = float(m_in.group(1))
                except Exception:
                    prices[m]['input'] = None
            if m_out:
                try:
                    prices[m]['output'] = float(m_out.group(1))
                except Exception:
                    prices[m]['output'] = None
            if (not prices[m]['input'] or not prices[m]['output']):
                # try generic extraction and assign to both if found
                mg = pat_generic.search(txt)
                if mg:
                    try:
                        val = float(mg.group(1))
                        if not prices[m]['input']:
                            prices[m]['input'] = val
                        if not prices[m]['output']:
                            prices[m]['output'] = val
                    except Exception:
                        pass
        return prices

    # Run extraction and prefill input/output pricing for the selected model
    extracted_io_prices = _extract_input_output_prices('info.json', model_groups.get(provider, [])) if info_json else {}
    # sensible defaults (USD per 1k tokens). These are used unless the snapshot provides explicit values.
    default_input_price = 0.0020
    default_output_price = 0.0080
    if selected_model and extracted_io_prices.get(selected_model):
        # prefer extracted values when available
        if extracted_io_prices[selected_model].get('input') is not None:
            default_input_price = extracted_io_prices[selected_model].get('input')
        if extracted_io_prices[selected_model].get('output') is not None:
            default_output_price = extracted_io_prices[selected_model].get('output')

    # Allow fine-grained edits; step set to 0.0001 so users can enter 0.0020 easily
    model_input_price_per_1k = st.number_input('Model input price per 1k tokens (USD)', value=float(default_input_price), min_value=0.0, step=0.0001, format='%.4f', help='Enter input/prompt price in USD per 1,000 tokens for this model if known')
    model_output_price_per_1k = st.number_input('Model output price per 1k tokens (USD)', value=float(default_output_price), min_value=0.0, step=0.0001, format='%.4f', help='Enter output/completion price in USD per 1,000 tokens for this model if known')
    
    # PTU TPM (tokens per minute) input
    ptu_tpm = st.number_input('PTU TPM (Tokens Per Minute per PTU)', value=3000, min_value=1, step=100, help='For GPT 4.1, this is typically 3000 tokens per minute per PTU')
    
    if default_input_price > 0 or default_output_price > 0:
        st.caption(f"Prefilled model IO prices from snapshot: input ${default_input_price:.4f}/1k, output ${default_output_price:.4f}/1k")

    # --- File upload and processing ---
    st.subheader("Upload and Analyze Token Data")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv", label_visibility="visible")
    if not uploaded_file:
        st.info("Upload a CSV file to begin analysis.")
        return

    # Progress indicator for file processing
    with st.spinner("Processing file..."):
        # 1. Read and prepare the data
        try:
            raw_df = pd.read_csv(uploaded_file, dtype=str)
        except Exception as e:
            st.error(f"Error reading CSV file: {e}")
            return

        # 2. Prepare dataframe (column detection, parsing, normalization)
        minutes_df, err = prepare_dataframe(raw_df)
        if err:
            st.error(err)
            return

        # 3. Aggregate tokens per minute
        minute_series = compute_minute_aggregation(minutes_df)

    st.success("File processed successfully!")

    # --- Display and download results ---
    st.subheader("Results")
    # Show raw minute-level data with tokens aggregated
    with st.expander("Show minute-level data", expanded=False):
        st.write("Total rows:", len(minute_series))
        st.dataframe(minute_series, height=300)

    # Per-date statistics
    stats = compute_stats_per_date(minute_series)
    st.write("Total dates:", len(stats))
    st.dataframe(stats, height=300)

    # Helper to create CSV download links
    import base64
    def create_download_link(df: pd.DataFrame, file_name: str, label: str):
        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="{file_name}">{label}</a>'
        return href

    # Minute-level data download
    st.markdown(create_download_link(minute_series, "minute_level_tokens.csv", "Download minute-level data (CSV)"), unsafe_allow_html=True)
    # Stats download (if applicable)
    if not stats.empty:
        st.markdown(create_download_link(stats, "daily_stats_tokens.csv", "Download per-date stats (CSV)"), unsafe_allow_html=True)

    # --- Optional: Model cost estimation ---
    st.subheader("Optional: Model Cost Estimation")
    if st.checkbox("Enable model cost estimation", value=False):
        # Ensure minute-level data is available
        if 'minute_series' not in locals() or minute_series.empty:
            st.error("No minute-level data available. Upload a CSV first to enable cost estimation.")
        else:
            # PTU count range to evaluate
            col1, col2 = st.columns(2)
            with col1:
                min_ptu_count = st.number_input('Min PTU count', min_value=15, max_value=500, value=15, step=5, help='Starting PTU count (minimum 15)')
            with col2:
                max_ptu_count = st.number_input('Max PTU count', min_value=15, max_value=500, value=50, step=5, help='Maximum PTU count to evaluate')
            
            # Ensure min <= max
            if min_ptu_count > max_ptu_count:
                st.error("Minimum PTU count cannot be greater than maximum PTU count")
                return

            # Check if we have input/output token data
            has_io = ('input_tokens' in minute_series.columns and 'output_tokens' in minute_series.columns)
            if not has_io:
                st.error("Input/output token columns not found. This calculation requires separate input and output token data.")
                return

            # Calculate the token ratio weight based on pricing
            # If input costs $0.002 and output costs $0.008, then 1 output token = 4x input token in PTU capacity
            input_price = float(model_input_price_per_1k)
            output_price = float(model_output_price_per_1k)
            
            if input_price <= 0 or output_price <= 0:
                st.error("Both input and output prices must be greater than 0 for PTU calculations.")
                return
                
            # Price ratio: how much more expensive is output vs input in PTU terms
            output_weight = output_price / input_price
            st.info(f"Price ratio: 1 output token = {output_weight:.2f}x input token in PTU capacity")
            
            # Get the original request-level data for simulation
            request_data = minutes_df.copy()  # This has individual requests with timestamps
            request_data = request_data.sort_values('minute')  # Sort by time
            
            # Find peak tokens per minute for PTU sizing
            peak_tpm = minute_series['tokens_per_minute'].max()
            st.info(f"Peak actual TPM: {peak_tpm:,.0f} tokens")
            st.info(f"Total requests in dataset: {len(request_data):,}")
            
            # Calculate dataset duration for cost averaging
            start_time = minute_series['minute'].min()
            end_time = minute_series['minute'].max()
            dataset_hours = (end_time - start_time).total_seconds() / 3600
            dataset_days = dataset_hours / 24
            st.info(f"Dataset duration: {dataset_days:.1f} days ({dataset_hours:.1f} hours)")
            
            rows = []
            
            # Calculate total configurations to simulate (0, 15, 20, 25, 30...)
            ptu_counts = [0] + list(range(min_ptu_count, max_ptu_count + 1, 5))
            total_configs = len(ptu_counts)
            
            st.info(f"Will simulate {total_configs} PTU configurations: 0 (PAYGO-only), {min_ptu_count} to {max_ptu_count} PTUs (step 5)")
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, num_ptus in enumerate(ptu_counts):
                # Update progress bar and status
                progress = (i + 1) / total_configs
                progress_bar.progress(progress)
                ptu_capacity_tpm = num_ptus * ptu_tpm
                
                if num_ptus == 0:
                    status_text.text(f"Calculating PAYGO-only (0 PTUs) - Config {i+1}/{total_configs}")
                else:
                    status_text.text(f"Simulating {num_ptus} PTUs ({ptu_capacity_tpm:,} TPM) - Config {i+1}/{total_configs} - Processing {len(request_data):,} requests...")
                
                # Initialize counters
                ptu_input_tokens = 0
                ptu_output_tokens = 0
                paygo_input_tokens = 0
                paygo_output_tokens = 0
                
                if num_ptus == 0:
                    # PAYGO-only: simple sum of all tokens
                    paygo_input_tokens = request_data['input_tokens'].sum()
                    paygo_output_tokens = request_data['output_tokens'].sum()
                    # No PTU tokens
                    ptu_input_tokens = 0
                    ptu_output_tokens = 0
                else:
                    # Simulate request by request for PTU configurations
                    # Track PTU capacity per minute (resets each minute)
                    current_minute = None
                    remaining_ptu_capacity = 0
                    
                    # For large datasets, show request processing progress too
                    total_requests = len(request_data)
                    request_batch_size = max(1, total_requests // 20)  # Update every 5% of requests
                    
                    for req_idx, (_, request) in enumerate(request_data.iterrows()):
                        # Update detailed progress for large datasets
                        if req_idx % request_batch_size == 0 and total_requests > 1000:
                            request_progress = req_idx / total_requests
                            detailed_status = f"{num_ptus} PTUs ({ptu_capacity_tpm:,} TPM) - Config {i+1}/{total_configs} - Request {req_idx:,}/{total_requests:,} ({request_progress:.1%})"
                            status_text.text(detailed_status)
                        
                        request_minute = request['minute']
                        request_input = request['input_tokens']
                        request_output = request['output_tokens']
                        
                        # Reset PTU capacity at the start of each new minute
                        if current_minute != request_minute:
                            current_minute = request_minute
                            remaining_ptu_capacity = ptu_capacity_tpm
                        
                        # Calculate PTU capacity needed for this request
                        request_ptu_demand = request_input + (request_output * output_weight)
                        
                        if request_ptu_demand <= remaining_ptu_capacity:
                            # PTUs can handle this entire request
                            ptu_input_tokens += request_input
                            ptu_output_tokens += request_output
                            remaining_ptu_capacity -= request_ptu_demand
                        else:
                            # Partial or full spillover to PAYGO
                            if remaining_ptu_capacity > 0:
                                # PTUs can handle part of the request
                                # Determine how much based on maintaining input/output ratio
                                total_request_tokens = request_input + request_output
                                if total_request_tokens > 0:
                                    input_ratio = request_input / total_request_tokens
                                    output_ratio = request_output / total_request_tokens
                                    
                                    # Solve: ptu_tokens * (input_ratio + output_ratio * output_weight) = remaining_capacity
                                    denominator = input_ratio + output_ratio * output_weight
                                    if denominator > 0:
                                        ptu_tokens_this_request = remaining_ptu_capacity / denominator
                                        ptu_tokens_this_request = min(ptu_tokens_this_request, total_request_tokens)
                                        
                                        request_ptu_input = ptu_tokens_this_request * input_ratio
                                        request_ptu_output = ptu_tokens_this_request * output_ratio
                                        
                                        ptu_input_tokens += request_ptu_input
                                        ptu_output_tokens += request_ptu_output
                                        
                                        # Spillover to PAYGO
                                        paygo_input_tokens += request_input - request_ptu_input
                                        paygo_output_tokens += request_output - request_ptu_output
                                        
                                        remaining_ptu_capacity = 0  # Used up all PTU capacity
                                    else:
                                        # All goes to PAYGO
                                        paygo_input_tokens += request_input
                                        paygo_output_tokens += request_output
                                else:
                                    # No tokens in this request, skip
                                    pass
                            else:
                                # No PTU capacity left, all goes to PAYGO
                                paygo_input_tokens += request_input
                                paygo_output_tokens += request_output
                
                # Calculate costs
                ptu_monthly_cost = num_ptus * final_ptu_price
                
                paygo_input_cost = (paygo_input_tokens / 1000.0) * input_price
                paygo_output_cost = (paygo_output_tokens / 1000.0) * output_price
                paygo_total_cost = paygo_input_cost + paygo_output_cost
                
                # Annualize PAYGO cost (scale from dataset period to full year)
                if dataset_days > 0:
                    paygo_annual_cost = paygo_total_cost * (365.25 / dataset_days)
                    paygo_monthly_cost = paygo_annual_cost / 12
                else:
                    paygo_monthly_cost = 0
                
                total_monthly_cost = ptu_monthly_cost + paygo_monthly_cost
                
                # Add to results
                rows.append({
                    'num_ptus': num_ptus,
                    'ptu_capacity_tpm': ptu_capacity_tpm,
                    'ptu_monthly_cost': ptu_monthly_cost,
                    'ptu_input_tokens': int(ptu_input_tokens),
                    'ptu_output_tokens': int(ptu_output_tokens),
                    'paygo_input_tokens': int(paygo_input_tokens),
                    'paygo_output_tokens': int(paygo_output_tokens),
                    'paygo_dataset_cost': paygo_total_cost,
                    'paygo_monthly_cost': paygo_monthly_cost,
                    'total_monthly_cost': total_monthly_cost,
                    'utilization_pct': min(100, (peak_tpm / ptu_capacity_tpm) * 100) if ptu_capacity_tpm > 0 else 0
                })
            
            # Complete the progress bar
            progress_bar.progress(1.0)
            status_text.text(f"✅ Simulation complete! Analyzed {total_configs} PTU configurations with {len(request_data):,} requests.")
            
            sweep_df = pd.DataFrame(rows)
            
            # Add formatted columns
            sweep_df['ptu_monthly_cost_usd'] = sweep_df['ptu_monthly_cost'].apply(lambda x: f"${x:,.2f}")
            sweep_df['paygo_monthly_cost_usd'] = sweep_df['paygo_monthly_cost'].apply(lambda x: f"${x:,.2f}")
            sweep_df['total_monthly_cost_usd'] = sweep_df['total_monthly_cost'].apply(lambda x: f"${x:,.2f}")
            sweep_df['utilization_pct'] = sweep_df['utilization_pct'].apply(lambda x: f"{x:.1f}%")
            
            st.subheader('PTU Analysis Results')
            
            # Show key metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Peak TPM", f"{peak_tpm:,.0f}", help="Peak tokens per minute in dataset")
            with col2:
                total_input = minute_series['input_tokens'].sum()
                st.metric("Total input tokens", f"{total_input:,}")
            with col3:
                total_output = minute_series['output_tokens'].sum()
                st.metric("Total output tokens", f"{total_output:,}")
            
            # Display results table
            display_cols = ['num_ptus', 'ptu_capacity_tpm', 'ptu_input_tokens', 'ptu_output_tokens', 
                          'paygo_input_tokens', 'paygo_output_tokens', 'ptu_monthly_cost_usd', 
                          'paygo_monthly_cost_usd', 'total_monthly_cost_usd', 'utilization_pct']
            
            st.dataframe(sweep_df[display_cols], height=400)
            
            # Charts
            st.subheader('Cost Analysis Charts')
            
            # Cost chart by PTU count
            cost_chart_df = sweep_df[['num_ptus', 'ptu_monthly_cost', 'paygo_monthly_cost']].set_index('num_ptus')
            st.line_chart(cost_chart_df)
            
            # Token distribution chart by PTU count
            token_chart_df = pd.DataFrame({
                'PTU Input Tokens': sweep_df['ptu_input_tokens'],
                'PTU Output Tokens': sweep_df['ptu_output_tokens'], 
                'PAYGO Input Tokens': sweep_df['paygo_input_tokens'],
                'PAYGO Output Tokens': sweep_df['paygo_output_tokens']
            }, index=sweep_df['num_ptus'])
            st.bar_chart(token_chart_df)
            
            # Download link
            st.markdown(create_download_link(sweep_df, 'ptu_analysis_results.csv', 'Download PTU analysis results (CSV)'), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
