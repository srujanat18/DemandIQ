"""
Data Quality & Validation Engine for DemandIQ
Implements automated data profiling, validation gates, anomaly detection, and data quality reporting.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Tuple, Any
import pandas as pd
import config

logger = logging.getLogger("DemandIQ.DataQuality")

class DataQualityReport:
    """Stores metrics and validation outcomes for data audit reporting."""
    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name
        self.timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.total_incoming: int = 0
        self.duplicates_removed: int = 0
        self.nulls_handled: int = 0
        self.negative_quantities_rejected: int = 0
        self.invalid_prices_rejected: int = 0
        self.invalid_dates_rejected: int = 0
        self.foreign_key_violations_rejected: int = 0
        self.final_valid_records: int = 0
        self.validation_passed: bool = True
        self.warnings: list = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "timestamp": self.timestamp,
            "total_incoming": self.total_incoming,
            "duplicates_removed": self.duplicates_removed,
            "nulls_handled": self.nulls_handled,
            "negative_quantities_rejected": self.negative_quantities_rejected,
            "invalid_prices_rejected": self.invalid_prices_rejected,
            "invalid_dates_rejected": self.invalid_dates_rejected,
            "foreign_key_violations_rejected": self.foreign_key_violations_rejected,
            "final_valid_records": self.final_valid_records,
            "acceptance_rate_pct": round(
                (self.final_valid_records / self.total_incoming * 100) if self.total_incoming > 0 else 0, 2
            ),
            "validation_passed": self.validation_passed,
            "warnings": self.warnings
        }

    def save_report(self, filepath=None):
        if filepath is None:
            filepath = config.PROCESSED_DATA_DIR / f"dq_report_{self.dataset_name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Data quality report saved to {filepath}")


def validate_and_clean_sales(df_sales: pd.DataFrame, valid_product_ids: set, valid_customer_ids: set) -> Tuple[pd.DataFrame, DataQualityReport]:
    """
    Cleans and validates the incoming sales DataFrame.
    Applies business rules:
      1. Deduplication on sale_id
      2. Non-null handling for essential fields
      3. Quantity > 0
      4. Unit Price > 0
      5. Valid Date format YYYY-MM-DD
      6. Foreign key existence in products and customers
    """
    report = DataQualityReport("sales")
    report.total_incoming = len(df_sales)
    logger.info(f"Starting data quality validation on {report.total_incoming} sales records...")

    df = df_sales.copy()

    # 1. Deduplication
    initial_count = len(df)
    df = df.drop_duplicates(subset=["sale_id"], keep="first")
    report.duplicates_removed = initial_count - len(df)
    if report.duplicates_removed > 0:
        logger.info(f"[DQ Gate] Removed {report.duplicates_removed} duplicate records.")

    # 2. Date Format Validation & Standardization
    initial_count = len(df)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    invalid_dates_mask = df["transaction_date"].isna()
    report.invalid_dates_rejected = int(invalid_dates_mask.sum())
    df = df[~invalid_dates_mask]
    df["transaction_date"] = df["transaction_date"].dt.strftime("%Y-%m-%d")

    # 3. Numeric Conversions
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce")
    df["customer_id"] = pd.to_numeric(df["customer_id"], errors="coerce")

    # 4. Check negative or zero quantities
    negative_qty_mask = (df["quantity"] <= 0) | df["quantity"].isna()
    report.negative_quantities_rejected = int(negative_qty_mask.sum())
    if report.negative_quantities_rejected > 0:
        logger.warning(f"[DQ Gate] Rejected {report.negative_quantities_rejected} records with negative/null quantities.")
    df = df[~negative_qty_mask]

    # 5. Check negative or zero unit prices
    invalid_price_mask = (df["unit_price"] <= 0) | df["unit_price"].isna()
    report.invalid_prices_rejected = int(invalid_price_mask.sum())
    if report.invalid_prices_rejected > 0:
        logger.warning(f"[DQ Gate] Rejected {report.invalid_prices_rejected} records with invalid/negative prices.")
    df = df[~invalid_price_mask]

    # 6. Null Handling for optional descriptive fields
    null_payment_mask = df["payment_method"].isna() | (df["payment_method"].str.strip() == "")
    report.nulls_handled = int(null_payment_mask.sum())
    df.loc[null_payment_mask, "payment_method"] = "Credit Card"

    null_channel_mask = df["channel"].isna() | (df["channel"].str.strip() == "")
    df.loc[null_channel_mask, "channel"] = "Online"

    # Recalculate and validate total_amount consistency
    df["discount_pct"] = df["discount_pct"].fillna(0.0)
    df["total_amount"] = (df["quantity"] * df["unit_price"] * (1 - df["discount_pct"])).round(2)

    # 7. Referential Integrity / Foreign Key Validation
    if valid_product_ids:
        fk_prod_mask = df["product_id"].isin(valid_product_ids)
        fk_prod_violations = int((~fk_prod_mask).sum())
    else:
        fk_prod_violations = 0
        fk_prod_mask = pd.Series(True, index=df.index)

    if valid_customer_ids:
        fk_cust_mask = df["customer_id"].isin(valid_customer_ids)
        fk_cust_violations = int((~fk_cust_mask).sum())
    else:
        fk_cust_violations = 0
        fk_cust_mask = pd.Series(True, index=df.index)

    report.foreign_key_violations_rejected = fk_prod_violations + fk_cust_violations
    if report.foreign_key_violations_rejected > 0:
        logger.warning(f"[DQ Gate] Rejected {report.foreign_key_violations_rejected} foreign key violations.")
    df = df[fk_prod_mask & fk_cust_mask]

    # Final counts and status
    report.final_valid_records = len(df)
    report.validation_passed = (report.final_valid_records > 0)
    report.save_report()

    logger.info(
        f"[DQ Finished] Incoming: {report.total_incoming} | Valid: {report.final_valid_records} | "
        f"Duplicates: {report.duplicates_removed} | Invalid Prices: {report.invalid_prices_rejected} | "
        f"Negative Qty: {report.negative_quantities_rejected} | FK Violations: {report.foreign_key_violations_rejected}"
    )

    return df, report


def get_latest_dq_report() -> Dict[str, Any]:
    """Retrieves the latest data quality report JSON."""
    report_file = config.PROCESSED_DATA_DIR / "dq_report_sales.json"
    if report_file.exists():
        with open(report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "dataset_name": "sales",
        "timestamp": "N/A",
        "total_incoming": 0,
        "duplicates_removed": 0,
        "nulls_handled": 0,
        "negative_quantities_rejected": 0,
        "invalid_prices_rejected": 0,
        "foreign_key_violations_rejected": 0,
        "final_valid_records": 0,
        "acceptance_rate_pct": 100.0,
        "validation_passed": True
    }
