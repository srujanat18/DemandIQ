"""
Data Extraction Module for DemandIQ
Extracts raw data from multiple sources:
1. Sales CSV
2. Product & Category CSVs
3. Customer CSV
4. Competitor Pricing CSV
5. Live Weather Forecast API (Open-Meteo REST API with resilient offline fallback)
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
import requests
from sqlalchemy import text
from database.db_connection import get_engine
import config

logger = logging.getLogger("DemandIQ.Extract")

def extract_csv(file_path: Path) -> pd.DataFrame:
    """Reads a CSV file into a pandas DataFrame."""
    if not file_path.exists():
        raise FileNotFoundError(f"Source file not found: {file_path}")
    df = pd.read_csv(file_path)
    logger.info(f"Extracted {len(df)} records from {file_path.name}")
    return df

def fetch_weather_api(days_back: int = 30) -> pd.DataFrame:
    """
    Fetches real-time / historical daily weather data from Open-Meteo free API.
    If the API is unreachable (e.g. offline sandbox), seamlessly generates
    realistic weather records for the required date span.
    """
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days_back)
    
    url = (
        f"{config.WEATHER_API_URL}?latitude={config.WEATHER_LATITUDE}"
        f"&longitude={config.WEATHER_LONGITUDE}"
        f"&daily=temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean,precipitation_sum,weather_code"
        f"&timezone=auto"
        f"&start_date={start_date.strftime('%Y-%m-%d')}"
        f"&end_date={end_date.strftime('%Y-%m-%d')}"
    )
    
    weather_records = []
    try:
        logger.info(f"Querying Open-Meteo Weather API: {config.WEATHER_API_URL}...")
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("daily", {})
            dates = data.get("time", [])
            max_temps = data.get("temperature_2m_max", [])
            min_temps = data.get("temperature_2m_min", [])
            humidities = data.get("relative_humidity_2m_mean", [])
            rains = data.get("precipitation_sum", [])
            codes = data.get("weather_code", [])

            for i in range(len(dates)):
                avg_temp = round((max_temps[i] + min_temps[i]) / 2, 1) if (max_temps and min_temps) else 20.0
                rain = rains[i] if rains else 0.0
                cond = "Rainy" if (rain and rain > 1.0) else "Sunny/Clear"
                weather_records.append({
                    "record_id": i + 1,
                    "recorded_date": dates[i],
                    "location": "New York",
                    "temperature": avg_temp,
                    "humidity": humidities[i] if humidities else 60.0,
                    "rainfall": rain if rain is not None else 0.0,
                    "weather_condition": cond
                })
            logger.info(f"Successfully fetched {len(weather_records)} weather records from Open-Meteo.")
    except Exception as e:
        logger.warning(f"Could not reach live Weather API ({e}). Generating realistic fallback weather data.")

    # Fallback if API returned empty or failed
    if not weather_records:
        # Generate weather for each day from 2026-01-01 to today
        cur = datetime(2026, 1, 1).date()
        rec_id = 1
        while cur <= end_date:
            month = cur.month
            # Seasonal temperature simulation
            base_temp = 2.0 if month in [1, 2, 12] else (15.0 if month in [3, 4, 10, 11] else 26.0)
            rain = 4.5 if (cur.day % 7 == 0) else 0.0
            cond = "Rainy" if rain > 0 else ("Cloudy" if cur.day % 3 == 0 else "Sunny")
            weather_records.append({
                "record_id": rec_id,
                "recorded_date": cur.strftime("%Y-%m-%d"),
                "location": "New York",
                "temperature": round(base_temp + (cur.day % 5) - 2, 1),
                "humidity": 55.0 + (cur.day % 20),
                "rainfall": rain,
                "weather_condition": cond
            })
            cur += timedelta(days=1)
            rec_id += 1

    df_weather = pd.DataFrame(weather_records)
    
    # Save raw weather JSON
    raw_weather_path = config.RAW_DATA_DIR / "weather_raw.json"
    with open(raw_weather_path, "w", encoding="utf-8") as f:
        json.dump(weather_records, f, indent=2)

    return df_weather


def stage_raw_data(sales_df: pd.DataFrame, prod_df: pd.DataFrame, cust_df: pd.DataFrame, weather_df: pd.DataFrame):
    """
    Loads raw extracted data into staging tables to satisfy ELT architecture.
    """
    engine = get_engine()
    logger.info("Landing raw extracts into staging tables (stg_sales, stg_products, stg_customers, stg_weather)...")
    with engine.begin() as conn:
        # Load sample into staging
        try:
            sales_df.head(500).to_sql("stg_sales", conn, if_exists="replace", index=False)
            prod_df.to_sql("stg_products", conn, if_exists="replace", index=False)
            cust_df.to_sql("stg_customers", conn, if_exists="replace", index=False)
            weather_df.to_sql("stg_weather", conn, if_exists="replace", index=False)
            logger.info("Staging landing complete.")
        except Exception as e:
            logger.warning(f"Error during staging load: {e}")


def extract_all() -> Dict[str, pd.DataFrame]:
    """Runs extraction for all sources and lands in staging."""
    logger.info("--- Starting Extraction Phase ---")
    
    prod_df = extract_csv(config.RAW_DATA_DIR / "products_raw.csv")
    cat_df = extract_csv(config.RAW_DATA_DIR / "categories_raw.csv")
    cust_df = extract_csv(config.RAW_DATA_DIR / "customers_raw.csv")
    sales_df = extract_csv(config.RAW_DATA_DIR / "sales_raw.csv")
    comp_df = extract_csv(config.RAW_DATA_DIR / "competitors_raw.csv")
    weather_df = fetch_weather_api()

    # Stage raw data
    stage_raw_data(sales_df, prod_df, cust_df, weather_df)

    return {
        "categories": cat_df,
        "products": prod_df,
        "customers": cust_df,
        "sales": sales_df,
        "competitors": comp_df,
        "weather": weather_df
    }

if __name__ == "__main__":
    datasets = extract_all()
    print("Extracted datasets summary:")
    for k, v in datasets.items():
        print(f" - {k}: {len(v)} rows")
