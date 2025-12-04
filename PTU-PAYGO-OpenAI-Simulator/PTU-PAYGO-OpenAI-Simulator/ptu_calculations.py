"""
PTU (Provisioned Throughput Units) calculation module.

Handles PTU capacity simulation, cost calculations, and pricing logic
for comparing PTU vs PAYGO pricing models.
"""

import pandas as pd
from typing import List, Dict, Any


def simulate_ptu_usage(request_data: pd.DataFrame, num_ptus: int, ptu_capacity_tpm: int, 
                      output_weight: float) -> Dict[str, float]:
    """Simulate PTU usage for a given configuration.
    
    Args:
        request_data: DataFrame with columns ['minute', 'input_tokens', 'output_tokens']
        num_ptus: Number of PTUs (0 for PAYGO-only)
        ptu_capacity_tpm: PTU capacity in tokens per minute
        output_weight: Weight factor for output tokens in PTU capacity calculation
        
    Returns:
        Dictionary with PTU and PAYGO token usage
    """
    if num_ptus == 0:
        # PAYGO-only: simple sum of all tokens
        return {
            'ptu_input_tokens': 0,
            'ptu_output_tokens': 0,
            'paygo_input_tokens': request_data['input_tokens'].sum(),
            'paygo_output_tokens': request_data['output_tokens'].sum()
        }
    
    # PTU simulation - process request by request
    ptu_input_tokens = 0
    ptu_output_tokens = 0
    paygo_input_tokens = 0
    paygo_output_tokens = 0
    
    # Track PTU capacity per minute (resets each minute)
    current_minute = None
    remaining_ptu_capacity = 0
    
    for _, request in request_data.iterrows():
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
    
    return {
        'ptu_input_tokens': ptu_input_tokens,
        'ptu_output_tokens': ptu_output_tokens,
        'paygo_input_tokens': paygo_input_tokens,
        'paygo_output_tokens': paygo_output_tokens
    }


def calculate_costs(ptu_tokens: Dict[str, float], num_ptus: int, ptu_price: float,
                   input_price: float, output_price: float, dataset_days: float) -> Dict[str, float]:
    """Calculate PTU and PAYGO costs.
    
    Args:
        ptu_tokens: Dictionary with token usage from simulate_ptu_usage
        num_ptus: Number of PTUs
        ptu_price: Price per PTU per month
        input_price: PAYGO price per 1K input tokens
        output_price: PAYGO price per 1K output tokens  
        dataset_days: Number of days in the dataset for annualization
        
    Returns:
        Dictionary with cost breakdown
    """
    # PTU monthly cost
    ptu_monthly_cost = num_ptus * ptu_price
    
    # PAYGO costs
    paygo_input_cost = (ptu_tokens['paygo_input_tokens'] / 1000.0) * input_price
    paygo_output_cost = (ptu_tokens['paygo_output_tokens'] / 1000.0) * output_price
    paygo_total_cost = paygo_input_cost + paygo_output_cost
    
    # Annualize PAYGO cost (scale from dataset period to full year)
    if dataset_days > 0:
        paygo_annual_cost = paygo_total_cost * (365.25 / dataset_days)
        paygo_monthly_cost = paygo_annual_cost / 12
    else:
        paygo_monthly_cost = 0
    
    total_monthly_cost = ptu_monthly_cost + paygo_monthly_cost
    
    return {
        'ptu_monthly_cost': ptu_monthly_cost,
        'paygo_dataset_cost': paygo_total_cost,
        'paygo_monthly_cost': paygo_monthly_cost,
        'total_monthly_cost': total_monthly_cost
    }


def run_ptu_analysis(request_data: pd.DataFrame, minute_series: pd.DataFrame,
                    min_ptu_count: int, max_ptu_count: int, ptu_capacity_tpm: int,
                    final_ptu_price: float, input_price: float, output_price: float,
                    dataset_days: float, output_weight: float,
                    progress_callback=None, status_callback=None) -> pd.DataFrame:
    """Run complete PTU analysis across PTU count range.
    
    Args:
        request_data: DataFrame with individual requests
        minute_series: DataFrame with minute-level aggregations  
        min_ptu_count: Minimum PTU count to analyze
        max_ptu_count: Maximum PTU count to analyze
        ptu_capacity_tpm: PTU capacity in tokens per minute
        final_ptu_price: Price per PTU per month
        input_price: PAYGO price per 1K input tokens
        output_price: PAYGO price per 1K output tokens
        dataset_days: Number of days in dataset
        output_weight: Weight for output tokens in PTU capacity
        progress_callback: Optional callback for progress updates
        status_callback: Optional callback for status updates
        
    Returns:
        DataFrame with analysis results for each PTU configuration
    """
    # Generate PTU count range: [0] + [15, 20, 25, ...]
    ptu_counts = [0] + list(range(15, max_ptu_count + 1, 5))
    total_configs = len(ptu_counts)
    
    rows = []
    
    for i, num_ptus in enumerate(ptu_counts):
        # Calculate total PTU capacity (like original app)
        total_ptu_capacity_tpm = num_ptus * ptu_capacity_tpm
        
        # Update progress
        if progress_callback:
            progress = (i + 0.5) / total_configs
            progress_callback(progress)
        
        if status_callback:
            if num_ptus == 0:
                status = f"Analyzing PAYGO-only (0 PTUs) - Config {i+1}/{total_configs}"
            else:
                status = f"Simulating {num_ptus} PTUs ({total_ptu_capacity_tpm:,} TPM) - Config {i+1}/{total_configs}"
            status_callback(status)
        
        # Simulate PTU usage (pass total capacity)
        ptu_tokens = simulate_ptu_usage(request_data, num_ptus, total_ptu_capacity_tpm, output_weight)
        
        # Calculate costs
        costs = calculate_costs(ptu_tokens, num_ptus, final_ptu_price, 
                              input_price, output_price, dataset_days)
        
        # Calculate utilization as average of per-minute utilizations
        if total_ptu_capacity_tpm > 0 and not minute_series.empty:
            minute_utilizations = (minute_series['tokens_per_minute'] / total_ptu_capacity_tpm * 100).clip(0, 100)
            utilization_pct = minute_utilizations.mean()
        else:
            utilization_pct = 0
        
        # Combine results
        row = {
            'num_ptus': num_ptus,
            'ptu_capacity_tpm': total_ptu_capacity_tpm,  # Show total capacity like original
            'utilization_pct': utilization_pct,
            **ptu_tokens,
            **costs
        }
        rows.append(row)
    
    # Final progress update
    if progress_callback:
        progress_callback(1.0)
    
    if status_callback:
        total_requests = len(request_data)
        status_callback(f"✅ Simulation complete! Analyzed {total_configs} PTU configurations with {total_requests:,} requests.")
    
    return pd.DataFrame(rows)


def format_analysis_results(sweep_df: pd.DataFrame) -> pd.DataFrame:
    """Add formatted currency and percentage columns to analysis results.
    
    Args:
        sweep_df: DataFrame from run_ptu_analysis
        
    Returns:
        DataFrame with additional formatted columns
    """
    result_df = sweep_df.copy()
    
    # Calculate token percentages handled by PTUs
    result_df['total_input'] = result_df['ptu_input_tokens'] + result_df['paygo_input_tokens']
    result_df['total_output'] = result_df['ptu_output_tokens'] + result_df['paygo_output_tokens']
    result_df['total_tokens'] = result_df['total_input'] + result_df['total_output']
    
    # Percentage of tokens handled by PTUs
    result_df['ptu_input_pct'] = (result_df['ptu_input_tokens'] / result_df['total_input'] * 100).fillna(0)
    result_df['ptu_output_pct'] = (result_df['ptu_output_tokens'] / result_df['total_output'] * 100).fillna(0)
    result_df['ptu_total_pct'] = ((result_df['ptu_input_tokens'] + result_df['ptu_output_tokens']) / result_df['total_tokens'] * 100).fillna(0)
    
    # Add formatted columns with US number formatting
    result_df['ptu_capacity_tpm_formatted'] = result_df['ptu_capacity_tpm'].apply(lambda x: f"{x:,.0f}")
    result_df['ptu_input_tokens_formatted'] = result_df['ptu_input_tokens'].apply(lambda x: f"{x:,.0f}")
    result_df['ptu_output_tokens_formatted'] = result_df['ptu_output_tokens'].apply(lambda x: f"{x:,.0f}")
    result_df['paygo_input_tokens_formatted'] = result_df['paygo_input_tokens'].apply(lambda x: f"{x:,.0f}")
    result_df['paygo_output_tokens_formatted'] = result_df['paygo_output_tokens'].apply(lambda x: f"{x:,.0f}")
    result_df['ptu_monthly_cost_usd'] = result_df['ptu_monthly_cost'].apply(lambda x: f"${x:,.2f}")
    result_df['paygo_monthly_cost_usd'] = result_df['paygo_monthly_cost'].apply(lambda x: f"${x:,.2f}")
    result_df['total_monthly_cost_usd'] = result_df['total_monthly_cost'].apply(lambda x: f"${x:,.2f}")
    result_df['utilization_pct_formatted'] = result_df['utilization_pct'].apply(lambda x: f"{x:.1f}%")
    result_df['ptu_total_pct_formatted'] = result_df['ptu_total_pct'].apply(lambda x: f"{x:.1f}%")
    
    return result_df