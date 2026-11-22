"""
Master Pipeline Orchestrator for DemandIQ
Coordinates the full End-to-End Batch ETL:
Extract -> Validate/Clean -> Transform -> Load -> Forecast -> Log
"""
import logging
from typing import Dict, Any
from database.db_connection import init_db
from monitoring.pipeline_logger import PipelineRun
from pipelines.extract import extract_all
from pipelines.transform import transform_all
from pipelines.load import load_all
from pipelines.incremental_load import save_watermark
from forecasting.demand_forecast import generate_demand_forecasts

logger = logging.getLogger("DemandIQ.MainPipeline")

def run_full_pipeline() -> Dict[str, Any]:
    """
    Executes the complete DemandIQ data engineering pipeline.
    Wrapped in PipelineRun for observability and auditing in pipeline_logs.
    """
    # Step 0: Ensure database schema and views exist
    init_db()

    with PipelineRun("demand_iq_master_batch_etl") as pipeline_tracker:
        logger.info("==================================================")
        logger.info("       STARTING DEMANDIQ MASTER DATA PIPELINE     ")
        logger.info("==================================================")

        # Step 1: Extract raw data from multi-sources (CSVs + Weather API + Staging)
        raw_datasets = extract_all()

        # Step 2: Transform, Clean, Validate & Build Star Schema
        clean_operational, star_schema, dq_report = transform_all(raw_datasets)

        # Step 3: Load into relational database and data warehouse
        load_all(clean_operational, star_schema)

        # Step 4: Initialize/Update Watermark for future incremental loads
        clean_sales = clean_operational["sales"]
        if not clean_sales.empty:
            max_sale_id = int(clean_sales["sale_id"].max())
            max_date = str(clean_sales["transaction_date"].max())
            save_watermark(max_sale_id, max_date)

        # Step 5: Demand Forecasting Analytics
        forecast_results = generate_demand_forecasts(horizon_days=30)

        # Total records processed tracking
        total_records = len(clean_sales) + len(clean_operational["products"]) + len(clean_operational["weather"])
        pipeline_tracker.records_processed = total_records

        logger.info("==================================================")
        logger.info(f"   PIPELINE FINISHED SUCCESSFULLY! ({total_records} records)   ")
        logger.info("==================================================")

        return {
            "status": "SUCCESS",
            "records_processed": total_records,
            "data_quality_report": dq_report.to_dict(),
            "forecast_metrics": forecast_results["metrics"],
            "pipeline_id": pipeline_tracker.pipeline_id,
            "duration_seconds": pipeline_tracker.duration_seconds
        }

if __name__ == "__main__":
    result = run_full_pipeline()
    print("Master pipeline execution summary:", result)
