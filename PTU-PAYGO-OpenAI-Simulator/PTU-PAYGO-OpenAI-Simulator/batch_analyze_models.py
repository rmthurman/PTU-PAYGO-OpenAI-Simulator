"""
Batch PTU Analysis for Multiple Models

This script reads the CSV with model data and automatically runs PTU analysis
for each model separately, generating individual reports and recommendations.

Usage:
    python3 batch_analyze_models.py --csv analysis_output/nvstrgitentint_complete_analysis_with_models.csv
"""

import argparse
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime
from data_processing import prepare_dataframe, compute_minute_aggregation
from ptu_calculations import run_ptu_analysis, format_analysis_results
from pricing import load_pricing_data
from utils import get_dataset_duration_days


def analyze_single_model(model_name, model_df, output_dir, pricing_config):
    """Analyze a single model and generate report."""
    
    print(f"\n{'='*80}")
    print(f"Analyzing Model: {model_name}")
    print(f"{'='*80}")
    print(f"Requests: {len(model_df):,}")
    
    # Prepare dataframe (remove model columns for processing)
    df_for_analysis = model_df[['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens']].copy()
    
    # Compute minute aggregations
    minute_series = compute_minute_aggregation(df_for_analysis)
    
    if minute_series.empty:
        print(f"⚠️  No valid data for {model_name}")
        return None
    
    # Calculate dataset metrics
    dataset_days = get_dataset_duration_days(df_for_analysis, 'timestamp [UTC]')
    total_input = minute_series['input_tokens'].sum()
    total_output = minute_series['output_tokens'].sum()
    peak_tpm = minute_series['tokens_per_minute'].max()
    avg_tpm = minute_series['tokens_per_minute'].mean()
    
    print(f"Dataset Duration: {dataset_days:.1f} days")
    print(f"Total Input Tokens: {total_input:,}")
    print(f"Total Output Tokens: {total_output:,}")
    print(f"Peak TPM: {peak_tpm:,.0f}")
    print(f"Average TPM: {avg_tpm:,.0f}")
    
    # Get pricing for this model
    input_price = pricing_config.get('input_price', 0.01)
    output_price = pricing_config.get('output_price', 0.03)
    ptu_capacity_tpm = pricing_config.get('ptu_capacity_tpm', 3000)
    final_ptu_price = pricing_config.get('final_ptu_price', 221.0)
    min_ptu = pricing_config.get('min_ptu_count', 15)
    max_ptu = pricing_config.get('max_ptu_count', 100)
    
    # Calculate output weight
    output_weight = output_price / input_price if input_price > 0 else 1.0
    
    # Run PTU analysis
    print(f"Running PTU analysis ({min_ptu}-{max_ptu} PTUs)...")
    
    results_df = run_ptu_analysis(
        request_data=df_for_analysis,
        minute_series=minute_series,
        min_ptu_count=min_ptu,
        max_ptu_count=max_ptu,
        ptu_capacity_tpm=ptu_capacity_tpm,
        final_ptu_price=final_ptu_price,
        input_price=input_price,
        output_price=output_price,
        dataset_days=dataset_days,
        output_weight=output_weight
    )
    
    formatted_df = format_analysis_results(results_df)
    
    # Find optimal configuration
    paygo_only_cost = results_df[results_df['num_ptus'] == 0]['total_monthly_cost'].iloc[0]
    ptu_configs = results_df[results_df['num_ptus'] > 0].copy()
    
    if not ptu_configs.empty:
        ptu_configs['cost_diff'] = ptu_configs['total_monthly_cost'] - paygo_only_cost
        above_paygo = ptu_configs[ptu_configs['cost_diff'] >= 0]
        
        if not above_paygo.empty:
            closest_idx = above_paygo['cost_diff'].idxmin()
        else:
            closest_idx = ptu_configs['cost_diff'].abs().idxmin()
        
        optimal_config = results_df.loc[closest_idx]
        optimal_formatted = formatted_df.loc[closest_idx]
    else:
        optimal_config = None
        optimal_formatted = None
    
    # Save results
    model_safe_name = model_name.replace('/', '_').replace(' ', '_')
    csv_path = output_dir / f"{model_safe_name}_ptu_analysis.csv"
    formatted_df.to_csv(csv_path, index=False)
    print(f"✅ Saved: {csv_path}")
    
    # Generate report
    report_path = output_dir / f"{model_safe_name}_ptu_report.txt"
    with open(report_path, 'w') as f:
        f.write(f"{'='*80}\n")
        f.write(f"PTU ANALYSIS REPORT: {model_name}\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Dataset Duration: {dataset_days:.1f} days\n\n")
        
        f.write(f"{'='*80}\n")
        f.write(f"TRAFFIC STATISTICS\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"Total Requests: {len(model_df):,}\n")
        f.write(f"Total Input Tokens: {total_input:,}\n")
        f.write(f"Total Output Tokens: {total_output:,}\n")
        f.write(f"Peak TPM: {peak_tpm:,.0f}\n")
        f.write(f"Average TPM: {avg_tpm:,.0f}\n")
        f.write(f"Median TPM: {minute_series['tokens_per_minute'].median():,.0f}\n\n")
        
        f.write(f"{'='*80}\n")
        f.write(f"PRICING CONFIGURATION\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"Input Price: ${input_price:.4f} per 1K tokens\n")
        f.write(f"Output Price: ${output_price:.4f} per 1K tokens\n")
        f.write(f"PTU Monthly Price: ${final_ptu_price:.2f}\n")
        f.write(f"PTU Capacity: {ptu_capacity_tpm:,} TPM\n\n")
        
        f.write(f"{'='*80}\n")
        f.write(f"PAYGO COST\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"Monthly Cost (PAYGO only): ${paygo_only_cost:,.2f}\n\n")
        
        if optimal_config is not None:
            f.write(f"{'='*80}\n")
            f.write(f"RECOMMENDED PTU CONFIGURATION\n")
            f.write(f"{'='*80}\n\n")
            f.write(f"Recommended PTUs: {optimal_config['num_ptus']:.0f}\n")
            f.write(f"PTU Capacity: {optimal_config['ptu_capacity_tpm']:,.0f} TPM\n")
            f.write(f"PTU Monthly Cost: ${optimal_config['ptu_monthly_cost']:,.2f}\n")
            f.write(f"PAYGO Monthly Cost: ${optimal_config['paygo_monthly_cost']:,.2f}\n")
            f.write(f"Total Monthly Cost: ${optimal_config['total_monthly_cost']:,.2f}\n")
            f.write(f"Tokens via PTU: {optimal_formatted['ptu_total_pct']:.1f}%\n")
            f.write(f"Utilization: {optimal_formatted['utilization_pct']:.1f}%\n\n")
            
            cost_diff = optimal_config['total_monthly_cost'] - paygo_only_cost
            cost_diff_pct = (cost_diff / paygo_only_cost * 100) if paygo_only_cost > 0 else 0
            
            if cost_diff > 0:
                f.write(f"Cost vs PAYGO: +${cost_diff:,.2f} (+{cost_diff_pct:.1f}%)\n")
                f.write(f"RECOMMENDATION: PTU provides {optimal_formatted['ptu_total_pct']:.1f}% traffic optimization\n")
                f.write(f"for {cost_diff_pct:.1f}% additional cost. Consider if reliability/consistency is important.\n")
            else:
                f.write(f"Cost vs PAYGO: -${abs(cost_diff):,.2f} ({cost_diff_pct:.1f}%)\n")
                f.write(f"RECOMMENDATION: PTU is cost-effective! Saves ${abs(cost_diff):,.2f}/month\n")
                f.write(f"while optimizing {optimal_formatted['ptu_total_pct']:.1f}% of traffic.\n")
        
        f.write(f"\n{'='*80}\n")
        f.write(f"NOTE: Token counts are ESTIMATED (±25-30% accuracy)\n")
        f.write(f"Use 1.3-1.5x safety buffer for production PTU planning\n")
        f.write(f"{'='*80}\n")
    
    print(f"✅ Saved: {report_path}")
    
    return {
        'model': model_name,
        'requests': len(model_df),
        'dataset_days': dataset_days,
        'peak_tpm': peak_tpm,
        'avg_tpm': avg_tpm,
        'paygo_cost': paygo_only_cost,
        'recommended_ptus': optimal_config['num_ptus'] if optimal_config else 0,
        'recommended_cost': optimal_config['total_monthly_cost'] if optimal_config else paygo_only_cost,
        'cost_diff': (optimal_config['total_monthly_cost'] - paygo_only_cost) if optimal_config else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Batch PTU analysis for multiple models")
    parser.add_argument('--csv', required=True, help='Path to CSV with model data')
    parser.add_argument('--output-dir', default='./model_analysis', help='Output directory')
    parser.add_argument('--min-requests', type=int, default=1000, help='Minimum requests to analyze model')
    parser.add_argument('--ptu-price', type=float, default=221.0, help='PTU monthly price')
    parser.add_argument('--ptu-capacity', type=int, default=3000, help='PTU capacity (TPM)')
    parser.add_argument('--min-ptu', type=int, default=15, help='Min PTU count')
    parser.add_argument('--max-ptu', type=int, default=100, help='Max PTU count')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"BATCH PTU ANALYSIS")
    print(f"{'='*80}")
    print(f"CSV: {args.csv}")
    print(f"Output: {output_dir}")
    print(f"Min Requests: {args.min_requests:,}")
    print(f"{'='*80}\n")
    
    # Load CSV
    print("Loading CSV...")
    df = pd.read_csv(args.csv, dtype={'model': str, 'model_version': str, 'result_code': str})
    print(f"Loaded {len(df):,} rows")
    
    # Filter successful requests only
    df = df[df['result_code'] == '200'].copy()
    print(f"Successful requests (200): {len(df):,}\n")
    
    # Group by model
    model_groups = df.groupby('model')
    print(f"Found {len(model_groups)} unique models\n")
    
    # Load pricing data
    model_list, model_prices = load_pricing_data()
    
    # Configure pricing (use default GPT-4 pricing if not found)
    default_input_price = 0.01
    default_output_price = 0.03
    
    pricing_config = {
        'ptu_capacity_tpm': args.ptu_capacity,
        'final_ptu_price': args.ptu_price,
        'min_ptu_count': args.min_ptu,
        'max_ptu_count': args.max_ptu,
        'input_price': default_input_price,
        'output_price': default_output_price,
    }
    
    # Analyze each model
    results = []
    for model_name, model_df in model_groups:
        if len(model_df) < args.min_requests:
            print(f"⏭️  Skipping {model_name}: only {len(model_df):,} requests (< {args.min_requests:,})")
            continue
        
        try:
            result = analyze_single_model(model_name, model_df, output_dir, pricing_config)
            if result:
                results.append(result)
        except Exception as e:
            print(f"❌ Error analyzing {model_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Generate summary report
    if results:
        summary_path = output_dir / "SUMMARY_all_models.txt"
        with open(summary_path, 'w') as f:
            f.write(f"{'='*80}\n")
            f.write(f"BATCH PTU ANALYSIS SUMMARY\n")
            f.write(f"{'='*80}\n\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Models Analyzed: {len(results)}\n\n")
            
            # Sort by requests
            results.sort(key=lambda x: x['requests'], reverse=True)
            
            f.write(f"{'='*80}\n")
            f.write(f"MODELS BY REQUEST VOLUME\n")
            f.write(f"{'='*80}\n\n")
            
            total_paygo = 0
            total_recommended = 0
            
            for r in results:
                f.write(f"{r['model']}\n")
                f.write(f"  Requests: {r['requests']:,}\n")
                f.write(f"  Peak TPM: {r['peak_tpm']:,.0f}\n")
                f.write(f"  PAYGO Cost: ${r['paygo_cost']:,.2f}/month\n")
                f.write(f"  Recommended PTUs: {r['recommended_ptus']:.0f}\n")
                f.write(f"  Recommended Cost: ${r['recommended_cost']:,.2f}/month\n")
                
                cost_diff = r['cost_diff']
                if cost_diff > 0:
                    f.write(f"  Cost Difference: +${cost_diff:,.2f} (+{cost_diff/r['paygo_cost']*100:.1f}%)\n")
                else:
                    f.write(f"  Cost Difference: -${abs(cost_diff):,.2f} ({cost_diff/r['paygo_cost']*100:.1f}%)\n")
                
                f.write("\n")
                
                total_paygo += r['paygo_cost']
                total_recommended += r['recommended_cost']
            
            f.write(f"{'='*80}\n")
            f.write(f"TOTAL COSTS\n")
            f.write(f"{'='*80}\n\n")
            f.write(f"Total PAYGO Cost: ${total_paygo:,.2f}/month\n")
            f.write(f"Total with PTU Recommendations: ${total_recommended:,.2f}/month\n")
            f.write(f"Difference: ${total_recommended - total_paygo:+,.2f} ({(total_recommended - total_paygo)/total_paygo*100:+.1f}%)\n")
        
        print(f"\n{'='*80}")
        print(f"BATCH ANALYSIS COMPLETE")
        print(f"{'='*80}")
        print(f"Models Analyzed: {len(results)}")
        print(f"Output Directory: {output_dir}")
        print(f"Summary Report: {summary_path}")
        print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
