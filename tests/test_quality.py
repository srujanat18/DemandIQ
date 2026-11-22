"""
Unit & Integration Tests for DemandIQ Data Quality Engine
"""
import pytest
import pandas as pd
from validation.data_quality import validate_and_clean_sales, DataQualityReport

def test_deduplication():
    """Verify that duplicate sale_ids are removed."""
    df_raw = pd.DataFrame([
        {"sale_id": 1, "transaction_date": "2026-05-01", "product_id": 101, "customer_id": 1001, "quantity": 2, "unit_price": 50.0, "total_amount": 100.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"},
        {"sale_id": 1, "transaction_date": "2026-05-01", "product_id": 101, "customer_id": 1001, "quantity": 2, "unit_price": 50.0, "total_amount": 100.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"},
        {"sale_id": 2, "transaction_date": "2026-05-02", "product_id": 101, "customer_id": 1001, "quantity": 1, "unit_price": 50.0, "total_amount": 50.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"}
    ])
    
    clean_df, report = validate_and_clean_sales(df_raw, valid_product_ids={101}, valid_customer_ids={1001})
    assert len(clean_df) == 2
    assert report.duplicates_removed == 1

def test_negative_quantity_rejection():
    """Verify that records with negative or zero quantities are rejected."""
    df_raw = pd.DataFrame([
        {"sale_id": 1, "transaction_date": "2026-05-01", "product_id": 101, "customer_id": 1001, "quantity": -5, "unit_price": 50.0, "total_amount": -250.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"},
        {"sale_id": 2, "transaction_date": "2026-05-02", "product_id": 101, "customer_id": 1001, "quantity": 0, "unit_price": 50.0, "total_amount": 0.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"},
        {"sale_id": 3, "transaction_date": "2026-05-03", "product_id": 101, "customer_id": 1001, "quantity": 3, "unit_price": 50.0, "total_amount": 150.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"}
    ])

    clean_df, report = validate_and_clean_sales(df_raw, valid_product_ids={101}, valid_customer_ids={1001})
    assert len(clean_df) == 1
    assert clean_df.iloc[0]["sale_id"] == 3
    assert report.negative_quantities_rejected == 2

def test_invalid_price_rejection():
    """Verify that records with negative unit prices are rejected."""
    df_raw = pd.DataFrame([
        {"sale_id": 1, "transaction_date": "2026-05-01", "product_id": 101, "customer_id": 1001, "quantity": 2, "unit_price": -20.0, "total_amount": -40.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"},
        {"sale_id": 2, "transaction_date": "2026-05-02", "product_id": 101, "customer_id": 1001, "quantity": 2, "unit_price": 45.0, "total_amount": 90.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"}
    ])

    clean_df, report = validate_and_clean_sales(df_raw, valid_product_ids={101}, valid_customer_ids={1001})
    assert len(clean_df) == 1
    assert report.invalid_prices_rejected == 1

def test_foreign_key_referential_integrity():
    """Verify that records referencing non-existent product_ids are rejected."""
    df_raw = pd.DataFrame([
        {"sale_id": 1, "transaction_date": "2026-05-01", "product_id": 9999, "customer_id": 1001, "quantity": 1, "unit_price": 50.0, "total_amount": 50.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"},
        {"sale_id": 2, "transaction_date": "2026-05-02", "product_id": 101, "customer_id": 1001, "quantity": 1, "unit_price": 50.0, "total_amount": 50.0, "discount_pct": 0, "payment_method": "Credit Card", "channel": "Online"}
    ])

    clean_df, report = validate_and_clean_sales(df_raw, valid_product_ids={101}, valid_customer_ids={1001})
    assert len(clean_df) == 1
    assert report.foreign_key_violations_rejected == 1

def test_null_value_imputation():
    """Verify that missing payment_method or channel are imputed with default values."""
    df_raw = pd.DataFrame([
        {"sale_id": 1, "transaction_date": "2026-05-01", "product_id": 101, "customer_id": 1001, "quantity": 1, "unit_price": 50.0, "total_amount": 50.0, "discount_pct": 0, "payment_method": "", "channel": None}
    ])

    clean_df, report = validate_and_clean_sales(df_raw, valid_product_ids={101}, valid_customer_ids={1001})
    assert len(clean_df) == 1
    assert clean_df.iloc[0]["payment_method"] == "Credit Card"
    assert clean_df.iloc[0]["channel"] == "Online"
    assert report.nulls_handled >= 1
