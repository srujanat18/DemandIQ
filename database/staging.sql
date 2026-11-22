-- =======================================================
-- DemandIQ Staging Area Schema (ELT / Data Ingestion Landing)
-- =======================================================

-- Staging table for raw incoming sales transactions
CREATE TABLE IF NOT EXISTS stg_sales (
    raw_id INT PRIMARY KEY,
    transaction_date VARCHAR(50),
    product_id VARCHAR(50),
    customer_id VARCHAR(50),
    quantity VARCHAR(50),
    unit_price VARCHAR(50),
    total_amount VARCHAR(50),
    payment_method VARCHAR(100),
    channel VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Staging table for product catalog feeds
CREATE TABLE IF NOT EXISTS stg_products (
    product_id VARCHAR(50),
    product_name VARCHAR(255),
    category_name VARCHAR(100),
    cost_price VARCHAR(50),
    list_price VARCHAR(50),
    stock_quantity VARCHAR(50),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Staging table for customer profile updates
CREATE TABLE IF NOT EXISTS stg_customers (
    customer_id VARCHAR(50),
    customer_name VARCHAR(150),
    email VARCHAR(150),
    location VARCHAR(100),
    segment VARCHAR(50),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Staging table for weather API JSON records
CREATE TABLE IF NOT EXISTS stg_weather (
    recorded_date VARCHAR(50),
    location VARCHAR(100),
    temperature VARCHAR(50),
    humidity VARCHAR(50),
    rainfall VARCHAR(50),
    weather_condition VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Staging table for competitor scraped data
CREATE TABLE IF NOT EXISTS stg_competitors (
    product_id VARCHAR(50),
    competitor_name VARCHAR(100),
    competitor_price VARCHAR(50),
    recorded_date VARCHAR(50),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
