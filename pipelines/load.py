"""
Data Loading Module for DemandIQ
Loads cleaned and transformed datasets into both normalized relational tables
and dimensional star schema warehouse tables.
"""
import logging
from typing import Dict
import pandas as pd
from sqlalchemy import text
from database.db_connection import get_engine
import config

logger = logging.getLogger("DemandIQ.Load")

def load_operational_tables(clean_data: Dict[str, pd.DataFrame]):
    """
    Loads normalized operational tables respecting foreign key dependency ordering:
    1. categories
    2. products
    3. customers
    4. sales
    5. weather
    6. competitors
    """
    engine = get_engine()
    logger.info("Loading cleaned records into OLTP database tables...")

    # Load order matters for referential integrity
    tables_order = ["categories", "products", "customers", "sales", "weather", "competitors"]

    with engine.begin() as conn:
        for tbl in tables_order:
            if tbl in clean_data:
                df = clean_data[tbl]
                # Using if_exists='replace' for initial load / staging replacement
                df.to_sql(tbl, conn, if_exists="replace", index=False)
                logger.info(f"Loaded {len(df)} records into table '{tbl}'")

def load_star_schema(star_schema: Dict[str, pd.DataFrame]):
    """
    Loads dimensional data warehouse tables:
    1. dim_date
    2. dim_product
    3. dim_customer
    4. fact_sales
    """
    engine = get_engine()
    logger.info("Loading transformed records into Star Schema analytical tables...")

    dims_order = ["dim_date", "dim_product", "dim_customer", "fact_sales"]

    with engine.begin() as conn:
        for tbl in dims_order:
            if tbl in star_schema:
                df = star_schema[tbl]
                df.to_sql(tbl, conn, if_exists="replace", index=False)
                logger.info(f"Loaded {len(df)} records into warehouse table '{tbl}'")

def load_all(clean_operational: Dict[str, pd.DataFrame], star_schema: Dict[str, pd.DataFrame]):
    """Loads both operational and analytical layers."""
    logger.info("--- Starting Database Loading Phase ---")
    load_operational_tables(clean_operational)
    load_star_schema(star_schema)
    logger.info("All tables loaded successfully.")
