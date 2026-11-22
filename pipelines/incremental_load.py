"""
Incremental Data Loading Engine for DemandIQ
Demonstrates production High-Watermark CDC (Change Data Capture) pattern.
Only ingests and transforms newly arrived records without reprocessing the entire database.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
from sqlalchemy import text
from database.db_connection import get_engine
from monitoring.pipeline_logger import PipelineRun
from validation.data_quality import validate_and_clean_sales
import config

logger = logging.getLogger("DemandIQ.IncrementalLoad")

def get_current_watermark() -> Dict[str, Any]:
    """Reads the stored watermark (last processed sale_id and timestamp)."""
    if config.WATERMARK_FILE.exists():
        try:
            with open(config.WATERMARK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # If watermark file doesn't exist, query the database for max(sale_id)
    engine = get_engine()
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT COALESCE(MAX(sale_id), 0), COALESCE(MAX(transaction_date), '2026-01-01') FROM sales")).fetchone()
            return {
                "last_processed_sale_id": int(res[0]),
                "last_processed_date": str(res[1]),
                "last_pipeline_run": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            }
    except Exception:
        return {
            "last_processed_sale_id": 0,
            "last_processed_date": "2026-01-01",
            "last_pipeline_run": "Never"
        }

def save_watermark(max_sale_id: int, max_date: str):
    """Updates the watermark state file with the new high-water mark."""
    state = {
        "last_processed_sale_id": max_sale_id,
        "last_processed_date": max_date,
        "last_pipeline_run": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(config.WATERMARK_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    logger.info(f"Watermark updated: last_sale_id={max_sale_id}, last_date={max_date}")

def run_incremental_load(batch_file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Executes the incremental load:
    1. Retrieves the current watermark.
    2. Identifies new records exceeding the watermark.
    3. Validates and cleans delta records.
    4. Appends to operational sales table and dimensional fact_sales table.
    5. Updates watermark and records pipeline telemetry.
    """
    with PipelineRun("incremental_sales_load") as pipeline_tracker:
        if batch_file_path is None:
            batch_file_path = config.SAMPLE_DATA_DIR / "incremental_batch_1.csv"

        if not batch_file_path.exists():
            raise FileNotFoundError(f"Incremental batch file not found: {batch_file_path}")

        watermark = get_current_watermark()
        last_id = watermark.get("last_processed_sale_id", 0)
        logger.info(f"High-Watermark Check: Current last_sale_id is {last_id}")

        # Read incoming delta batch
        incoming_df = pd.read_csv(batch_file_path)
        incoming_count = len(incoming_df)
        logger.info(f"Incoming delta batch contains {incoming_count} records.")

        # Filter delta: only records with sale_id > last_id
        incoming_df["sale_id"] = pd.to_numeric(incoming_df["sale_id"], errors="coerce").fillna(0).astype(int)
        delta_df = incoming_df[incoming_df["sale_id"] > last_id].copy()

        if delta_df.empty:
            logger.info("No new records to process. Database is up to date with the latest watermark.")
            pipeline_tracker.records_processed = 0
            return {
                "status": "UP_TO_DATE",
                "new_records_count": 0,
                "watermark": watermark
            }

        logger.info(f"Identified {len(delta_df)} new records after watermark filter.")

        # Fetch active products & customers for referential validation
        engine = get_engine()
        with engine.connect() as conn:
            prods = set(pd.read_sql_query(text("SELECT product_id FROM products"), conn)["product_id"])
            custs = set(pd.read_sql_query(text("SELECT customer_id FROM customers"), conn)["customer_id"])

        # Validate through Data Quality Engine
        clean_delta, dq_report = validate_and_clean_sales(
            delta_df,
            valid_product_ids=prods,
            valid_customer_ids=custs
        )

        if clean_delta.empty:
            logger.warning("All delta records were rejected by Data Quality gates.")
            pipeline_tracker.records_processed = 0
            return {
                "status": "ALL_REJECTED",
                "new_records_count": 0,
                "dq_report": dq_report.to_dict()
            }

        # Append to operational sales table
        with engine.begin() as conn:
            clean_delta.to_sql("sales", conn, if_exists="append", index=False)
            logger.info(f"Appended {len(clean_delta)} records to table 'sales'.")

        # Update Star Schema: Dim_Date and Fact_Sales
        with engine.connect() as conn:
            prod_lookup = pd.read_sql_query(text("SELECT product_key, product_id, cost_price FROM dim_product"), conn)

        delta_fact = pd.merge(clean_delta, prod_lookup, on="product_id", how="left")
        delta_fact["cost_price"] = delta_fact["cost_price"].fillna(0.0)
        delta_fact["date_id"] = pd.to_datetime(delta_fact["transaction_date"]).dt.strftime("%Y%m%d").astype(int)
        delta_fact["customer_key"] = delta_fact["customer_id"]
        delta_fact["gross_revenue"] = delta_fact["total_amount"]
        delta_fact["total_cost"] = (delta_fact["quantity"] * delta_fact["cost_price"]).round(2)
        delta_fact["net_profit"] = (delta_fact["gross_revenue"] - delta_fact["total_cost"]).round(2)

        fact_to_insert = pd.DataFrame({
            "fact_id": delta_fact["sale_id"],
            "sale_id": delta_fact["sale_id"],
            "date_id": delta_fact["date_id"],
            "product_key": delta_fact["product_key"],
            "customer_key": delta_fact["customer_key"],
            "quantity": delta_fact["quantity"],
            "unit_price": delta_fact["unit_price"],
            "gross_revenue": delta_fact["gross_revenue"],
            "total_cost": delta_fact["total_cost"],
            "net_profit": delta_fact["net_profit"],
            "channel": delta_fact["channel"]
        })

        with engine.begin() as conn:
            fact_to_insert.to_sql("fact_sales", conn, if_exists="append", index=False)
            logger.info(f"Appended {len(fact_to_insert)} records to warehouse table 'fact_sales'.")

        # Update watermark
        new_max_id = int(clean_delta["sale_id"].max())
        new_max_date = str(clean_delta["transaction_date"].max())
        save_watermark(new_max_id, new_max_date)

        pipeline_tracker.records_processed = len(clean_delta)

        return {
            "status": "SUCCESS",
            "new_records_count": len(clean_delta),
            "new_watermark": {
                "last_processed_sale_id": new_max_id,
                "last_processed_date": new_max_date
            },
            "dq_report": dq_report.to_dict()
        }

if __name__ == "__main__":
    result = run_incremental_load()
    print("Incremental load result:", result)
