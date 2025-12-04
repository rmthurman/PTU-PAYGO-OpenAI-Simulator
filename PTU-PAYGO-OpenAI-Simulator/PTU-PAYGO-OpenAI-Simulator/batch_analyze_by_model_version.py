"""
Batch PTU Analysis by Model and Version

Analyzes the Azure OpenAI logs with actual model/version data and generates
PTU sizing recommendations for each model and version combination.

Usage:
    python3 batch_analyze_by_model_version.py
    python3 batch_analyze_by_model_version.py --min-requests 50000
    python3 batch_analyze_by_model_version.py --top-n 10
"""

import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys

# Import our PTU calculation modules
from data_processing import prepare_dataframe, compute_minute_aggregation
from ptu_calculations import run_ptu_analysis, format_analysis_results
from pricing import load_pricing_data, get_price_ratio
from utils import get_dataset_duration_days


def map_model_to_pricing(model_name, model_version):
    """Map deployment model name and version to pricing model name."""
    model_lower = model_name.lower()
    
    # Direct matches
    if 'gpt-5' in model_lower:
        if 'mini' in model_lower:
            return 'gpt-4o-mini'  # Proxy for GPT-5 mini variants
        return 'gpt-4o'  # Proxy for GPT-5 models
    
    if 'gpt-4o' in model_lower:
        if 'mini' in model_lower:
            return 'gpt-4o-mini'
        if 'audio' in model_lower:
            return 'gpt-4o-audio-preview'
        return 'gpt-4o'
    
    if 'gpt-4.1' in model_lower or 'gpt-4-1' in model_lower:
        if 'mini' in model_lower:
            return 'gpt-4o-mini'  # Proxy for 4.1 mini
        return 'gpt-4o'  # Proxy for 4.1
    
    if 'gpt-4' in model_lower or 'gpt4' in model_lower:
        if 'turbo' in model_lower:
            return 'gpt-4-turbo'
        if '32k' in model_lower:
            return 'gpt-4-32k'
        if 'vision' in model_lower:
            return 'gpt-4-turbo'
        return 'gpt-4'
    
    if 'o3' in model_lower or 'o4' in model_lower:
        if 'mini' in model_lower:
            return 'o1-mini'
        return 'o1'
    
    if 'o1' in model_lower:
        if 'mini' in model_lower:
            return 'o1-mini'
        if 'preview' in model_lower:
            return 'o1-preview'
        return 'o1'
    
    if 'gpt-3.5' in model_lower or 'gpt35' in model_lower:
        return 'gpt-3.5-turbo'
    
    # Default fallback
    return 'gpt-4o'


def analyze_dataset_models(csv_path):
    """Analyze the dataset to get model/version statistics."""
    print(f"Loading and analyzing dataset: {csv_path}")
    print("This may take a moment for large files...")
    
    # Read CSV with proper dtypes - use low_memory=False for large files
    print("Reading CSV... (this may take 2-3 minutes for 4.5 GB file)")
    df = pd.read_csv(csv_path, 
                     dtype={
                         'timestamp [UTC]': str,
                         'input_tokens': int,
                         'output_tokens': int,
                         'total_tokens': int,
                         'model': str,
                         'model_version': str
                     },
                     low_memory=False)
    
    print(f"✅ Loaded {len(df):,} total requests")
    
    # Handle missing model/version
    df['model'] = df['model'].fillna('unknown')
    df['model_version'] = df['model_version'].fillna('unknown')
    
    # Create model+version key
    df['model_version_key'] = df['model'] + ' (' + df['model_version'] + ')'
    
    # Group by model and version
    model_stats = df.groupby('model_version_key').agg({
        'input_tokens': 'sum',
        'output_tokens': 'sum',
        'total_tokens': 'sum',
        'model': 'first',
        'model_version': 'first'
    }).reset_index()
    
    model_stats['request_count'] = df.groupby('model_version_key').size().values
    model_stats = model_stats.sort_values('request_count', ascending=False)
    
    print(f"\nFound {len(model_stats)} unique model/version combinations")
    print("\nTop 20 by request count:")
    print("-" * 100)
    for idx, row in model_stats.head(20).iterrows():
        print(f"  {row['model_version_key']:60s} {row['request_count']:>15,} requests  {row['total_tokens']:>20,} tokens")
    
    return df, model_stats


def run_batch_analysis(csv_path, output_dir, min_ptus=15, max_ptus=100, 
                       ptu_capacity_tpm=3000, ptu_price=221.0, 
                       min_requests=10000, top_n=None):
    """Run PTU analysis for each model/version in the dataset."""
    
    print(f"\n{'='*100}")
    print(f"BATCH PTU ANALYSIS BY MODEL AND VERSION")
    print(f"{'='*100}\n")
    
    # Load and analyze dataset
    full_df, model_stats = analyze_dataset_models(csv_path)
    
    # Filter by minimum requests
    significant_models = model_stats[model_stats['request_count'] >= min_requests].copy()
    print(f"\n{len(significant_models)} models meet the {min_requests:,} request threshold")
    
    # Optionally limit to top N
    if top_n:
        significant_models = significant_models.head(top_n)
        print(f"Analyzing top {top_n} models by request count")
    
    # Load pricing data
    model_list, model_prices = load_pricing_data()
    if not model_list:
        print("ERROR: Could not load pricing data")
        return
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Results storage
    all_results = []
    
    # Analyze each model/version
    for idx, row in significant_models.iterrows():
        model_key = row['model_version_key']
        model_name = row['model']
        model_version = row['model_version']
        request_count = row['request_count']
        
        print(f"\n{'-'*100}")
        print(f"[{len(all_results)+1}/{len(significant_models)}] Analyzing: {model_key}")
        print(f"  Requests: {request_count:,}")
        print(f"  Total Tokens: {row['total_tokens']:,}")
        print(f"  Input Tokens: {row['input_tokens']:,}")
        print(f"  Output Tokens: {row['output_tokens']:,}")
        
        # Map to pricing model
        pricing_model = map_model_to_pricing(model_name, model_version)
        print(f"  Using pricing for: {pricing_model}")
        
        if pricing_model not in model_prices:
            print(f"  WARNING: No pricing found for {pricing_model}, using gpt-4o as fallback")
            pricing_model = 'gpt-4o'
        
        input_price, output_price = model_prices[pricing_model]
        print(f"  Pricing: ${input_price:.4f}/1K input, ${output_price:.4f}/1K output")
        
        # Filter dataset for this model/version
        model_df = full_df[full_df['model_version_key'] == model_key].copy()
        
        # Prepare dataframe (convert timestamps, etc.)
        prepared_df, error = prepare_dataframe(model_df[['timestamp [UTC]', 'input_tokens', 'output_tokens', 'total_tokens']])
        
        if error:
            print(f"  ERROR preparing data: {error}")
            continue
        
        # Compute minute aggregation
        try:
            minute_series = compute_minute_aggregation(prepared_df)
            
            if minute_series.empty:
                print(f"  WARNING: No minute-level data after aggregation, skipping")
                continue
            
            dataset_days = get_dataset_duration_days(prepared_df, 'timestamp')
            peak_tpm = minute_series['tokens_per_minute'].max()
            avg_tpm = minute_series['tokens_per_minute'].mean()
            median_tpm = minute_series['tokens_per_minute'].median()
            
            print(f"  Dataset duration: {dataset_days:.1f} days")
            print(f"  Peak TPM: {peak_tpm:,.0f}")
            print(f"  Average TPM: {avg_tpm:,.0f}")
            print(f"  Median TPM: {median_tpm:,.0f}")
            
            # Run PTU analysis
            output_weight = get_price_ratio(input_price, output_price)
            
            print(f"  Running PTU analysis ({min_ptus}-{max_ptus} PTUs)...")
            results_df = run_ptu_analysis(
                request_data=prepared_df,
                minute_series=minute_series,
                min_ptu_count=min_ptus,
                max_ptu_count=max_ptus,
                ptu_capacity_tpm=ptu_capacity_tpm,
                final_ptu_price=ptu_price,
                input_price=input_price,
                output_price=output_price,
                dataset_days=dataset_days,
                output_weight=output_weight,
                progress_callback=None,
                status_callback=None
            )
            
            # Find optimal configuration
            paygo_only_cost = results_df[results_df['num_ptus'] == 0]['total_monthly_cost'].iloc[0]
            ptu_configs = results_df[results_df['num_ptus'] > 0].copy()
            ptu_configs['cost_diff'] = ptu_configs['total_monthly_cost'] - paygo_only_cost
            above_paygo = ptu_configs[ptu_configs['cost_diff'] >= 0]
            
            if not above_paygo.empty:
                optimal_idx = above_paygo['cost_diff'].idxmin()
            else:
                optimal_idx = ptu_configs['cost_diff'].abs().idxmin()
            
            optimal = results_df.loc[optimal_idx]
            
            # Calculate PTU percentage if not present
            if 'ptu_total_pct' not in optimal.index:
                ptu_tokens = optimal['ptu_input_tokens'] + optimal['ptu_output_tokens']
                total_tokens = prepared_df['total_tokens'].sum()
                ptu_total_pct = (ptu_tokens / total_tokens * 100) if total_tokens > 0 else 0
            else:
                ptu_total_pct = optimal['ptu_total_pct']
            
            print(f"\n  ✅ RECOMMENDATION:")
            print(f"     PTU Count: {optimal['num_ptus']:.0f}")
            print(f"     PTU Capacity: {optimal['ptu_capacity_tpm']:,.0f} TPM")
            print(f"     Utilization: {optimal['utilization_pct']:.1f}%")
            print(f"     Tokens via PTU: {ptu_total_pct:.1f}%")
            print(f"     Total Monthly Cost: ${optimal['total_monthly_cost']:,.2f}")
            print(f"     PAYGO Only Cost: ${paygo_only_cost:,.2f}")
            cost_diff_pct = ((optimal['total_monthly_cost'] - paygo_only_cost) / paygo_only_cost * 100)
            print(f"     Cost vs PAYGO: {cost_diff_pct:+.1f}%")
            
            # Save detailed results
            formatted_df = format_analysis_results(results_df)
            safe_filename = model_key.replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "")
            csv_output = output_path / f"{safe_filename}_analysis.csv"
            formatted_df.to_csv(csv_output, index=False)
            print(f"     Saved details: {csv_output.name}")
            
            # Store summary
            all_results.append({
                'model': model_name,
                'model_version': model_version,
                'model_version_key': model_key,
                'pricing_model': pricing_model,
                'requests': request_count,
                'total_tokens': row['total_tokens'],
                'input_tokens': row['input_tokens'],
                'output_tokens': row['output_tokens'],
                'dataset_days': dataset_days,
                'peak_tpm': peak_tpm,
                'avg_tpm': avg_tpm,
                'median_tpm': median_tpm,
                'recommended_ptus': optimal['num_ptus'],
                'ptu_capacity_tpm': optimal['ptu_capacity_tpm'],
                'utilization_pct': optimal['utilization_pct'],
                'tokens_via_ptu_pct': ptu_total_pct,
                'paygo_only_cost': paygo_only_cost,
                'optimal_cost': optimal['total_monthly_cost'],
                'cost_diff_usd': optimal['total_monthly_cost'] - paygo_only_cost,
                'cost_diff_pct': cost_diff_pct,
                'input_price_per_1k': input_price,
                'output_price_per_1k': output_price,
            })
            
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Generate summary report
    print(f"\n{'='*100}")
    print("GENERATING SUMMARY REPORT")
    print(f"{'='*100}\n")
    
    if not all_results:
        print("ERROR: No successful analyses to report")
        return
    
    summary_df = pd.DataFrame(all_results)
    summary_csv = output_path / "summary_by_model_version.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"✅ Saved CSV summary: {summary_csv}")
    
    # Generate text report
    report_path = output_path / "summary_report.txt"
    with open(report_path, 'w') as f:
        f.write("="*100 + "\n")
        f.write("PTU SIZING ANALYSIS BY MODEL AND VERSION\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*100 + "\n\n")
        
        f.write(f"Total Model/Version Combinations Analyzed: {len(all_results)}\n")
        f.write(f"PTU Pricing: ${ptu_price:.2f}/month per unit\n")
        f.write(f"PTU Capacity: {ptu_capacity_tpm:,} TPM per unit\n")
        f.write(f"Analysis Range: {min_ptus}-{max_ptus} PTUs\n\n")
        
        # Sort by monthly cost (highest first)
        summary_df_sorted = summary_df.sort_values('optimal_cost', ascending=False)
        
        f.write("\nMODEL RECOMMENDATIONS (sorted by monthly cost)\n")
        f.write("="*100 + "\n\n")
        
        for _, row in summary_df_sorted.iterrows():
            f.write(f"{row['model_version_key']}\n")
            f.write(f"  Pricing Model: {row['pricing_model']}\n")
            f.write(f"  Requests: {row['requests']:,.0f}\n")
            f.write(f"  Total Tokens: {row['total_tokens']:,.0f}\n")
            f.write(f"  Dataset Duration: {row['dataset_days']:.1f} days\n")
            f.write(f"  Peak TPM: {row['peak_tpm']:,.0f}\n")
            f.write(f"  Average TPM: {row['avg_tpm']:,.0f}\n")
            f.write(f"  Median TPM: {row['median_tpm']:,.0f}\n")
            f.write(f"\n")
            f.write(f"  RECOMMENDATION:\n")
            f.write(f"    PTU Count: {row['recommended_ptus']:.0f}\n")
            f.write(f"    PTU Capacity: {row['ptu_capacity_tpm']:,.0f} TPM\n")
            f.write(f"    Utilization: {row['utilization_pct']:.1f}%\n")
            f.write(f"    % Tokens via PTU: {row['tokens_via_ptu_pct']:.1f}%\n")
            f.write(f"    Monthly Cost (PTU+PAYGO): ${row['optimal_cost']:,.2f}\n")
            f.write(f"    Monthly Cost (PAYGO only): ${row['paygo_only_cost']:,.2f}\n")
            f.write(f"    Cost Difference: ${row['cost_diff_usd']:,.2f} ({row['cost_diff_pct']:+.1f}%)\n")
            f.write(f"\n")
            f.write("-"*100 + "\n\n")
        
        # Aggregate summary
        total_requests = summary_df['requests'].sum()
        total_tokens = summary_df['total_tokens'].sum()
        total_paygo = summary_df['paygo_only_cost'].sum()
        total_optimal = summary_df['optimal_cost'].sum()
        total_diff = total_optimal - total_paygo
        total_diff_pct = (total_diff / total_paygo * 100) if total_paygo > 0 else 0
        total_ptus = summary_df['recommended_ptus'].sum()
        
        f.write("\n" + "="*100 + "\n")
        f.write("AGGREGATE SUMMARY\n")
        f.write("="*100 + "\n")
        f.write(f"Total Requests: {total_requests:,.0f}\n")
        f.write(f"Total Tokens: {total_tokens:,.0f}\n")
        f.write(f"\n")
        f.write(f"Total Monthly Cost (PAYGO only): ${total_paygo:,.2f}\n")
        f.write(f"Total Monthly Cost (PTU optimized): ${total_optimal:,.2f}\n")
        f.write(f"Total Difference: ${total_diff:,.2f} ({total_diff_pct:+.1f}%)\n")
        f.write(f"\n")
        f.write(f"Total Recommended PTUs: {total_ptus:.0f}\n")
        f.write(f"Total PTU Monthly Cost: ${total_ptus * ptu_price:,.2f}\n")
        
        # Top models by cost
        f.write(f"\n\nTOP 10 MODELS BY MONTHLY COST\n")
        f.write("-"*100 + "\n")
        for i, (_, row) in enumerate(summary_df_sorted.head(10).iterrows(), 1):
            f.write(f"{i:2d}. {row['model_version_key']:50s} ${row['optimal_cost']:>12,.2f}/mo  ({row['recommended_ptus']:.0f} PTUs)\n")
    
    print(f"✅ Saved text report: {report_path}")
    
    print(f"\n{'='*100}")
    print("✅ BATCH ANALYSIS COMPLETE")
    print(f"{'='*100}\n")
    print(f"Analyzed: {len(all_results)} model/version combinations")
    print(f"Output directory: {output_dir}/")
    print(f"\n📊 Key Results:")
    print(f"   Total PAYGO Cost: ${total_paygo:,.2f}/month")
    print(f"   Total PTU Cost: ${total_optimal:,.2f}/month")
    print(f"   Difference: ${total_diff:,.2f} ({total_diff_pct:+.1f}%)")
    print(f"   Recommended PTUs: {total_ptus:.0f}")
    print(f"\n📁 Output Files:")
    print(f"   - {summary_csv.name} (detailed CSV)")
    print(f"   - {report_path.name} (summary report)")
    print(f"   - Individual model CSVs with full analysis")


def main():
    parser = argparse.ArgumentParser(
        description="Batch PTU analysis by model and version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all models with 10K+ requests
  python3 batch_analyze_by_model_version.py
  
  # Analyze top 15 models only
  python3 batch_analyze_by_model_version.py --top-n 15
  
  # Higher threshold for major models only
  python3 batch_analyze_by_model_version.py --min-requests 100000
  
  # Custom PTU configuration
  python3 batch_analyze_by_model_version.py --ptu-price 200 --ptu-capacity 5000
        """
    )
    
    parser.add_argument('--input', 
                       default='analysis_output/nvstrgitentint_complete_analysis_with_models.csv',
                       help='Input CSV file path with model/version columns')
    parser.add_argument('--output', 
                       default='batch_analysis_output',
                       help='Output directory for results')
    parser.add_argument('--min-ptus', type=int, default=15,
                       help='Minimum PTU count to analyze (default: 15)')
    parser.add_argument('--max-ptus', type=int, default=100,
                       help='Maximum PTU count to analyze (default: 100)')
    parser.add_argument('--ptu-capacity', type=int, default=3000,
                       help='TPM capacity per PTU unit (default: 3000)')
    parser.add_argument('--ptu-price', type=float, default=221.0,
                       help='Monthly price per PTU unit (default: 221.0)')
    parser.add_argument('--min-requests', type=int, default=10000,
                       help='Minimum requests threshold for analysis (default: 10000)')
    parser.add_argument('--top-n', type=int, default=None,
                       help='Only analyze top N models by request count (default: all)')
    
    args = parser.parse_args()
    
    # Check if input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ ERROR: Input file not found: {args.input}")
        print(f"\nLooking for CSV with columns: timestamp [UTC], input_tokens, output_tokens, total_tokens, model, model_version")
        sys.exit(1)
    
    # Run batch analysis
    run_batch_analysis(
        csv_path=args.input,
        output_dir=args.output,
        min_ptus=args.min_ptus,
        max_ptus=args.max_ptus,
        ptu_capacity_tpm=args.ptu_capacity,
        ptu_price=args.ptu_price,
        min_requests=args.min_requests,
        top_n=args.top_n
    )


if __name__ == "__main__":
    main()
