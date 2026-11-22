"""
DemandIQ Command-Line Pipeline Execution Tool
Usage:
    python run_pipeline.py --mode full           # Runs the complete Batch ETL
    python run_pipeline.py --mode incremental    # Runs incremental High-Watermark load
    python run_pipeline.py --mode generate-data  # Regenerates synthetic raw datasets
"""
import argparse
import sys
from pipelines.main import run_full_pipeline
from pipelines.incremental_load import run_incremental_load
from data.generate_mock_raw_data import (
    generate_products, generate_customers, generate_sales, generate_competitors
)

def main():
    parser = argparse.ArgumentParser(description="DemandIQ Data Pipeline CLI Runner")
    parser.add_argument(
        "--mode",
        choices=["full", "incremental", "generate-data"],
        default="full",
        help="Pipeline execution mode (default: full)"
    )
    args = parser.parse_args()

    if args.mode == "generate-data":
        print("[CLI] Regenerating mock raw data...")
        p = generate_products()
        c = generate_customers()
        generate_sales(p, c)
        generate_competitors(p)
        print("[CLI] Data generation complete.")

    elif args.mode == "incremental":
        print("[CLI] Triggering incremental high-watermark load...")
        res = run_incremental_load()
        print(f"[CLI] Incremental load status: {res.get('status')}")
        print(f"[CLI] New records processed: {res.get('new_records_count')}")

    elif args.mode == "full":
        print("[CLI] Triggering Master ETL batch pipeline...")
        res = run_full_pipeline()
        print(f"[CLI] Status: {res.get('status')}")
        print(f"[CLI] Records processed: {res.get('records_processed')}")
        print(f"[CLI] Data Quality Acceptance: {res.get('data_quality_report', {}).get('acceptance_rate_pct')}%")

if __name__ == "__main__":
    main()
