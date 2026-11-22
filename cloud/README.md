# DemandIQ Cloud Integration (AWS Data Architecture)

This directory details how DemandIQ scales into an enterprise cloud data platform using **Amazon Web Services (AWS)**.

---

## 1. Cloud Architecture Overview

```
[Raw Sources: CSVs, Weather API]
               │
               ▼
   [Amazon S3 Raw Data Lake]
   (s3://demandiq-data-lake-raw/)
               │
               ▼
   [AWS Glue Data Catalog & ETL]
   (Crawler, Schema Registry & PySpark ETL)
         │                   │
         ▼                   ▼
 [Amazon Athena]     [Amazon Redshift]
 (Serverless SQL)    (Analytical Data Warehouse)
         │                   │
         └─────────┬─────────┘
                   ▼
     [DemandIQ Flask Dashboard / BI]
```

---

## 2. Component Breakdown

### A. Storage: Amazon S3 Data Lake
- **Bucket**: `demandiq-data-lake-raw`
- **Partitions**: Date-partitioned directory structure:
  - `s3://demandiq-data-lake-raw/demandiq-lake/raw/`
  - `s3://demandiq-data-lake-raw/demandiq-lake/processed/`
- **File formats**: Raw CSV/JSON; transformed into columnar **Apache Parquet** with Snappy compression for 80% query cost reduction.

### B. Catalog & Transformation: AWS Glue
- **AWS Glue Crawlers**: Automatically infer schemas from S3 objects and register metadata in the **Glue Data Catalog**.
- **AWS Glue Jobs (PySpark)**: Distributed transformation of multi-gigabyte transaction streams, handling deduplication, joins with customer dimensions, and data cleansing at scale.

### C. Serverless Analytics: Amazon Athena
- Allows querying data directly inside S3 buckets using standard ANSI SQL without provisioning database instances.
- Pre-configured DDL scripts are provided in [`glue_athena_setup.sql`](file:///Users/srujana/Desktop/DemandIQ/cloud/glue_athena_setup.sql).

### D. Data Warehouse: Amazon Redshift
- Used for high-concurrency sub-second OLAP reporting.
- Loads data using the `COPY` command directly from S3 parquet partitions.
- Utilizes distribution keys (`DISTKEY(product_id)`) and sort keys (`SORTKEY(transaction_date)`).

### E. Observability: Amazon CloudWatch & SNS
- Tracks pipeline failures, duration metrics, and triggers alerts via SNS if data validation thresholds are breached.

---

## 3. How to Run S3 Synchronization
Execute the bundled synchronization script:

```bash
# Dry-run simulation (no AWS credentials required)
python cloud/s3_sync.py

# Live sync (requires AWS credentials in .env)
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
python -c "from cloud.s3_sync import sync_to_s3; sync_to_s3(dry_run=False)"
```
