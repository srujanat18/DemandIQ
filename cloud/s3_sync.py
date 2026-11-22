"""
AWS S3 Data Lake Synchronization Module for DemandIQ
Transfers raw CSV/JSON extracts and processed analytical datasets to Amazon S3.
Supports both real AWS S3 upload (boto3) and resilient simulated dry-run mode.
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Any
import config

logger = logging.getLogger("DemandIQ.AWS.S3")

def sync_to_s3(dry_run: bool = True) -> Dict[str, Any]:
    """
    Syncs raw and processed datasets to Amazon S3 data lake.
    Default dry_run simulates S3 transfer with deterministic paths.
    """
    bucket_name = config.AWS_S3_BUCKET
    files_to_sync = [
        ("raw/sales", config.RAW_DATA_DIR / "sales_raw.csv"),
        ("raw/products", config.RAW_DATA_DIR / "products_raw.csv"),
        ("raw/customers", config.RAW_DATA_DIR / "customers_raw.csv"),
        ("raw/weather", config.RAW_DATA_DIR / "weather_raw.json"),
        ("processed/sales", config.PROCESSED_DATA_DIR / "sales_clean.csv"),
        ("processed/quality_reports", config.PROCESSED_DATA_DIR / "dq_report_sales.json")
    ]

    synced_objects = []

    try:
        import boto3
        s3_client = boto3.client(
            "s3",
            region_name=config.AWS_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        has_boto3 = True
    except Exception:
        has_boto3 = False

    for prefix, file_path in files_to_sync:
        if file_path.exists():
            s3_key = f"demandiq-lake/{prefix}/{file_path.name}"
            s3_uri = f"s3://{bucket_name}/{s3_key}"

            if has_boto3 and not dry_run and os.getenv("AWS_ACCESS_KEY_ID"):
                try:
                    s3_client.upload_file(str(file_path), bucket_name, s3_key)
                    logger.info(f"Uploaded {file_path.name} to {s3_uri}")
                    synced_objects.append({"file": file_path.name, "s3_uri": s3_uri, "status": "UPLOADED"})
                except Exception as e:
                    logger.warning(f"Failed to upload {file_path.name} to S3: {e}")
                    synced_objects.append({"file": file_path.name, "s3_uri": s3_uri, "status": f"FAILED: {e}"})
            else:
                # Dry run simulation
                logger.info(f"[S3 Sync (Simulation)] {file_path.name} -> {s3_uri}")
                synced_objects.append({"file": file_path.name, "s3_uri": s3_uri, "status": "SIMULATED_SYNC"})

    return {
        "bucket": bucket_name,
        "region": config.AWS_REGION,
        "synced_objects": synced_objects,
        "total_files": len(synced_objects)
    }

if __name__ == "__main__":
    result = sync_to_s3(dry_run=True)
    print("S3 Sync Summary:", result)
