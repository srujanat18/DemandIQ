-- =======================================================
-- DemandIQ Database Schema (OLTP & Core Operational Layer)
-- Target: MySQL 8.0+ / SQLite compatible
-- =======================================================

-- 1. Categories Table (Normalization of product categories)
CREATE TABLE IF NOT EXISTS categories (
    category_id INT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Products Table
CREATE TABLE IF NOT EXISTS products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category_id INT NOT NULL,
    cost_price DECIMAL(10, 2) NOT NULL,
    list_price DECIMAL(10, 2) NOT NULL,
    stock_quantity INT DEFAULT 0,
    reorder_level INT DEFAULT 20,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT
);

-- 3. Customers Table
CREATE TABLE IF NOT EXISTS customers (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) UNIQUE,
    location VARCHAR(100) NOT NULL,
    segment VARCHAR(50) DEFAULT 'Consumer', -- Consumer, Corporate, Wholesale
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Sales Transactions Table
CREATE TABLE IF NOT EXISTS sales (
    sale_id INT PRIMARY KEY,
    transaction_date DATE NOT NULL,
    product_id INT NOT NULL,
    customer_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0),
    total_amount DECIMAL(12, 2) NOT NULL,
    discount_pct DECIMAL(5, 2) DEFAULT 0.00,
    payment_method VARCHAR(50) DEFAULT 'Credit Card',
    channel VARCHAR(50) DEFAULT 'Online', -- Online, In-Store, Distributor
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
);

-- 5. Weather Records Table (External Factor Ingestion)
CREATE TABLE IF NOT EXISTS weather (
    record_id INT PRIMARY KEY,
    recorded_date DATE NOT NULL,
    location VARCHAR(100) NOT NULL,
    temperature DECIMAL(5, 2), -- Celsius
    humidity DECIMAL(5, 2),    -- Percentage
    rainfall DECIMAL(6, 2),    -- mm
    weather_condition VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Competitor Pricing Table (Market Intelligence Ingestion)
CREATE TABLE IF NOT EXISTS competitors (
    competitor_id INT PRIMARY KEY,
    product_id INT NOT NULL,
    competitor_name VARCHAR(100) NOT NULL,
    competitor_price DECIMAL(10, 2) NOT NULL,
    recorded_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

-- 7. Demand Forecasts Table
CREATE TABLE IF NOT EXISTS forecasts (
    forecast_id INT PRIMARY KEY,
    product_id INT NOT NULL,
    forecast_date DATE NOT NULL,
    predicted_demand INT NOT NULL,
    lower_bound INT,
    upper_bound INT,
    model_name VARCHAR(100) DEFAULT 'Moving_Average_Seasonal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);

-- 8. Pipeline Execution Logs Table (Observability & Monitoring)
CREATE TABLE IF NOT EXISTS pipeline_logs (
    pipeline_id VARCHAR(64) PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_seconds DECIMAL(8, 2),
    records_processed INT DEFAULT 0,
    status VARCHAR(20) NOT NULL, -- 'SUCCESS', 'FAILED', 'RUNNING'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Query Performance & Analytical Acceleration
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(transaction_date);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_weather_date ON weather(recorded_date);
CREATE INDEX IF NOT EXISTS idx_forecast_product_date ON forecasts(product_id, forecast_date);
CREATE INDEX IF NOT EXISTS idx_logs_start ON pipeline_logs(start_time);
