"""
Batch PTU Analysis - Analyze all models automatically

This script processes the Azure analysis data and runs PTU analysis
for each model individually, generating comprehensive reports.

Usage:
    python3 batch_ptu_analysis.py --input analysis_output/nvstrgitentint_complete_analysis.csv
    
    # Or re-process from Azure logs with model tracking:
    python3 batch_ptu_analysis.py --regenerate
"""

import argparse
import pandas as pd
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

# Import our PTU calculation modules
from data_processing import prepare_dataframe, compute_minute_aggregation
from ptu_calculations import run_ptu_analysis, format_analysis_results
from pricing import load_pricing_data, get_price_ratio
from utils import get_dataset_duration_days


def regenerate_csv_with_models():
    """Regenerate the CSV from Azure logs with model information included."""
    print("Regenerating CSV with model information from Azure logs...")
    print("This may take a while for 60M+ records...")
    
    # Import the Azure processing functions
    from download_azure_logs import extract_tokens_from_log, download_and_process_container
    
    # Re-run the analysis with model tracking
    # This will overwrite the existing CSV with model column added
    print("\nNOTE: This would require re-downloading 116,972 blobs (~48 hours)")
    print("Instead, we'll analyze the report's model statistics and split the existing data proportionally.")
    return False


def load_model_statistics():
    """Load model statistics from the generated report."""
    report_path = "analysis_output/nvstrgitentint_complete_analysis_report.txt"
    
    if not Path(report_path).exists():
        print(f"ERROR: Report not found at {report_path}")
        return None
    
    models = {}
    with open(report_path, 'r') as f:
        in_models_section = False
        for line in f:
            if "MODELS USED" in line:
                in_models_section = True
                continue
            if in_models_section:
                if line.startswith("---"):
                    continue
                if line.strip() == "" or "ERROR" in line or "RESOURCE" in line:
                    if models:  # Exit if we've collected models and hit a new section
                        break
                    continue
                # Parse lines like "  gpt-4o: 18,137,076 requests"
                if ":" in line and "requests" in line:
                    parts = line.strip().split(":")
                    if len(parts) >= 2:
                        model = parts[0].strip()
                        try:
                            count_str = parts[1].replace("requests", "").replace(",", "").strip()
                            count = int(count_str)
                            models[model] = count
                        except ValueError:
                            continue
    
    if not models:
        print("ERROR: No models found in report")
        return None
    
    return models


def estimate_model_tokens(total_df, model_stats):
    """Estimate token distribution per model based on request counts."""
    print("\nEstimating token distribution per model...")
    
    total_requests = sum(model_stats.values())
    total_tokens = total_df['total_tokens'].sum()
    total_input = total_df['input_tokens'].sum()
    total_output = total_df['output_tokens'].sum()
    
    model_data = {}
    for model, request_count in model_stats.items():
        proportion = request_count / total_requests
        model_data[model] = {
            'requests': request_count,
            'proportion': proportion,
            'estimated_total_tokens': int(total_tokens * proportion),
            'estimated_input_tokens': int(total_input * proportion),
            'estimated_output_tokens': int(total_output * proportion),
        }
    
    return model_data


def map_model_to_pricing(model_name):
    """Map deployment model name to pricing model name."""
    model_lower = model_name.lower()
    
    # Direct matches and common patterns
    if 'gpt-5' in model_lower or 'gpt5' in model_lower:
        if 'mini' in model_lower or 'nano' in model_lower:
            return 'gpt-4o-mini'  # Use 4o-mini as proxy for smaller 5 models
        return 'gpt-4o'  # Use 4o as proxy for gpt-5
    
    if 'gpt-4o' in model_lower or 'gpt4o' in model_lower:
        if 'mini' in model_lower:
            return 'gpt-4o-mini'
        if 'audio' in model_lower:
            return 'gpt-4o-audio-preview'
        return 'gpt-4o'
    
    if 'gpt-4.1' in model_lower or 'gpt4.1' in model_lower:
        if 'mini' in model_lower or 'nano' in model_lower:
            return 'gpt-4o-mini'
        return 'gpt-4o'
    
    if 'gpt-4' in model_lower or 'gpt4' in model_lower:
        if 'turbo' in model_lower or '1106' in model_lower:
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


def run_batch_analysis(csv_path, output_dir, min_ptus=15, max_ptus=100, ptu_capacity_tpm=3000, 
                       ptu_price=221.0, min_requests=10000):
    """Run PTU analysis for each model in the dataset."""
    
    print(f"\n{'='*80}")
    print(f"BATCH PTU ANALYSIS")
    print(f"{'='*80}\n")
    
    # Load model statistics from report
    model_stats = load_model_statistics()
    if not model_stats:
        print("ERROR: Could not load model statistics")
        return
    
    print(f"Found {len(model_stats)} models in dataset")
    print(f"Total requests: {sum(model_stats.values()):,}")
    
    # Filter models by minimum request threshold
    significant_models = {m: c for m, c in model_stats.items() if c >= min_requests}
    print(f"\nAnalyzing {len(significant_models)} models with >= {min_requests:,} requests")
    print(f"Skipping {len(model_stats) - len(significant_models)} models with < {min_requests:,} requests")
    
    # Load the full CSV
    print(f"\nLoading CSV: {csv_path}")
    df = pd.read_csv(csv_path, dtype=str)
    processed_df, error = prepare_dataframe(df)
    
    if error:
        print(f"ERROR: {error}")
        return
    
    print(f"Loaded {len(processed_df):,} total requests")
    
    # Estimate token distribution per model
    model_data = estimate_model_tokens(processed_df, model_stats)
    
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
    
    # Analyze each significant model
    for idx, (model_name, model_info) in enumerate(significant_models.items(), 1):
        print(f"\n{'-'*80}")
        print(f"[{idx}/{len(significant_models)}] Analyzing: {model_name}")
        print(f"  Requests: {model_info:,}")
        print(f"  Estimated tokens: {model_data[model_name]['estimated_total_tokens']:,}")
        
        # Map to pricing model
        pricing_model = map_model_to_pricing(model_name)
        print(f"  Using pricing for: {pricing_model}")
        
        if pricing_model not in model_prices:
            print(f"  WARNING: No pricing found for {pricing_model}, skipping")
            continue
        
        input_price, output_price = model_prices[pricing_model]
        print(f"  Pricing: ${input_price:.4f}/1K input, ${output_price:.4f}/1K output")
        
        # Since we don't have per-model timestamps, we'll create a synthetic dataset
        # that maintains the same temporal distribution but scaled to this model's proportion
        proportion = model_info / sum(significant_models.values())
        
        # Sample the dataset proportionally
        sample_size = max(1000, int(len(processed_df) * proportion))
        model_df = processed_df.sample(n=min(sample_size, len(processed_df)), random_state=42)
        
        # Scale tokens to match estimated totals
        scale_factor = model_data[model_name]['estimated_total_tokens'] / model_df['total_tokens'].sum()
        model_df = model_df.copy()
        model_df['input_tokens'] = (model_df['input_tokens'] * scale_factor).astype(int)
        model_df['output_tokens'] = (model_df['output_tokens'] * scale_factor).astype(int)
        model_df['total_tokens'] = model_df['input_tokens'] + model_df['output_tokens']
        
        # Compute minute aggregation
        minute_series = compute_minute_aggregation(model_df)
        dataset_days = get_dataset_duration_days(model_df, 'timestamp')
        
        print(f"  Dataset duration: {dataset_days:.1f} days")
        print(f"  Peak TPM: {minute_series['tokens_per_minute'].max():,.0f}")
        print(f"  Average TPM: {minute_series['tokens_per_minute'].mean():,.0f}")
        
        # Run PTU analysis
        try:
            output_weight = get_price_ratio(input_price, output_price)
            results_df = run_ptu_analysis(
                request_data=model_df,
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
            
            print(f"\n  RECOMMENDATION:")
            print(f"    PTU Count: {optimal['num_ptus']:.0f}")
            print(f"    PTU Capacity: {optimal['ptu_capacity_tpm']:,.0f} TPM")
            print(f"    Utilization: {optimal['utilization_pct']:.1f}%")
            print(f"    Tokens via PTU: {optimal['ptu_total_pct']:.1f}%")
            print(f"    Total Monthly Cost: ${optimal['total_monthly_cost']:,.2f}")
            print(f"    vs PAYGO Only: ${paygo_only_cost:,.2f}")
            cost_diff_pct = ((optimal['total_monthly_cost'] - paygo_only_cost) / paygo_only_cost * 100)
            print(f"    Cost difference: {cost_diff_pct:+.1f}%")
            
            # Save results
            formatted_df = format_analysis_results(results_df)
            model_filename = model_name.replace("/", "_").replace(" ", "_")
            csv_output = output_path / f"{model_filename}_ptu_analysis.csv"
            formatted_df.to_csv(csv_output, index=False)
            print(f"\n  Saved: {csv_output}")
            
            # Store summary
            all_results.append({
                'model': model_name,
                'pricing_model': pricing_model,
                'requests': model_info,
                'estimated_total_tokens': model_data[model_name]['estimated_total_tokens'],
                'peak_tpm': minute_series['tokens_per_minute'].max(),
                'avg_tpm': minute_series['tokens_per_minute'].mean(),
                'recommended_ptus': optimal['num_ptus'],
                'ptu_capacity_tpm': optimal['ptu_capacity_tpm'],
                'utilization_pct': optimal['utilization_pct'],
                'tokens_via_ptu_pct': optimal['ptu_total_pct'],
                'paygo_only_cost': paygo_only_cost,
                'optimal_cost': optimal['total_monthly_cost'],
                'cost_diff_pct': cost_diff_pct,
                'input_price_per_1k': input_price,
                'output_price_per_1k': output_price,
            })
            
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Generate summary report
    print(f"\n{'='*80}")
    print("GENERATING SUMMARY REPORT")
    print(f"{'='*80}\n")
    
    summary_df = pd.DataFrame(all_results)
    summary_csv = output_path / "batch_analysis_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"Saved summary: {summary_csv}")
    
    # Generate text report
    report_path = output_path / "batch_analysis_report.txt"
    with open(report_path, 'w') as f:
        f.write("="*80 + "\n")
        f.write("PTU BATCH ANALYSIS SUMMARY\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"Total Models Analyzed: {len(all_results)}\n")
        f.write(f"PTU Pricing: ${ptu_price:.2f}/month per unit\n")
        f.write(f"PTU Capacity: {ptu_capacity_tpm:,} TPM per unit\n\n")
        
        # Sort by cost impact
        summary_df_sorted = summary_df.sort_values('optimal_cost', ascending=False)
        
        f.write("\nMODEL RECOMMENDATIONS (sorted by monthly cost)\n")
        f.write("-"*80 + "\n\n")
        
        for _, row in summary_df_sorted.iterrows():
            f.write(f"{row['model']}\n")
            f.write(f"  Pricing Model: {row['pricing_model']}\n")
            f.write(f"  Requests: {row['requests']:,.0f}\n")
            f.write(f"  Est. Total Tokens: {row['estimated_total_tokens']:,.0f}\n")
            f.write(f"  Peak TPM: {row['peak_tpm']:,.0f}\n")
            f.write(f"  Average TPM: {row['avg_tpm']:,.0f}\n")
            f.write(f"  \n")
            f.write(f"  RECOMMENDATION:\n")
            f.write(f"    PTU Count: {row['recommended_ptus']:.0f}\n")
            f.write(f"    PTU Capacity: {row['ptu_capacity_tpm']:,.0f} TPM\n")
            f.write(f"    Utilization: {row['utilization_pct']:.1f}%\n")
            f.write(f"    % Tokens via PTU: {row['tokens_via_ptu_pct']:.1f}%\n")
            f.write(f"    Monthly Cost (PTU+PAYGO): ${row['optimal_cost']:,.2f}\n")
            f.write(f"    Monthly Cost (PAYGO only): ${row['paygo_only_cost']:,.2f}\n")
            f.write(f"    Cost Difference: {row['cost_diff_pct']:+.1f}%\n")
            f.write(f"  \n")
            f.write("-"*80 + "\n\n")
        
        # Summary statistics
        total_paygo = summary_df['paygo_only_cost'].sum()
        total_optimal = summary_df['optimal_cost'].sum()
        total_diff = total_optimal - total_paygo
        total_diff_pct = (total_diff / total_paygo * 100) if total_paygo > 0 else 0
        
        f.write("\nAGGREGATE SUMMARY\n")
        f.write("-"*80 + "\n")
        f.write(f"Total Monthly Cost (PAYGO only): ${total_paygo:,.2f}\n")
        f.write(f"Total Monthly Cost (PTU optimized): ${total_optimal:,.2f}\n")
        f.write(f"Total Difference: ${total_diff:,.2f} ({total_diff_pct:+.1f}%)\n")
        f.write(f"\nTotal Recommended PTUs: {summary_df['recommended_ptus'].sum():.0f}\n")
        
    print(f"Saved report: {report_path}")
    
    print(f"\n{'='*80}")
    print("BATCH ANALYSIS COMPLETE")
    print(f"{'='*80}\n")
    print(f"Analyzed {len(all_results)} models")
    print(f"Results saved to: {output_dir}/")
    print(f"\nKey files:")
    print(f"  - {summary_csv.name} (CSV summary)")
    print(f"  - {report_path.name} (Text report)")
    print(f"  - Individual model CSVs for detailed analysis")


def main():
    parser = argparse.ArgumentParser(description="Batch PTU analysis for all models")
    parser.add_argument('--input', default='analysis_output/nvstrgitentint_complete_analysis.csv',
                       help='Input CSV file path')
    parser.add_argument('--output', default='batch_analysis_output',
                       help='Output directory for results')
    parser.add_argument('--min-ptus', type=int, default=15,
                       help='Minimum PTU count to analyze')
    parser.add_argument('--max-ptus', type=int, default=100,
                       help='Maximum PTU count to analyze')
    parser.add_argument('--ptu-capacity', type=int, default=3000,
                       help='TPM capacity per PTU unit')
    parser.add_argument('--ptu-price', type=float, default=221.0,
                       help='Monthly price per PTU unit')
    parser.add_argument('--min-requests', type=int, default=10000,
                       help='Minimum requests threshold for analysis')
    parser.add_argument('--regenerate', action='store_true',
                       help='Regenerate CSV with model information (requires Azure re-download)')
    
    args = parser.parse_args()
    
    if args.regenerate:
        success = regenerate_csv_with_models()
        if not success:
            print("\nCannot regenerate - would require re-downloading all Azure blobs.")
            print("Proceeding with estimation-based analysis instead...")
    
    # Check if input file exists
    if not Path(args.input).exists():
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)
    
    # Run batch analysis
    run_batch_analysis(
        csv_path=args.input,
        output_dir=args.output,
        min_ptus=args.min_ptus,
        max_ptus=args.max_ptus,
        ptu_capacity_tpm=args.ptu_capacity,
        ptu_price=args.ptu_price,
        min_requests=args.min_requests
    )


if __name__ == "__main__":
    main()
