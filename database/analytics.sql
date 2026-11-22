-- =======================================================
-- DemandIQ Analytical Data Warehouse (Star Schema & Views)
-- =======================================================

-- 1. Dimension: Date (dim_date)
CREATE TABLE IF NOT EXISTS dim_date (
    date_id INT PRIMARY KEY,              -- YYYYMMDD format
    full_date DATE NOT NULL UNIQUE,
    day INT NOT NULL,
    month INT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    quarter INT NOT NULL,
    year INT NOT NULL,
    day_of_week VARCHAR(15) NOT NULL,
    is_weekend INT DEFAULT 0
);

-- 2. Dimension: Product (dim_product)
CREATE TABLE IF NOT EXISTS dim_product (
    product_key INT PRIMARY KEY,
    product_id INT NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    cost_price DECIMAL(10, 2) NOT NULL,
    list_price DECIMAL(10, 2) NOT NULL,
    margin_pct DECIMAL(5, 2)
);

-- 3. Dimension: Customer (dim_customer)
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key INT PRIMARY KEY,
    customer_id INT NOT NULL,
    customer_name VARCHAR(150) NOT NULL,
    location VARCHAR(100) NOT NULL,
    segment VARCHAR(50) NOT NULL
);

-- 4. Fact Table: Sales (fact_sales)
CREATE TABLE IF NOT EXISTS fact_sales (
    fact_id INT PRIMARY KEY,
    sale_id INT NOT NULL,
    date_id INT NOT NULL,
    product_key INT NOT NULL,
    customer_key INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    gross_revenue DECIMAL(12, 2) NOT NULL,
    total_cost DECIMAL(12, 2) NOT NULL,
    net_profit DECIMAL(12, 2) NOT NULL,
    channel VARCHAR(50),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
    FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key)
);

-- Indexes for Star Schema Fast Join Traversal
CREATE INDEX IF NOT EXISTS idx_fact_date ON fact_sales(date_id);
CREATE INDEX IF NOT EXISTS idx_fact_prod ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_cust ON fact_sales(customer_key);


-- =======================================================
-- Analytical Reporting Views
-- Demonstrating Joins, Aggregations, Subqueries, & Metrics
-- =======================================================

-- View 1: Daily Sales & Revenue Performance
CREATE VIEW IF NOT EXISTS v_daily_sales_summary AS
SELECT 
    s.transaction_date,
    COUNT(s.sale_id) AS total_orders,
    SUM(s.quantity) AS total_units_sold,
    ROUND(SUM(s.total_amount), 2) AS total_revenue,
    ROUND(AVG(s.total_amount), 2) AS avg_order_value,
    COALESCE(w.temperature, 0) AS avg_temperature,
    COALESCE(w.weather_condition, 'Clear') AS weather_condition
FROM sales s
LEFT JOIN weather w ON s.transaction_date = w.recorded_date
GROUP BY s.transaction_date, w.temperature, w.weather_condition;

-- View 2: Monthly Sales Summary & Trends
CREATE VIEW IF NOT EXISTS v_monthly_sales_summary AS
SELECT 
    SUBSTR(s.transaction_date, 1, 7) AS sales_month,
    COUNT(s.sale_id) AS total_orders,
    SUM(s.quantity) AS total_units_sold,
    ROUND(SUM(s.total_amount), 2) AS total_revenue,
    ROUND(SUM(s.total_amount) / COUNT(DISTINCT s.customer_id), 2) AS revenue_per_customer
FROM sales s
GROUP BY SUBSTR(s.transaction_date, 1, 7);

-- View 3: Product-Wise Sales & Profitability Analysis
CREATE VIEW IF NOT EXISTS v_product_performance AS
SELECT 
    p.product_id,
    p.product_name,
    c.category_name,
    p.cost_price,
    p.list_price,
    p.stock_quantity,
    COALESCE(SUM(s.quantity), 0) AS units_sold,
    ROUND(COALESCE(SUM(s.total_amount), 0), 2) AS gross_revenue,
    ROUND(COALESCE(SUM(s.quantity * (s.unit_price - p.cost_price)), 0), 2) AS total_profit,
    ROUND(
        CASE 
            WHEN SUM(s.total_amount) > 0 
            THEN (SUM(s.quantity * (s.unit_price - p.cost_price)) / SUM(s.total_amount)) * 100 
            ELSE 0 
        END, 2
    ) AS profit_margin_pct
FROM products p
JOIN categories c ON p.category_id = c.category_id
LEFT JOIN sales s ON p.product_id = s.product_id
GROUP BY p.product_id, p.product_name, c.category_name, p.cost_price, p.list_price, p.stock_quantity;

-- View 4: Category-Wise Sales Distribution
CREATE VIEW IF NOT EXISTS v_category_sales AS
SELECT 
    c.category_name,
    COUNT(DISTINCT p.product_id) AS total_products,
    COALESCE(SUM(s.quantity), 0) AS units_sold,
    ROUND(COALESCE(SUM(s.total_amount), 0), 2) AS total_revenue
FROM categories c
LEFT JOIN products p ON c.category_id = p.category_id
LEFT JOIN sales s ON p.product_id = s.product_id
GROUP BY c.category_name;

-- View 5: Region-Wise Customer & Sales Analysis
CREATE VIEW IF NOT EXISTS v_region_sales AS
SELECT 
    cust.location AS region,
    COUNT(DISTINCT cust.customer_id) AS total_customers,
    COUNT(s.sale_id) AS total_orders,
    ROUND(COALESCE(SUM(s.total_amount), 0), 2) AS total_revenue
FROM customers cust
LEFT JOIN sales s ON cust.customer_id = s.customer_id
GROUP BY cust.location;

-- View 6: Top-Selling Products (Ranked)
CREATE VIEW IF NOT EXISTS v_top_selling_products AS
SELECT 
    p.product_id,
    p.product_name,
    c.category_name,
    SUM(s.quantity) AS total_units_sold,
    ROUND(SUM(s.total_amount), 2) AS total_revenue
FROM sales s
JOIN products p ON s.product_id = p.product_id
JOIN categories c ON p.category_id = c.category_id
GROUP BY p.product_id, p.product_name, c.category_name
ORDER BY total_revenue DESC;

-- View 7: Inventory Demand vs Stock Risk Monitor
CREATE VIEW IF NOT EXISTS v_inventory_demand_risk AS
SELECT 
    p.product_id,
    p.product_name,
    c.category_name,
    p.stock_quantity,
    p.reorder_level,
    COALESCE(f.predicted_demand, 0) AS predicted_30d_demand,
    CASE 
        WHEN p.stock_quantity <= p.reorder_level THEN 'CRITICAL: Reorder Immediately'
        WHEN p.stock_quantity < COALESCE(f.predicted_demand, 0) THEN 'HIGH RISK: Stockout Expected'
        WHEN p.stock_quantity > (COALESCE(f.predicted_demand, 0) * 2) THEN 'LOW: Excess Inventory'
        ELSE 'OPTIMAL: Balanced Stock'
    END AS stock_status
FROM products p
JOIN categories c ON p.category_id = c.category_id
LEFT JOIN (
    SELECT product_id, SUM(predicted_demand) AS predicted_demand
    FROM forecasts
    GROUP BY product_id
) f ON p.product_id = f.product_id;
