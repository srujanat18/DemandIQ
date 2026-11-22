-- ====================================================================
-- AWS Glue Data Catalog & Amazon Athena External Table Setup
-- Allows ad-hoc SQL querying over S3 Data Lake (Serverless Analytics)
-- ====================================================================

-- 1. Create Glue Data Catalog Database
CREATE DATABASE IF NOT EXISTS demandiq_datalake_db
COMMENT 'External Data Lake Catalog for DemandIQ Analytics';

-- 2. External Table: Clean Sales Data (stored in S3 CSV/Parquet)
CREATE EXTERNAL TABLE IF NOT EXISTS demandiq_datalake_db.ext_sales (
    sale_id INT,
    transaction_date STRING,
    product_id INT,
    customer_id INT,
    quantity INT,
    unit_price DOUBLE,
    total_amount DOUBLE,
    discount_pct DOUBLE,
    payment_method STRING,
    channel STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://demandiq-data-lake-raw/demandiq-lake/processed/sales/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 3. External Table: Product Catalog
CREATE EXTERNAL TABLE IF NOT EXISTS demandiq_datalake_db.ext_products (
    product_id INT,
    product_name STRING,
    category_id INT,
    cost_price DOUBLE,
    list_price DOUBLE,
    stock_quantity INT,
    reorder_level INT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://demandiq-data-lake-raw/demandiq-lake/raw/products/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 4. Athena Analytical Query: Monthly Sales Trend directly from S3
-- Demonstrates serverless big data querying without maintaining database servers
SELECT 
    SUBSTR(transaction_date, 1, 7) AS sales_month,
    COUNT(sale_id) AS total_orders,
    SUM(quantity) AS total_units_sold,
    ROUND(SUM(total_amount), 2) AS total_revenue
FROM demandiq_datalake_db.ext_sales
GROUP BY SUBSTR(transaction_date, 1, 7)
ORDER BY sales_month ASC;

-- 5. Athena Cross-Table Join: Product Margins & Revenue
SELECT 
    p.product_name,
    SUM(s.quantity) AS units_sold,
    ROUND(SUM(s.total_amount), 2) AS gross_revenue,
    ROUND(SUM(s.quantity * (s.unit_price - p.cost_price)), 2) AS net_profit
FROM demandiq_datalake_db.ext_sales s
JOIN demandiq_datalake_db.ext_products p ON s.product_id = p.product_id
GROUP BY p.product_name
ORDER BY gross_revenue DESC;
