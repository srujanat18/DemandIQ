"""
Data Transformation & Star Schema Builder for DemandIQ
Cleans raw datasets via the Data Quality Engine and transforms them into
both normalized operational models and dimensional warehouse models.
"""
import logging
from typing import Dict, Any, Tuple
import pandas as pd
from validation.data_quality import validate_and_clean_sales, DataQualityReport
import config

logger = logging.getLogger("DemandIQ.Transform")

def transform_categories(raw_cats: pd.DataFrame) -> pd.DataFrame:
    """Standardizes and cleans categories dataset."""
    df = raw_cats.copy()
    df["category_id"] = pd.to_numeric(df["category_id"], errors="raise")
    df["category_name"] = df["category_name"].str.strip()
    df["description"] = df["description"].fillna("General Category")
    df = df.drop_duplicates(subset=["category_id"])
    return df

def transform_products(raw_prods: pd.DataFrame, valid_cat_ids: set) -> pd.DataFrame:
    """Standardizes and cleans products dataset."""
    df = raw_prods.copy()
    df["product_id"] = pd.to_numeric(df["product_id"], errors="raise")
    df["category_id"] = pd.to_numeric(df["category_id"], errors="raise")
    df["product_name"] = df["product_name"].str.strip()
    df["cost_price"] = pd.to_numeric(df["cost_price"], errors="coerce").round(2)
    df["list_price"] = pd.to_numeric(df["list_price"], errors="coerce").round(2)
    df["stock_quantity"] = pd.to_numeric(df["stock_quantity"], errors="coerce").fillna(0).astype(int)
    df["reorder_level"] = pd.to_numeric(df["reorder_level"], errors="coerce").fillna(10).astype(int)

    # Filter invalid category foreign keys
    if valid_cat_ids:
        df = df[df["category_id"].isin(valid_cat_ids)]

    df = df.drop_duplicates(subset=["product_id"])
    return df

def transform_customers(raw_custs: pd.DataFrame) -> pd.DataFrame:
    """Standardizes and cleans customer profiles."""
    df = raw_custs.copy()
    df["customer_id"] = pd.to_numeric(df["customer_id"], errors="raise")
    df["customer_name"] = df["customer_name"].str.strip()
    df["email"] = df["email"].str.strip().str.lower()
    df["location"] = df["location"].str.strip()
    df["segment"] = df["segment"].fillna("Consumer").str.strip()
    df = df.drop_duplicates(subset=["customer_id"])
    return df

def transform_weather(raw_weather: pd.DataFrame) -> pd.DataFrame:
    """Standardizes weather measurements."""
    df = raw_weather.copy()
    df["recorded_date"] = pd.to_datetime(df["recorded_date"]).dt.strftime("%Y-%m-%d")
    df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce").fillna(20.0).round(1)
    df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce").fillna(50.0).round(1)
    df["rainfall"] = pd.to_numeric(df["rainfall"], errors="coerce").fillna(0.0).round(2)
    df["weather_condition"] = df["weather_condition"].fillna("Clear")
    df = df.drop_duplicates(subset=["recorded_date", "location"])
    return df

def transform_competitors(raw_comp: pd.DataFrame, valid_product_ids: set) -> pd.DataFrame:
    """Standardizes competitor price feeds."""
    df = raw_comp.copy()
    df["competitor_id"] = pd.to_numeric(df["competitor_id"], errors="raise")
    df["product_id"] = pd.to_numeric(df["product_id"], errors="raise")
    df["competitor_name"] = df["competitor_name"].str.strip()
    df["competitor_price"] = pd.to_numeric(df["competitor_price"], errors="coerce").round(2)
    df["recorded_date"] = pd.to_datetime(df["recorded_date"]).dt.strftime("%Y-%m-%d")
    if valid_product_ids:
        df = df[df["product_id"].isin(valid_product_ids)]
    df = df.drop_duplicates(subset=["competitor_id"])
    return df

def build_star_schema(clean_sales: pd.DataFrame, clean_products: pd.DataFrame, 
                      clean_categories: pd.DataFrame, clean_customers: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Transforms normalized tables into a Dimensional Star Schema:
    - Dim_Date
    - Dim_Product
    - Dim_Customer
    - Fact_Sales
    """
    logger.info("Constructing Star Schema analytical models (Dim_Date, Dim_Product, Dim_Customer, Fact_Sales)...")

    # 1. Dim_Date
    dates_series = pd.to_datetime(clean_sales["transaction_date"].unique())
    dim_date = pd.DataFrame({"full_date_dt": dates_series})
    dim_date["date_id"] = dim_date["full_date_dt"].dt.strftime("%Y%m%d").astype(int)
    dim_date["full_date"] = dim_date["full_date_dt"].dt.strftime("%Y-%m-%d")
    dim_date["day"] = dim_date["full_date_dt"].dt.day
    dim_date["month"] = dim_date["full_date_dt"].dt.month
    dim_date["month_name"] = dim_date["full_date_dt"].dt.strftime("%B")
    dim_date["quarter"] = dim_date["full_date_dt"].dt.quarter
    dim_date["year"] = dim_date["full_date_dt"].dt.year
    dim_date["day_of_week"] = dim_date["full_date_dt"].dt.strftime("%A")
    dim_date["is_weekend"] = dim_date["full_date_dt"].dt.dayofweek.isin([5, 6]).astype(int)
    dim_date = dim_date.drop(columns=["full_date_dt"]).sort_values("date_id").reset_index(drop=True)

    # 2. Dim_Product
    prod_cat = pd.merge(clean_products, clean_categories, on="category_id", how="left")
    dim_product = pd.DataFrame({
        "product_key": prod_cat["product_id"], # surrogate / natural key
        "product_id": prod_cat["product_id"],
        "product_name": prod_cat["product_name"],
        "category_name": prod_cat["category_name"].fillna("Unknown"),
        "cost_price": prod_cat["cost_price"],
        "list_price": prod_cat["list_price"],
        "margin_pct": (((prod_cat["list_price"] - prod_cat["cost_price"]) / prod_cat["list_price"]) * 100).round(2)
    })

    # 3. Dim_Customer
    dim_customer = pd.DataFrame({
        "customer_key": clean_customers["customer_id"],
        "customer_id": clean_customers["customer_id"],
        "customer_name": clean_customers["customer_name"],
        "location": clean_customers["location"],
        "segment": clean_customers["segment"]
    })

    # 4. Fact_Sales
    # Join with products to get cost for net profit calculation
    sales_merged = pd.merge(
        clean_sales, 
        dim_product[["product_id", "product_key", "cost_price"]], 
        on="product_id", 
        how="inner"
    )
    sales_merged["date_id"] = pd.to_datetime(sales_merged["transaction_date"]).dt.strftime("%Y%m%d").astype(int)
    sales_merged["customer_key"] = sales_merged["customer_id"]
    sales_merged["gross_revenue"] = sales_merged["total_amount"]
    sales_merged["total_cost"] = (sales_merged["quantity"] * sales_merged["cost_price"]).round(2)
    sales_merged["net_profit"] = (sales_merged["gross_revenue"] - sales_merged["total_cost"]).round(2)

    fact_sales = pd.DataFrame({
        "fact_id": sales_merged["sale_id"],
        "sale_id": sales_merged["sale_id"],
        "date_id": sales_merged["date_id"],
        "product_key": sales_merged["product_key"],
        "customer_key": sales_merged["customer_key"],
        "quantity": sales_merged["quantity"],
        "unit_price": sales_merged["unit_price"],
        "gross_revenue": sales_merged["gross_revenue"],
        "total_cost": sales_merged["total_cost"],
        "net_profit": sales_merged["net_profit"],
        "channel": sales_merged["channel"]
    })

    logger.info(f"Star schema prepared: Fact_Sales has {len(fact_sales)} rows across {len(dim_date)} dates.")
    return {
        "dim_date": dim_date,
        "dim_product": dim_product,
        "dim_customer": dim_customer,
        "fact_sales": fact_sales
    }

def transform_all(raw_data: Dict[str, pd.DataFrame]) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame], DataQualityReport]:
    """
    Transforms all datasets: applies data cleaning and constructs star schema.
    Returns: (clean_operational_data, star_schema_data, dq_report)
    """
    logger.info("--- Starting Transformation Phase ---")

    # 1. Transform Dimensions / Reference Tables
    clean_cats = transform_categories(raw_data["categories"])
    valid_cat_ids = set(clean_cats["category_id"])

    clean_prods = transform_products(raw_data["products"], valid_cat_ids)
    valid_prod_ids = set(clean_prods["product_id"])

    clean_custs = transform_customers(raw_data["customers"])
    valid_cust_ids = set(clean_custs["customer_id"])

    clean_weather = transform_weather(raw_data["weather"])
    clean_comp = transform_competitors(raw_data["competitors"], valid_prod_ids)

    # 2. Transform & Validate Sales via Data Quality Engine
    clean_sales, dq_report = validate_and_clean_sales(
        raw_data["sales"],
        valid_product_ids=valid_prod_ids,
        valid_customer_ids=valid_cust_ids
    )

    # Save cleaned sales CSV to processed/
    clean_sales.to_csv(config.PROCESSED_DATA_DIR / "sales_clean.csv", index=False)
    clean_prods.to_csv(config.PROCESSED_DATA_DIR / "products_clean.csv", index=False)

    # 3. Construct Star Schema Models
    star_schema = build_star_schema(clean_sales, clean_prods, clean_cats, clean_custs)

    clean_operational = {
        "categories": clean_cats,
        "products": clean_prods,
        "customers": clean_custs,
        "weather": clean_weather,
        "competitors": clean_comp,
        "sales": clean_sales
    }

    return clean_operational, star_schema, dq_report
